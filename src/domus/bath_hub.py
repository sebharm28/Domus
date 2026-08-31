"""Bath hub data — cleaning checklist, towels, medicine cabinet."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from domus import db
from domus.meal_plan_views import calendar_week_bounds

CLEANING_ITEMS = (
    ("mirror", "Mirror"),
    ("sink", "Sink & tap"),
    ("toilet", "Toilet"),
    ("shower", "Shower / tub"),
    ("floor", "Floor"),
)

DEFAULT_TOWELS = ("Hand towel", "Bath towel", "Floor mat")
TOWEL_WASH_THRESHOLD = 4


@dataclass(frozen=True)
class BathTowel:
    id: int
    label: str
    use_count: int
    last_washed_at: str | None
    updated_at: str


@dataclass(frozen=True)
class BathMedicine:
    id: int
    name: str
    expiry_date: str | None
    quantity_note: str | None
    created_at: str
    updated_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _week_start(today: date | None = None) -> str:
    start, _ = calendar_week_bounds(0, today)
    return start.isoformat()


def cleaning_payload(db_path: Path, apartment: str, today: date | None = None) -> dict:
    week = _week_start(today)
    done_map: dict[str, tuple[str, str]] = {}
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT item_key, done_at, done_by FROM bath_cleaning_done
            WHERE apartment = ? AND week_start = ?
            """,
            (apartment, week),
        ).fetchall()
    for row in rows:
        done_map[row["item_key"]] = (row["done_at"], row["done_by"])

    items = []
    for key, label in CLEANING_ITEMS:
        done = done_map.get(key)
        items.append(
            {
                "key": key,
                "label": label,
                "done": done is not None,
                "done_at": done[0] if done else None,
                "done_by": done[1] if done else None,
            }
        )
    return {"week_start": week, "items": items}


def toggle_cleaning_item(
    db_path: Path,
    apartment: str,
    item_key: str,
    *,
    done_by: str,
    today: date | None = None,
) -> dict:
    week = _week_start(today)
    valid_keys = {k for k, _ in CLEANING_ITEMS}
    if item_key not in valid_keys:
        raise ValueError("Unknown cleaning item")
    with db.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id FROM bath_cleaning_done
            WHERE apartment = ? AND item_key = ? AND week_start = ?
            """,
            (apartment, item_key, week),
        ).fetchone()
        if row:
            conn.execute("DELETE FROM bath_cleaning_done WHERE id = ?", (row["id"],))
        else:
            conn.execute(
                """
                INSERT INTO bath_cleaning_done
                    (apartment, item_key, week_start, done_at, done_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (apartment, item_key, week, _now_iso(), done_by),
            )
    return cleaning_payload(db_path, apartment, today)


def _ensure_towels(db_path: Path, apartment: str) -> None:
    now = _now_iso()
    with db.connect(db_path) as conn:
        for label in DEFAULT_TOWELS:
            conn.execute(
                """
                INSERT INTO bath_towels (apartment, label, use_count, last_washed_at, updated_at)
                VALUES (?, ?, 0, NULL, ?)
                ON CONFLICT(apartment, label) DO NOTHING
                """,
                (apartment, label, now),
            )


def towels_payload(db_path: Path, apartment: str) -> dict:
    _ensure_towels(db_path, apartment)
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM bath_towels WHERE apartment = ?
            ORDER BY id ASC
            """,
            (apartment,),
        ).fetchall()
    towels = []
    for row in rows:
        use_count = int(row["use_count"])
        towels.append(
            {
                "id": int(row["id"]),
                "label": row["label"],
                "use_count": use_count,
                "last_washed_at": row["last_washed_at"],
                "needs_wash": use_count >= TOWEL_WASH_THRESHOLD,
                "last_washed_label": _format_date(row["last_washed_at"]),
            }
        )
    return {"towels": towels, "wash_threshold": TOWEL_WASH_THRESHOLD}


def log_towel_use(db_path: Path, apartment: str, label: str) -> dict:
    _ensure_towels(db_path, apartment)
    now = _now_iso()
    with db.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE bath_towels
            SET use_count = use_count + 1, updated_at = ?
            WHERE apartment = ? AND label = ?
            """,
            (now, apartment, label),
        )
    return towels_payload(db_path, apartment)


def log_towel_washed(db_path: Path, apartment: str, label: str) -> dict:
    _ensure_towels(db_path, apartment)
    now = _now_iso()
    with db.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE bath_towels
            SET use_count = 0, last_washed_at = ?, updated_at = ?
            WHERE apartment = ? AND label = ?
            """,
            (now, now, apartment, label),
        )
    return towels_payload(db_path, apartment)


def medicine_payload(db_path: Path, apartment: str) -> dict:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM bath_medicine WHERE apartment = ?
            ORDER BY expiry_date IS NULL, expiry_date ASC, name ASC
            """,
            (apartment,),
        ).fetchall()
    items = []
    today = date.today()
    for row in rows:
        expiry = row["expiry_date"]
        status = "ok"
        if expiry:
            try:
                exp_day = date.fromisoformat(expiry)
                if exp_day < today:
                    status = "expired"
                elif (exp_day - today).days <= 30:
                    status = "soon"
            except ValueError:
                pass
        items.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "expiry_date": expiry,
                "quantity_note": row["quantity_note"],
                "status": status,
            }
        )
    return {"items": items}


def add_medicine(
    db_path: Path,
    apartment: str,
    name: str,
    *,
    expiry_date: str | None = None,
    quantity_note: str | None = None,
) -> dict:
    now = _now_iso()
    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO bath_medicine
                (apartment, name, expiry_date, quantity_note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (apartment, name.strip(), expiry_date, quantity_note, now, now),
        )
    return medicine_payload(db_path, apartment)


def delete_medicine(db_path: Path, item_id: int) -> bool:
    with db.connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM bath_medicine WHERE id = ?", (item_id,))
        return cursor.rowcount > 0


def _format_date(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except (TypeError, ValueError):
        return iso[:10]
