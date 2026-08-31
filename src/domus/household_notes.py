"""Shared kitchen / household clipboard notes (per apartment)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from domus import db

NOTE_COLORS = ("yellow", "pink", "blue", "green", "mint", "rosa")


@dataclass(frozen=True)
class KitchenNote:
    id: int
    apartment: str
    author_user_id: int | None
    author_name: str
    body: str
    color: str
    created_at: str
    updated_at: str


def _row_to_note(row) -> KitchenNote:
    return KitchenNote(
        id=int(row["id"]),
        apartment=row["apartment"],
        author_user_id=row["author_user_id"],
        author_name=row["author_name"],
        body=row["body"],
        color=row["color"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def note_preview(body: str, max_len: int = 90) -> str:
    text = re.sub(r"\*\*|__|\*|_|`", "", body)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def list_kitchen_notes(db_path: Path, apartment: str) -> list[KitchenNote]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM kitchen_notes
            WHERE apartment = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (apartment,),
        ).fetchall()
    return [_row_to_note(row) for row in rows]


def create_kitchen_note(
    db_path: Path,
    *,
    apartment: str,
    author_user_id: int | None,
    author_name: str,
    body: str,
    color: str = "yellow",
) -> KitchenNote:
    if color not in NOTE_COLORS:
        color = "yellow"
    now = datetime.now(timezone.utc).isoformat()
    with db.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO kitchen_notes
                (apartment, author_user_id, author_name, body, color, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (apartment, author_user_id, author_name, body.strip(), color, now, now),
        )
        row = conn.execute(
            "SELECT * FROM kitchen_notes WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _row_to_note(row)


def update_kitchen_note(
    db_path: Path,
    note_id: int,
    *,
    body: str | None = None,
    color: str | None = None,
) -> KitchenNote | None:
    fields: list[str] = []
    params: list[str | int] = []
    if body is not None:
        fields.append("body = ?")
        params.append(body.strip())
    if color is not None:
        if color not in NOTE_COLORS:
            color = "yellow"
        fields.append("color = ?")
        params.append(color)
    if not fields:
        return get_kitchen_note(db_path, note_id)
    now = datetime.now(timezone.utc).isoformat()
    fields.append("updated_at = ?")
    params.append(now)
    params.append(note_id)
    with db.connect(db_path) as conn:
        conn.execute(
            f"UPDATE kitchen_notes SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        row = conn.execute("SELECT * FROM kitchen_notes WHERE id = ?", (note_id,)).fetchone()
    return _row_to_note(row) if row else None


def get_kitchen_note(db_path: Path, note_id: int) -> KitchenNote | None:
    with db.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM kitchen_notes WHERE id = ?", (note_id,)).fetchone()
    return _row_to_note(row) if row else None


def delete_kitchen_note(db_path: Path, note_id: int) -> bool:
    with db.connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM kitchen_notes WHERE id = ?", (note_id,))
        return cursor.rowcount > 0


def kitchen_notes_payload(db_path: Path, apartment: str | None) -> dict:
    if not apartment:
        return {"notes": [], "colors": list(NOTE_COLORS)}
    notes = list_kitchen_notes(db_path, apartment)
    return {
        "apartment": apartment,
        "colors": list(NOTE_COLORS),
        "notes": [
            {
                "id": n.id,
                "author_user_id": n.author_user_id,
                "author_name": n.author_name,
                "body": n.body,
                "preview": note_preview(n.body),
                "color": n.color,
                "created_at": n.created_at,
                "updated_at": n.updated_at,
                "date_label": _format_note_date(n.updated_at),
            }
            for n in notes
        ],
    }


def _format_note_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except (TypeError, ValueError):
        return iso[:10] if iso else ""
