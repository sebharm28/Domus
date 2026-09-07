"""Household account auth — sessions, invite links, OTP, export/import."""

from __future__ import annotations

import hashlib
import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path

from domus import db
from domus.households import (
    MEMBER_ACTIVE,
    MEMBER_REMOVED,
    ROLE_MEMBER,
    ROLE_OWNER,
    apartment_payload,
    create_apartment_with_owner,
    ensure_apartment_join_code,
    get_or_create_apartment_chat,
    members_payload,
    normalize_apartment,
)

INVITE_TOKEN_LENGTH = 32
OTP_LENGTH = 6
OTP_TTL_MINUTES = 15
SESSION_TOKEN_LENGTH = 48
EXPORT_VERSION = 1

DEFAULT_SEED_HOUSEHOLD = "Karl-Marx-Allee 5"
DEFAULT_SEED_ADMIN = "Sebastian"
DEFAULT_SEED_PASSWORD = "test1234"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, expected = stored.split("$", 1)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return secrets.compare_digest(digest, expected)


def generate_invite_token() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(INVITE_TOKEN_LENGTH))


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_LENGTH)


def generate_otp_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))


def _unique_invite_token(conn) -> str:
    for _ in range(32):
        token = generate_invite_token()
        row = conn.execute(
            "SELECT 1 FROM apartments WHERE invite_token = ?",
            (token,),
        ).fetchone()
        if not row:
            return token
    raise RuntimeError("Could not allocate invite token")


def migrate_household_auth_schema(db_path: Path) -> None:
    with db.connect(db_path) as conn:
        apt_columns = {row["name"] for row in conn.execute("PRAGMA table_info(apartments)")}
        if "invite_token" not in apt_columns:
            conn.execute("ALTER TABLE apartments ADD COLUMN invite_token TEXT")
        if "password_hash" not in apt_columns:
            conn.execute("ALTER TABLE apartments ADD COLUMN password_hash TEXT")
        if "household_name" not in apt_columns:
            conn.execute("ALTER TABLE apartments ADD COLUMN household_name TEXT")

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS device_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                apartment_label TEXT NOT NULL,
                device_label TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS household_otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                apartment_label TEXT NOT NULL,
                code TEXT NOT NULL,
                purpose TEXT NOT NULL DEFAULT 'join',
                expires_at TEXT NOT NULL,
                created_by_user_id INTEGER,
                used_at TEXT,
                used_by_user_id INTEGER
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_apartments_invite_token
                ON apartments(invite_token) WHERE invite_token IS NOT NULL;
            """
        )

        rows = conn.execute(
            "SELECT label FROM apartments WHERE invite_token IS NULL OR invite_token = ''"
        ).fetchall()
        for row in rows:
            token = _unique_invite_token(conn)
            conn.execute(
                "UPDATE apartments SET invite_token = ? WHERE label = ?",
                (token, row["label"]),
            )


def create_device_session(
    db_path: Path,
    user_id: int,
    apartment: str,
    *,
    device_label: str | None = None,
) -> str:
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    token = generate_session_token()
    now = _now_iso()
    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO device_sessions (token, user_id, apartment_label, device_label, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token, user_id, label, device_label, now, now),
        )
    return token


def resolve_session(db_path: Path, token: str | None) -> dict | None:
    if not token:
        return None
    now = _now_iso()
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT s.user_id, s.apartment_label, u.display_name
            FROM device_sessions s
            LEFT JOIN users u ON u.telegram_user_id = s.user_id
            WHERE s.token = ?
            """,
            (token.strip(),),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE device_sessions SET last_seen_at = ? WHERE token = ?",
            (now, token.strip()),
        )
    from domus.households import chat_id_for_apartment

    apartment = normalize_apartment(row["apartment_label"])
    return {
        "user_id": int(row["user_id"]),
        "apartment": apartment,
        "chat_id": chat_id_for_apartment(db_path, apartment),
        "display_name": row["display_name"] or f"User {row['user_id']}",
        "session_token": token.strip(),
    }


def revoke_sessions_for_member(db_path: Path, user_id: int, apartment: str | None = None) -> None:
    label = normalize_apartment(apartment)
    with db.connect(db_path) as conn:
        if label:
            conn.execute(
                "DELETE FROM device_sessions WHERE user_id = ? AND apartment_label = ?",
                (user_id, label),
            )
        else:
            conn.execute("DELETE FROM device_sessions WHERE user_id = ?", (user_id,))


def list_entity_sessions(db_path: Path, tokens: list[str]) -> list[dict]:
    """Resolve multiple session tokens for entity switcher."""
    entities = []
    seen: set[tuple[str, int]] = set()
    for token in tokens:
        sess = resolve_session(db_path, token)
        if not sess:
            continue
        key = (sess["apartment"] or "", sess["user_id"])
        if key in seen:
            continue
        seen.add(key)
        with db.connect(db_path) as conn:
            apt = conn.execute(
                "SELECT household_name, invite_token FROM apartments WHERE label = ?",
                (sess["apartment"],),
            ).fetchone()
        entities.append(
            {
                "session_token": sess["session_token"],
                "user_id": sess["user_id"],
                "display_name": sess["display_name"],
                "apartment": sess["apartment"],
                "chat_id": sess["chat_id"],
                "household_name": (apt["household_name"] if apt else None) or sess["apartment"],
                "invite_token": apt["invite_token"] if apt else None,
            }
        )
    return entities


def _apartment_by_invite_token(conn, invite_token: str) -> str | None:
    row = conn.execute(
        "SELECT label FROM apartments WHERE invite_token = ?",
        (invite_token.strip().lower(),),
    ).fetchone()
    return normalize_apartment(row["label"]) if row else None


def _verify_access(db_path: Path, apartment: str, *, password: str | None, otp: str | None) -> None:
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Unknown household")
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT password_hash FROM apartments WHERE label = ?",
            (label,),
        ).fetchone()
        password_hash = row["password_hash"] if row else None

    if otp:
        code = otp.strip()
        with db.connect(db_path) as conn:
            otp_row = conn.execute(
                """
                SELECT id FROM household_otps
                WHERE apartment_label = ? AND code = ? AND used_at IS NULL
                  AND expires_at > ?
                ORDER BY id DESC LIMIT 1
                """,
                (label, code, _now_iso()),
            ).fetchone()
            if otp_row:
                conn.execute(
                    "UPDATE household_otps SET used_at = ? WHERE id = ?",
                    (_now_iso(), otp_row["id"]),
                )
                return
        raise ValueError("Invalid or expired code")

    if password and verify_password(password, password_hash):
        return
    if password_hash is None and password:
        raise ValueError("Household password not set — use OTP from admin or ask admin to set a password")
    raise ValueError("Invalid household password or OTP required")


def create_household_account(
    db_path: Path,
    household_name: str,
    admin_name: str,
    password: str,
    *,
    user_id: int | None = None,
) -> dict:
    """Create household + admin entity + session."""
    name = household_name.strip()
    if not name:
        raise ValueError("Household name required")
    if not admin_name.strip():
        raise ValueError("Your name required")
    if len(password) < 4:
        raise ValueError("Password must be at least 4 characters")

    if user_id is None:
        profiles = db.list_user_profiles(db_path)
        user_id = max((p.telegram_user_id for p in profiles), default=0) + 1

    label = normalize_apartment(name)
    with db.connect(db_path) as conn:
        existing = conn.execute(
            "SELECT label FROM apartments WHERE label = ? OR household_name = ?",
            (label, name),
        ).fetchone()
    if existing:
        raise ValueError(
            "A household with this name already exists — use Join or Log in instead."
        )

    apt = create_apartment_with_owner(
        db_path,
        name,
        user_id,
        owner_name=admin_name.strip(),
    )
    token = generate_invite_token()
    pw_hash = hash_password(password)
    now = _now_iso()
    with db.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE apartments
            SET invite_token = ?, password_hash = ?, household_name = ?
            WHERE label = ?
            """,
            (token, pw_hash, name, name),
        )
    session_token = create_device_session(db_path, user_id, name)
    return {
        "session_token": session_token,
        "invite_token": token,
        "household": apartment_payload(db_path, name),
        "profile": {
            "id": user_id,
            "display_name": admin_name.strip(),
            "apartment": name,
        },
    }


def join_household_new_member(
    db_path: Path,
    invite_token: str,
    display_name: str,
    *,
    password: str | None = None,
    otp: str | None = None,
    user_id: int | None = None,
) -> dict:
    """Join as a new member entity after password/OTP verification."""
    with db.connect(db_path) as conn:
        label = _apartment_by_invite_token(conn, invite_token)
    if not label:
        raise ValueError("Invalid invite link")
    _verify_access(db_path, label, password=password, otp=otp)

    if user_id is None:
        profiles = db.list_user_profiles(db_path)
        user_id = max((p.telegram_user_id for p in profiles), default=0) + 1

    db.upsert_user_profile(db_path, user_id, display_name.strip())
    now = _now_iso()
    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO apartment_members
                (apartment_label, user_id, role, status, requested_at, joined_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(apartment_label, user_id) DO UPDATE SET
                status = excluded.status,
                joined_at = excluded.joined_at
            """,
            (label, user_id, ROLE_MEMBER, MEMBER_ACTIVE, now, now),
        )
    db.update_user_profile(db_path, user_id, apartment=label)
    session_token = create_device_session(db_path, user_id, label)
    return {
        "session_token": session_token,
        "profile": {
            "id": user_id,
            "display_name": display_name.strip(),
            "apartment": label,
        },
        "household": apartment_payload(db_path, label),
    }


def login_existing_entity(
    db_path: Path,
    invite_token: str,
    user_id: int,
    *,
    password: str | None = None,
    otp: str | None = None,
) -> dict:
    """Log in as an existing member on a new device."""
    with db.connect(db_path) as conn:
        label = _apartment_by_invite_token(conn, invite_token)
    if not label:
        raise ValueError("Invalid invite link")
    _verify_access(db_path, label, password=password, otp=otp)

    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT status FROM apartment_members
            WHERE apartment_label = ? AND user_id = ? AND status = ?
            """,
            (label, user_id, MEMBER_ACTIVE),
        ).fetchone()
    if not row:
        raise ValueError("Member not found in this household")

    profile = db.get_user_profile(db_path, user_id)
    if not profile:
        raise ValueError("Member profile missing")

    session_token = create_device_session(db_path, user_id, label)
    return {
        "session_token": session_token,
        "profile": {
            "id": user_id,
            "display_name": profile.display_name,
            "apartment": label,
        },
        "household": apartment_payload(db_path, label),
    }


def generate_household_otp(
    db_path: Path,
    apartment: str,
    *,
    created_by_user_id: int,
    purpose: str = "join",
) -> dict:
    from domus.households import _user_can_manage_members

    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    if not _user_can_manage_members(db_path, label, created_by_user_id):
        member_row = None
        with db.connect(db_path) as conn:
            member_row = conn.execute(
                """
                SELECT 1 FROM apartment_members
                WHERE apartment_label = ? AND user_id = ? AND status = ?
                """,
                (label, created_by_user_id, MEMBER_ACTIVE),
            ).fetchone()
        if not member_row:
            raise ValueError("Only household members can generate codes")

    code = generate_otp_code()
    expires = (_now() + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO household_otps
                (apartment_label, code, purpose, expires_at, created_by_user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (label, code, purpose, expires, created_by_user_id),
        )
    return {"code": code, "expires_at": expires, "ttl_minutes": OTP_TTL_MINUTES}


def set_household_password(
    db_path: Path,
    apartment: str,
    password: str,
    *,
    by_user_id: int,
) -> None:
    from domus.households import _user_can_manage_members

    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    if not _user_can_manage_members(db_path, label, by_user_id):
        raise ValueError("Only admin can change household password")
    if len(password) < 4:
        raise ValueError("Password must be at least 4 characters")
    pw_hash = hash_password(password)
    with db.connect(db_path) as conn:
        conn.execute(
            "UPDATE apartments SET password_hash = ? WHERE label = ?",
            (pw_hash, label),
        )


def regenerate_invite_token(db_path: Path, apartment: str, *, owner_user_id: int) -> dict:
    from domus.households import _user_can_manage_members

    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    if not _user_can_manage_members(db_path, label, owner_user_id):
        raise ValueError("Only admin can regenerate invite link")
    token = generate_invite_token()
    with db.connect(db_path) as conn:
        for _ in range(32):
            clash = conn.execute(
                "SELECT 1 FROM apartments WHERE invite_token = ? AND label != ?",
                (token, label),
            ).fetchone()
            if not clash:
                break
            token = generate_invite_token()
        conn.execute(
            "UPDATE apartments SET invite_token = ? WHERE label = ?",
            (token, label),
        )
    payload = apartment_payload(db_path, label)
    payload["invite_token"] = token
    return payload


def transfer_admin(
    db_path: Path,
    apartment: str,
    *,
    from_user_id: int,
    to_user_id: int,
) -> dict:
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    if from_user_id == to_user_id:
        raise ValueError("Cannot transfer admin to yourself")
    with db.connect(db_path) as conn:
        owner = conn.execute(
            """
            SELECT role FROM apartment_members
            WHERE apartment_label = ? AND user_id = ? AND status = ?
            """,
            (label, from_user_id, MEMBER_ACTIVE),
        ).fetchone()
        if not owner or owner["role"] != ROLE_OWNER:
            raise ValueError("Only admin can transfer admin role")
        target = conn.execute(
            """
            SELECT role FROM apartment_members
            WHERE apartment_label = ? AND user_id = ? AND status = ?
            """,
            (label, to_user_id, MEMBER_ACTIVE),
        ).fetchone()
        if not target:
            raise ValueError("Target member not found")
        conn.execute(
            "UPDATE apartment_members SET role = ? WHERE apartment_label = ? AND user_id = ?",
            (ROLE_MEMBER, label, from_user_id),
        )
        conn.execute(
            "UPDATE apartment_members SET role = ? WHERE apartment_label = ? AND user_id = ?",
            (ROLE_OWNER, label, to_user_id),
        )
        conn.execute(
            "UPDATE apartments SET created_by_user_id = ? WHERE label = ?",
            (to_user_id, label),
        )
    return members_payload(db_path, label)


def rename_member(
    db_path: Path,
    apartment: str,
    member_user_id: int,
    new_name: str,
    *,
    by_user_id: int,
) -> dict:
    from domus.households import _user_can_manage_members

    label = normalize_apartment(apartment)
    name = new_name.strip()
    if not label or not name:
        raise ValueError("Name required")
    if member_user_id != by_user_id and not _user_can_manage_members(
        db_path, label, by_user_id
    ):
        raise ValueError("Only admin can rename other members")
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT status FROM apartment_members
            WHERE apartment_label = ? AND user_id = ? AND status = ?
            """,
            (label, member_user_id, MEMBER_ACTIVE),
        ).fetchone()
        if not row:
            raise ValueError("Member not found")
    db.update_user_profile(db_path, member_user_id, display_name=name)
    return members_payload(db_path, label)


def remove_member(
    db_path: Path,
    apartment: str,
    member_user_id: int,
    *,
    by_user_id: int,
) -> dict:
    from domus.households import kick_apartment_member

    payload = kick_apartment_member(
        db_path,
        apartment,
        member_user_id,
        kicked_by_user_id=by_user_id,
    )
    revoke_sessions_for_member(db_path, member_user_id, apartment)
    return payload


def household_auth_payload(db_path: Path, apartment: str) -> dict:
    label = normalize_apartment(apartment)
    if not label:
        return {}
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT invite_token, household_name, password_hash IS NOT NULL AS has_password
            FROM apartments WHERE label = ?
            """,
            (label,),
        ).fetchone()
    base = apartment_payload(db_path, label)
    if row:
        base["invite_token"] = row["invite_token"]
        base["household_name"] = row["household_name"] or label
        base["has_password"] = bool(row["has_password"])
    return base


def _anonymize_name_map(members: list[dict]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for index, member in enumerate(members, start=1):
        mapping[int(member["user_id"])] = f"Member {index}"
    return mapping


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _rows_for_table(conn, table: str, apartment: str, *, shared_shopping: bool = False) -> list[dict]:
    if not _table_exists(conn, table):
        return []
    if table == "todos":
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM todos WHERE apartment = ? OR (apartment IS NULL AND category = 'shopping')",
                (apartment,),
            ).fetchall()
        ]
    return [
        dict(row)
        for row in conn.execute(
            f"SELECT * FROM {table} WHERE apartment = ?",
            (apartment,),
        ).fetchall()
    ]


def export_household(
    db_path: Path,
    apartment: str,
    *,
    anonymize: bool = False,
    requested_by_user_id: int,
) -> dict:
    label = normalize_apartment(apartment)
    if not label:
        raise ValueError("Apartment required")
    with db.connect(db_path) as conn:
        member_row = conn.execute(
            """
            SELECT 1 FROM apartment_members
            WHERE apartment_label = ? AND user_id = ? AND status = ?
            """,
            (label, requested_by_user_id, MEMBER_ACTIVE),
        ).fetchone()
    if not member_row:
        raise ValueError("Only active members can export household data")

    members = members_payload(db_path, label)["members"]
    name_map = _anonymize_name_map(members) if anonymize else {}

    def anon_name(uid: int | None, fallback: str | None) -> str | None:
        if not anonymize or uid is None:
            return fallback
        return name_map.get(uid, fallback)

    with db.connect(db_path) as conn:
        apt_row = conn.execute(
            "SELECT household_name, chat_id FROM apartments WHERE label = ?",
            (label,),
        ).fetchone()
        todos = _rows_for_table(conn, "todos", label)
        meal_plans = _rows_for_table(conn, "meal_plans", label)
        kitchen_notes = _rows_for_table(conn, "kitchen_notes", label)
        bath_towels = _rows_for_table(conn, "bath_towels", label)
        bath_medicine = _rows_for_table(conn, "bath_medicine", label)
        bath_cleaning = _rows_for_table(conn, "bath_cleaning_done", label)
        cleaning_chores = _rows_for_table(conn, "apartment_cleaning_chores", label)
        cleaning_log = _rows_for_table(conn, "apartment_cleaning_log", label)

    if anonymize:
        for todo in todos:
            uid = todo.get("completed_by_user_id") or todo.get("created_by_user_id")
            if todo.get("created_by") and todo.get("created_by_user_id") in name_map:
                todo["created_by"] = name_map[todo["created_by_user_id"]]
            if todo.get("completed_by_user_id") in name_map:
                pass
            if uid in name_map:
                if todo.get("created_by_user_id") == uid:
                    todo["created_by"] = name_map[uid]
        for note in kitchen_notes:
            if note.get("author_user_id") in name_map:
                note["author_name"] = name_map[note["author_user_id"]]
        for entry in bath_cleaning:
            for m in members:
                if entry.get("done_by") == m.get("display_name"):
                    entry["done_by"] = name_map.get(m["user_id"], entry["done_by"])
        for entry in cleaning_log:
            if entry.get("done_by_user_id") in name_map:
                entry["done_by_name"] = name_map[entry["done_by_user_id"]]
        for member in members:
            member["display_name"] = name_map.get(member["user_id"], member["display_name"])

    member_profiles = []
    for member in members:
        profile = db.get_user_profile(db_path, member["user_id"])
        if profile:
            member_profiles.append(
                {
                    "user_id": member["user_id"],
                    "display_name": member["display_name"],
                    "diet": profile.diet,
                    "allergies": profile.allergies,
                    "likes": profile.likes,
                    "dislikes": profile.dislikes,
                }
            )

    return {
        "version": EXPORT_VERSION,
        "exported_at": _now_iso(),
        "anonymized": anonymize,
        "household": {
            "label": label,
            "name": apt_row["household_name"] if apt_row else label,
            "chat_id": apt_row["chat_id"] if apt_row else None,
        },
        "members": member_profiles,
        "todos": todos,
        "meal_plans": meal_plans,
        "kitchen_notes": kitchen_notes,
        "bath_towels": bath_towels,
        "bath_medicine": bath_medicine,
        "bath_cleaning_done": bath_cleaning,
        "cleaning_chores": cleaning_chores,
        "cleaning_log": cleaning_log,
    }


def import_household(
    db_path: Path,
    bundle: dict,
    admin_name: str,
    password: str,
    *,
    new_household_name: str | None = None,
) -> dict:
    if bundle.get("version") != EXPORT_VERSION:
        raise ValueError("Unsupported export version")
    old_label = bundle.get("household", {}).get("label")
    if not old_label:
        raise ValueError("Export missing household label")
    name = (new_household_name or bundle["household"].get("name") or old_label).strip()
    if not name:
        raise ValueError("Household name required")

    result = create_household_account(db_path, name, admin_name, password)
    new_label = name
    id_map: dict[int, int] = {}
    profiles = db.list_user_profiles(db_path)
    next_id = max((p.telegram_user_id for p in profiles), default=0)

    admin_id = result["profile"]["id"]
    old_members = bundle.get("members") or []
    for member in old_members:
        old_id = int(member["user_id"])
        if member.get("display_name") == admin_name:
            id_map[old_id] = admin_id
            pref_updates = {
                k: member.get(k)
                for k in ("diet", "allergies", "likes", "dislikes")
                if member.get(k)
            }
            if pref_updates:
                db.update_user_profile(db_path, admin_id, **pref_updates)
            continue
        next_id += 1
        id_map[old_id] = next_id
        db.upsert_user_profile(
            db_path,
            next_id,
            member.get("display_name") or f"Member {next_id}",
        )
        pref_updates = {
            k: member.get(k)
            for k in ("diet", "allergies", "likes", "dislikes")
            if member.get(k)
        }
        if pref_updates:
            db.update_user_profile(db_path, next_id, **pref_updates)
        now = _now_iso()
        with db.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO apartment_members
                    (apartment_label, user_id, role, status, requested_at, joined_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (new_label, next_id, ROLE_MEMBER, MEMBER_ACTIVE, now, now),
            )
        db.update_user_profile(db_path, next_id, apartment=new_label)

    chat_id = get_or_create_apartment_chat(db_path, new_label)
    with db.connect(db_path) as conn:
        for todo in bundle.get("todos") or []:
            apt = new_label if todo.get("apartment") else None
            conn.execute(
                """
                INSERT INTO todos
                    (text, created_by, done, due_date, category, reminder_sent, quantity,
                     apartment, created_at, created_by_user_id, assigned_to_user_id,
                     completed_by_user_id, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    todo["text"],
                    todo.get("created_by") or "unknown",
                    todo.get("done", 0),
                    todo.get("due_date"),
                    todo.get("category", "general"),
                    todo.get("reminder_sent", 0),
                    todo.get("quantity"),
                    apt,
                    todo.get("created_at") or _now_iso(),
                    id_map.get(todo.get("created_by_user_id"), todo.get("created_by_user_id")),
                    id_map.get(todo.get("assigned_to_user_id"), todo.get("assigned_to_user_id")),
                    id_map.get(todo.get("completed_by_user_id"), todo.get("completed_by_user_id")),
                    todo.get("completed_at"),
                ),
            )
        for row in bundle.get("meal_plans") or []:
            if not _table_exists(conn, "meal_plans"):
                break
            conn.execute(
                """
                INSERT INTO meal_plans (day, dish, ingredients, apartment)
                VALUES (?, ?, ?, ?)
                """,
                (row["day"], row["dish"], row.get("ingredients", "[]"), new_label),
            )
        for row in bundle.get("kitchen_notes") or []:
            conn.execute(
                """
                INSERT INTO kitchen_notes
                    (apartment, author_user_id, author_name, body, color, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_label,
                    id_map.get(row.get("author_user_id"), row.get("author_user_id")),
                    row.get("author_name") or "unknown",
                    row.get("body") or "",
                    row.get("color") or "yellow",
                    row.get("created_at") or _now_iso(),
                    row.get("updated_at") or _now_iso(),
                ),
            )
        for row in bundle.get("bath_towels") or []:
            conn.execute(
                """
                INSERT INTO bath_towels (apartment, label, use_count, last_washed_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(apartment, label) DO UPDATE SET
                    use_count = excluded.use_count,
                    last_washed_at = excluded.last_washed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    new_label,
                    row["label"],
                    row.get("use_count", 0),
                    row.get("last_washed_at"),
                    row.get("updated_at") or _now_iso(),
                ),
            )
        for row in bundle.get("bath_medicine") or []:
            conn.execute(
                """
                INSERT INTO bath_medicine
                    (apartment, name, quantity, expires_on, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    new_label,
                    row["name"],
                    row.get("quantity"),
                    row.get("expires_on"),
                    row.get("notes"),
                    row.get("updated_at") or _now_iso(),
                ),
            )
        for row in bundle.get("bath_cleaning_done") or []:
            conn.execute(
                """
                INSERT OR IGNORE INTO bath_cleaning_done
                    (apartment, item_key, week_start, done_at, done_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_label,
                    row["item_key"],
                    row["week_start"],
                    row.get("done_at") or _now_iso(),
                    row.get("done_by") or "unknown",
                ),
            )
        chore_id_map: dict[int, int] = {}
        for row in bundle.get("cleaning_chores") or []:
            cur = conn.execute(
                """
                INSERT INTO apartment_cleaning_chores
                    (apartment, chore_key, label, interval_days, assigned_to_user_id, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_label,
                    row["chore_key"],
                    row["label"],
                    row.get("interval_days", 7),
                    id_map.get(row.get("assigned_to_user_id"), row.get("assigned_to_user_id")),
                    row.get("sort_order", 0),
                    row.get("created_at") or _now_iso(),
                ),
            )
            chore_id_map[int(row["id"])] = int(cur.lastrowid)
        for row in bundle.get("cleaning_log") or []:
            old_chore_id = row.get("chore_id")
            new_chore_id = chore_id_map.get(old_chore_id, old_chore_id)
            conn.execute(
                """
                INSERT INTO apartment_cleaning_log
                    (chore_id, apartment, done_at, done_by_user_id, done_by_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_chore_id,
                    new_label,
                    row.get("done_at") or _now_iso(),
                    id_map.get(row.get("done_by_user_id"), row.get("done_by_user_id")),
                    row.get("done_by_name") or "unknown",
                ),
            )

    result["imported_from"] = old_label
    result["household"] = apartment_payload(db_path, new_label)
    return result


_USER_ID_REASSIGNMENTS: tuple[tuple[str, str], ...] = (
    ("conversation_turns", "user_id"),
    ("todos", "created_by_user_id"),
    ("todos", "assigned_to_user_id"),
    ("todos", "completed_by_user_id"),
    ("apartments", "created_by_user_id"),
    ("apartment_cleaning_log", "done_by_user_id"),
    ("apartment_cleaning_chores", "assigned_to_user_id"),
    ("kitchen_notes", "author_user_id"),
    ("memory_facts", "user_id"),
    ("household_otps", "created_by_user_id"),
    ("household_otps", "used_by_user_id"),
)


def _reassign_user_id(db_path: Path, from_user_id: int, to_user_id: int) -> None:
    if from_user_id == to_user_id:
        return
    with db.connect(db_path) as conn:
        for table, column in _USER_ID_REASSIGNMENTS:
            conn.execute(
                f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                (to_user_id, from_user_id),
            )


def _delete_user(db_path: Path, user_id: int) -> None:
    with db.connect(db_path) as conn:
        conn.execute("DELETE FROM device_sessions WHERE user_id = ?", (user_id,))
        conn.execute(
            "DELETE FROM apartment_members WHERE user_id = ?",
            (user_id,),
        )
        conn.execute("DELETE FROM users WHERE telegram_user_id = ?", (user_id,))


def _canonical_member_id(db_path: Path, apartment_label: str) -> int | None:
    label = normalize_apartment(apartment_label)
    if not label:
        return None
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT user_id FROM device_sessions
            WHERE apartment_label = ?
            ORDER BY last_seen_at DESC
            LIMIT 1
            """,
            (label,),
        ).fetchone()
        if row:
            return int(row["user_id"])
        row = conn.execute(
            """
            SELECT user_id FROM apartment_members
            WHERE apartment_label = ? AND status = ?
            ORDER BY CASE role WHEN ? THEN 0 ELSE 1 END, user_id DESC
            LIMIT 1
            """,
            (label, MEMBER_ACTIVE, ROLE_OWNER),
        ).fetchone()
    return int(row["user_id"]) if row else None


def consolidate_duplicate_household_members(db_path: Path, apartment_label: str) -> int | None:
    """Merge duplicate member rows for one household onto a single canonical user."""
    label = normalize_apartment(apartment_label)
    if not label:
        return None
    keep_id = _canonical_member_id(db_path, label)
    if keep_id is None:
        return None
    with db.connect(db_path) as conn:
        member_ids = [
            int(row["user_id"])
            for row in conn.execute(
                """
                SELECT user_id FROM apartment_members
                WHERE apartment_label = ? AND status = ?
                """,
                (label, MEMBER_ACTIVE),
            ).fetchall()
        ]
    for user_id in member_ids:
        if user_id == keep_id:
            continue
        _reassign_user_id(db_path, user_id, keep_id)
        _delete_user(db_path, user_id)
    db.update_user_profile(db_path, keep_id, apartment=label)
    with db.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE apartment_members
            SET role = ?, status = ?
            WHERE apartment_label = ? AND user_id = ?
            """,
            (ROLE_OWNER, MEMBER_ACTIVE, label, keep_id),
        )
    return keep_id


def prune_orphan_users(db_path: Path) -> int:
    """Remove profiles that belong to no household."""
    removed = 0
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT u.telegram_user_id
            FROM users u
            LEFT JOIN apartment_members m
              ON m.user_id = u.telegram_user_id AND m.status = ?
            WHERE m.user_id IS NULL
            """,
            (MEMBER_ACTIVE,),
        ).fetchall()
    for row in rows:
        user_id = int(row["telegram_user_id"])
        _delete_user(db_path, user_id)
        removed += 1
    return removed


def init_household_auth(db_path: Path) -> None:
    """Schema migration, invite tokens, optional seed household."""
    migrate_household_auth_schema(db_path)
    profiles = db.list_user_profiles(db_path)
    if not profiles:
        create_household_account(
            db_path,
            DEFAULT_SEED_HOUSEHOLD,
            DEFAULT_SEED_ADMIN,
            DEFAULT_SEED_PASSWORD,
        )
        return

    # Backfill auth on existing households (e.g. Karl-Marx-Allee 5 from v1).
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT label, password_hash, household_name FROM apartments
            WHERE label = ? OR household_name IS NULL
            """,
            (DEFAULT_SEED_HOUSEHOLD,),
        ).fetchall()
        for row in rows:
            label = row["label"]
            if not row["household_name"]:
                conn.execute(
                    "UPDATE apartments SET household_name = ? WHERE label = ?",
                    (label, label),
                )
            if label == DEFAULT_SEED_HOUSEHOLD:
                if not row["password_hash"] or not verify_password(
                    DEFAULT_SEED_PASSWORD, row["password_hash"]
                ):
                    conn.execute(
                        "UPDATE apartments SET password_hash = ? WHERE label = ?",
                        (hash_password(DEFAULT_SEED_PASSWORD), label),
                    )

    consolidate_duplicate_household_members(db_path, DEFAULT_SEED_HOUSEHOLD)
    prune_orphan_users(db_path)
