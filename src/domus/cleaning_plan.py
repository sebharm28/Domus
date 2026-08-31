"""Shared-apartment cleaning plan — chores, assignments, who did what."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from domus import db

DEFAULT_CHORES: tuple[tuple[str, str, int], ...] = (
    ("kitchen", "Kitchen counters & dishes", 3),
    ("vacuum", "Vacuum / sweep common areas", 7),
    ("trash", "Take out trash & recycling", 3),
    ("bathroom", "Bathroom deep clean", 7),
    ("laundry", "Shared laundry", 7),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except (TypeError, ValueError):
        return None


def _ensure_chores(db_path: Path, apartment: str) -> None:
    with db.connect(db_path) as conn:
        for sort_order, (key, label, interval) in enumerate(DEFAULT_CHORES):
            conn.execute(
                """
                INSERT INTO apartment_cleaning_chores
                    (apartment, chore_key, label, interval_days, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(apartment, chore_key) DO NOTHING
                """,
                (apartment, key, label, interval, sort_order, _now_iso()),
            )


def cleaning_plan_payload(db_path: Path, apartment: str) -> dict:
    _ensure_chores(db_path, apartment)
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.chore_key, c.label, c.interval_days, c.assigned_to_user_id,
                   u.display_name AS assigned_name
            FROM apartment_cleaning_chores c
            LEFT JOIN users u ON u.telegram_user_id = c.assigned_to_user_id
            WHERE c.apartment = ?
            ORDER BY c.sort_order ASC, c.id ASC
            """,
            (apartment,),
        ).fetchall()
    chores: list[dict] = []
    for row in rows:
        last = _last_log(db_path, int(row["id"]))
        days = _days_since(last["done_at"]) if last else None
        interval = int(row["interval_days"])
        overdue = days is None or days >= interval
        chores.append(
            {
                "id": int(row["id"]),
                "key": row["chore_key"],
                "label": row["label"],
                "interval_days": interval,
                "assigned_to_user_id": row["assigned_to_user_id"],
                "assigned_to_name": row["assigned_name"],
                "last_done_at": last["done_at"] if last else None,
                "last_done_by": last["done_by_name"] if last else None,
                "days_since": days,
                "overdue": overdue,
            }
        )
    return {"apartment": apartment, "chores": chores}


def _last_log(db_path: Path, chore_id: int) -> dict | None:
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT done_at, done_by_name FROM apartment_cleaning_log
            WHERE chore_id = ?
            ORDER BY done_at DESC LIMIT 1
            """,
            (chore_id,),
        ).fetchone()
    if not row:
        return None
    return {"done_at": row["done_at"], "done_by_name": row["done_by_name"]}


def mark_chore_done(
    db_path: Path,
    apartment: str,
    chore_id: int,
    *,
    done_by_user_id: int | None,
    done_by_name: str,
) -> dict:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM apartment_cleaning_chores WHERE id = ? AND apartment = ?",
            (chore_id, apartment),
        ).fetchone()
        if not row:
            raise ValueError("Chore not found")
        conn.execute(
            """
            INSERT INTO apartment_cleaning_log
                (chore_id, apartment, done_at, done_by_user_id, done_by_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chore_id, apartment, _now_iso(), done_by_user_id, done_by_name),
        )
    return cleaning_plan_payload(db_path, apartment)


def add_chore(
    db_path: Path,
    apartment: str,
    label: str,
    *,
    interval_days: int = 7,
) -> dict:
    cleaned = label.strip()
    if not cleaned:
        raise ValueError("Label required")
    key = cleaned.lower().replace(" ", "_")[:40]
    now = _now_iso()
    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO apartment_cleaning_chores
                (apartment, chore_key, label, interval_days, sort_order, created_at)
            VALUES (?, ?, ?, ?, 99, ?)
            ON CONFLICT(apartment, chore_key) DO UPDATE SET
                label = excluded.label,
                interval_days = excluded.interval_days
            """,
            (apartment, key, cleaned, interval_days, now),
        )
    return cleaning_plan_payload(db_path, apartment)


def assign_chore(
    db_path: Path,
    apartment: str,
    chore_id: int,
    assigned_to_user_id: int | None,
) -> dict:
    with db.connect(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE apartment_cleaning_chores
            SET assigned_to_user_id = ?
            WHERE id = ? AND apartment = ?
            """,
            (assigned_to_user_id, chore_id, apartment),
        )
        if cursor.rowcount == 0:
            raise ValueError("Chore not found")
    return cleaning_plan_payload(db_path, apartment)
