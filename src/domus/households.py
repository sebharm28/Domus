"""Apartment / household scoping — chat_id, join codes, membership."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from pathlib import Path

from domus import db

DEFAULT_CHAT_ID = 1
_TELEGRAM_CHAT_CEILING = 99
JOIN_CODE_LENGTH = 13
JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits
MEMBER_ACTIVE = "active"
MEMBER_PENDING = "pending"
MEMBER_REMOVED = "removed"
ROLE_OWNER = "owner"
ROLE_MEMBER = "member"


def normalize_apartment(label: str | None) -> str | None:
    if not label:
        return None
    cleaned = label.strip()
    return cleaned or None


def generate_join_code(length: int = JOIN_CODE_LENGTH) -> str:
    """13-character apartment ID (uppercase letters + digits)."""
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(length))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unique_join_code(conn) -> str:
    for _ in range(32):
        code = generate_join_code()
        row = conn.execute(
            "SELECT 1 FROM apartments WHERE join_code = ?",
            (code,),
        ).fetchone()
        if not row:
            return code
    raise RuntimeError("Could not allocate unique apartment join code")


def ensure_apartment_join_code(db_path: Path, apartment: str) -> str:
    """Return join_code for an apartment, generating one if missing."""
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment label required")
    now = _now_iso()
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT join_code FROM apartments WHERE label = ?",
            (label,),
        ).fetchone()
        if row and row["join_code"]:
            return row["join_code"]
        code = _unique_join_code(conn)
        if row:
            conn.execute(
                "UPDATE apartments SET join_code = ? WHERE label = ?",
                (code, label),
            )
        else:
            chat_id = get_or_create_apartment_chat(db_path, label)
            conn.execute(
                """
                UPDATE apartments SET join_code = ?
                WHERE label = ? AND (join_code IS NULL OR join_code = '')
                """,
                (code, label),
            )
            if conn.total_changes == 0:
                conn.execute(
                    """
                    INSERT INTO apartments (label, chat_id, created_at, join_code)
                    VALUES (?, ?, ?, ?)
                    """,
                    (label, chat_id, now, code),
                )
        return code


def backfill_apartment_memberships(db_path: Path) -> None:
    """Migrate legacy profiles (apartment string only) into apartment_members."""
    now = _now_iso()
    with db.connect(db_path) as conn:
        profiles = conn.execute(
            "SELECT telegram_user_id, apartment FROM users WHERE apartment IS NOT NULL AND apartment != ''"
        ).fetchall()
        for profile in profiles:
            label = normalize_apartment(profile["apartment"])
            if not label:
                continue
            ensure_apartment_join_code(db_path, label)
            existing = conn.execute(
                """
                SELECT id FROM apartment_members
                WHERE apartment_label = ? AND user_id = ?
                """,
                (label, profile["telegram_user_id"]),
            ).fetchone()
            if existing:
                continue
            owners = conn.execute(
                """
                SELECT COUNT(*) AS c FROM apartment_members
                WHERE apartment_label = ? AND role = ? AND status = ?
                """,
                (label, ROLE_OWNER, MEMBER_ACTIVE),
            ).fetchone()["c"]
            role = ROLE_OWNER if owners == 0 else ROLE_MEMBER
            conn.execute(
                """
                INSERT INTO apartment_members
                    (apartment_label, user_id, role, status, requested_at, joined_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (label, profile["telegram_user_id"], role, MEMBER_ACTIVE, now, now),
            )
            apt = conn.execute(
                "SELECT created_by_user_id FROM apartments WHERE label = ?",
                (label,),
            ).fetchone()
            if apt and apt["created_by_user_id"] is None and role == ROLE_OWNER:
                conn.execute(
                    "UPDATE apartments SET created_by_user_id = ? WHERE label = ?",
                    (profile["telegram_user_id"], label),
                )


def get_or_create_apartment_chat(db_path: Path, apartment: str) -> int:
    """Return a stable chat_id for an apartment label (creates row if needed)."""
    label = normalize_apartment(apartment)
    if not label:
        return DEFAULT_CHAT_ID

    now = _now_iso()
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT chat_id FROM apartments WHERE label = ?",
            (label,),
        ).fetchone()
        if row:
            return int(row["chat_id"])

        max_row = conn.execute("SELECT MAX(chat_id) AS m FROM apartments").fetchone()
        next_id = int(max_row["m"] or _TELEGRAM_CHAT_CEILING) + 1
        if next_id <= _TELEGRAM_CHAT_CEILING:
            next_id = _TELEGRAM_CHAT_CEILING + 1

        conn.execute(
            """
            INSERT INTO apartments (label, chat_id, created_at)
            VALUES (?, ?, ?)
            """,
            (label, next_id, now),
        )
        return next_id


def create_apartment_with_owner(
    db_path: Path,
    apartment: str,
    owner_user_id: int,
    *,
    owner_name: str | None = None,
) -> dict:
    """Create apartment + join code; owner is immediately active."""
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment name required")
    if db.get_user_profile(db_path, owner_user_id) is None:
        db.upsert_user_profile(
            db_path,
            owner_user_id,
            owner_name or f"User {owner_user_id}",
        )
    now = _now_iso()
    chat_id = get_or_create_apartment_chat(db_path, label)
    with db.connect(db_path) as conn:
        code = _unique_join_code(conn)
        row = conn.execute("SELECT label FROM apartments WHERE label = ?", (label,)).fetchone()
        if row:
            conn.execute(
                """
                UPDATE apartments
                SET join_code = COALESCE(join_code, ?),
                    created_by_user_id = COALESCE(created_by_user_id, ?)
                WHERE label = ?
                """,
                (code, owner_user_id, label),
            )
            code_row = conn.execute(
                "SELECT join_code FROM apartments WHERE label = ?",
                (label,),
            ).fetchone()
            code = code_row["join_code"] or code
        else:
            conn.execute(
                """
                INSERT INTO apartments (label, chat_id, created_at, join_code, created_by_user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (label, chat_id, now, code, owner_user_id),
            )
        conn.execute(
            """
            INSERT INTO apartment_members
                (apartment_label, user_id, role, status, requested_at, joined_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(apartment_label, user_id) DO UPDATE SET
                role = excluded.role,
                status = excluded.status,
                joined_at = excluded.joined_at
            """,
            (label, owner_user_id, ROLE_OWNER, MEMBER_ACTIVE, now, now),
        )
    db.update_user_profile(db_path, owner_user_id, apartment=label)
    return apartment_payload(db_path, label)


def request_join_apartment(db_path: Path, user_id: int, join_code: str) -> dict:
    """Join an apartment by code — pending until owner accepts."""
    code = (join_code or "").strip().upper()
    if len(code) != JOIN_CODE_LENGTH:
        raise ValueError(f"Join code must be {JOIN_CODE_LENGTH} characters")
    now = _now_iso()
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT label FROM apartments WHERE join_code = ?",
            (code,),
        ).fetchone()
        if not row:
            raise ValueError("Unknown apartment code")
        label = row["label"]
        conn.execute(
            """
            INSERT INTO apartment_members
                (apartment_label, user_id, role, status, requested_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(apartment_label, user_id) DO UPDATE SET
                status = CASE
                    WHEN apartment_members.status = ? THEN ?
                    ELSE apartment_members.status
                END,
                requested_at = excluded.requested_at
            """,
            (label, user_id, ROLE_MEMBER, MEMBER_PENDING, now, MEMBER_REMOVED, MEMBER_PENDING),
        )
    return {
        "apartment_label": label,
        "join_code": code,
        "status": MEMBER_PENDING,
        "message": "Request sent — waiting for an apartment member to approve.",
    }


def accept_apartment_member(
    db_path: Path,
    apartment: str,
    member_user_id: int,
    *,
    accepted_by_user_id: int,
) -> dict:
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    if not _user_can_manage_members(db_path, label, accepted_by_user_id):
        raise ValueError("Only apartment owners can approve members")
    now = _now_iso()
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT status FROM apartment_members
            WHERE apartment_label = ? AND user_id = ?
            """,
            (label, member_user_id),
        ).fetchone()
        if not row or row["status"] != MEMBER_PENDING:
            raise ValueError("No pending request for this user")
        conn.execute(
            """
            UPDATE apartment_members
            SET status = ?, joined_at = ?
            WHERE apartment_label = ? AND user_id = ?
            """,
            (MEMBER_ACTIVE, now, label, member_user_id),
        )
    db.update_user_profile(db_path, member_user_id, apartment=label)
    return members_payload(db_path, label)


def kick_apartment_member(
    db_path: Path,
    apartment: str,
    member_user_id: int,
    *,
    kicked_by_user_id: int,
) -> dict:
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    if member_user_id == kicked_by_user_id:
        raise ValueError("You cannot remove yourself")
    if not _user_can_manage_members(db_path, label, kicked_by_user_id):
        raise ValueError("Only apartment owners can remove members")
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT role FROM apartment_members
            WHERE apartment_label = ? AND user_id = ? AND status = ?
            """,
            (label, member_user_id, MEMBER_ACTIVE),
        ).fetchone()
        if not row:
            raise ValueError("Member not found")
        if row["role"] == ROLE_OWNER:
            raise ValueError("Cannot remove the apartment owner")
        conn.execute(
            """
            UPDATE apartment_members SET status = ?
            WHERE apartment_label = ? AND user_id = ?
            """,
            (MEMBER_REMOVED, label, member_user_id),
        )
    profile = db.get_user_profile(db_path, member_user_id)
    if profile and normalize_apartment(profile.apartment) == label:
        db.update_user_profile(db_path, member_user_id, apartment=None)
    return members_payload(db_path, label)


def _user_can_manage_members(db_path: Path, apartment: str, user_id: int) -> bool:
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT role FROM apartment_members
            WHERE apartment_label = ? AND user_id = ? AND status = ?
            """,
            (apartment, user_id, MEMBER_ACTIVE),
        ).fetchone()
    return row is not None and row["role"] == ROLE_OWNER


def apartment_for_user(db_path: Path, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    profile = db.get_user_profile(db_path, user_id)
    if profile and profile.apartment:
        return normalize_apartment(profile.apartment)
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT apartment_label FROM apartment_members
            WHERE user_id = ? AND status = ?
            ORDER BY joined_at DESC LIMIT 1
            """,
            (user_id, MEMBER_ACTIVE),
        ).fetchone()
    return normalize_apartment(row["apartment_label"]) if row else None


def membership_status(db_path: Path, user_id: int) -> str | None:
    apartment = apartment_for_user(db_path, user_id)
    if not apartment:
        with db.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT status FROM apartment_members
                WHERE user_id = ? AND status = ?
                ORDER BY requested_at DESC LIMIT 1
                """,
                (user_id, MEMBER_PENDING),
            ).fetchone()
        return row["status"] if row else None
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT status FROM apartment_members
            WHERE apartment_label = ? AND user_id = ?
            """,
            (apartment, user_id),
        ).fetchone()
    return row["status"] if row else MEMBER_ACTIVE


def chat_id_for_apartment(db_path: Path, apartment: str | None) -> int:
    label = normalize_apartment(apartment)
    if not label:
        return DEFAULT_CHAT_ID
    return get_or_create_apartment_chat(db_path, label)


def chat_id_for_user(db_path: Path, user_id: int | None) -> int:
    if user_id is None:
        return DEFAULT_CHAT_ID
    return chat_id_for_apartment(db_path, apartment_for_user(db_path, user_id))


def apartment_payload(db_path: Path, apartment: str) -> dict:
    label = normalize_apartment(apartment)
    if not label:
        return {"apartment": None, "members": []}
    join_code = ensure_apartment_join_code(db_path, label)
    chat_id = chat_id_for_apartment(db_path, label)
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT created_by_user_id, created_at FROM apartments WHERE label = ?",
            (label,),
        ).fetchone()
    payload = members_payload(db_path, label)
    payload.update(
        {
            "apartment": label,
            "join_code": join_code,
            "chat_id": chat_id,
            "created_by_user_id": row["created_by_user_id"] if row else None,
            "created_at": row["created_at"] if row else None,
        }
    )
    return payload


def members_payload(db_path: Path, apartment: str) -> dict:
    label = normalize_apartment(apartment)
    if not label:
        return {"members": [], "pending": []}
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT m.user_id, m.role, m.status, m.requested_at, m.joined_at,
                   u.display_name
            FROM apartment_members m
            LEFT JOIN users u ON u.telegram_user_id = m.user_id
            WHERE m.apartment_label = ?
            ORDER BY m.status DESC, m.role ASC, m.joined_at ASC
            """,
            (label,),
        ).fetchall()
    members = []
    pending = []
    for row in rows:
        item = {
            "user_id": row["user_id"],
            "display_name": row["display_name"] or f"User {row['user_id']}",
            "role": row["role"],
            "status": row["status"],
            "requested_at": row["requested_at"],
            "joined_at": row["joined_at"],
        }
        if row["status"] == MEMBER_PENDING:
            pending.append(item)
        elif row["status"] == MEMBER_ACTIVE:
            members.append(item)
    return {"members": members, "pending": pending, "apartment": label, "pending_count": len(pending)}


def leave_apartment(db_path: Path, user_id: int) -> dict:
    """Member leaves apartment; owners must transfer ownership first."""
    apartment = apartment_for_user(db_path, user_id)
    if not apartment:
        raise ValueError("You are not in an apartment")
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT role FROM apartment_members
            WHERE apartment_label = ? AND user_id = ? AND status = ?
            """,
            (apartment, user_id, MEMBER_ACTIVE),
        ).fetchone()
        if not row:
            raise ValueError("Active membership not found")
        if row["role"] == ROLE_OWNER:
            others = conn.execute(
                """
                SELECT COUNT(*) AS c FROM apartment_members
                WHERE apartment_label = ? AND status = ? AND user_id != ?
                """,
                (apartment, MEMBER_ACTIVE, user_id),
            ).fetchone()["c"]
            if others > 0:
                raise ValueError("Transfer ownership before leaving (remove other members first)")
        conn.execute(
            """
            UPDATE apartment_members SET status = ?
            WHERE apartment_label = ? AND user_id = ?
            """,
            (MEMBER_REMOVED, apartment, user_id),
        )
    db.update_user_profile(db_path, user_id, apartment="")
    return {"left": apartment, "apartment": None}


def regenerate_join_code(db_path: Path, apartment: str, *, owner_user_id: int) -> dict:
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    if not _user_can_manage_members(db_path, label, owner_user_id):
        raise ValueError("Only apartment owners can regenerate the join code")
    with db.connect(db_path) as conn:
        code = _unique_join_code(conn)
        conn.execute(
            "UPDATE apartments SET join_code = ? WHERE label = ?",
            (code, label),
        )
    return apartment_payload(db_path, label)


def pending_count_for_owner(db_path: Path, user_id: int) -> int:
    apartment = apartment_for_user(db_path, user_id)
    if not apartment or not _user_can_manage_members(db_path, apartment, user_id):
        return 0
    payload = members_payload(db_path, apartment)
    return int(payload.get("pending_count", 0))


def init_households(db_path: Path) -> None:
    """Run after schema migration — backfill join codes and memberships."""
    backfill_apartment_memberships(db_path)
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT label FROM apartments WHERE join_code IS NULL OR join_code = ''"
        ).fetchall()
    for row in rows:
        ensure_apartment_join_code(db_path, row["label"])
