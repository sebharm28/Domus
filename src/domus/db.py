import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Todo:
    id: int
    text: str
    created_by: str
    done: bool
    due_date: str | None


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_by TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                due_date TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                dish TEXT NOT NULL,
                ingredients TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                paid_by TEXT NOT NULL,
                category TEXT,
                date TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                recurrence TEXT,
                next_due TEXT
            );
            """
        )


def _row_to_todo(row: sqlite3.Row) -> Todo:
    return Todo(
        id=row["id"],
        text=row["text"],
        created_by=row["created_by"],
        done=bool(row["done"]),
        due_date=row["due_date"],
    )


def add_todo(db_path: Path, text: str, created_by: str) -> Todo:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO todos (text, created_by, created_at) VALUES (?, ?, ?)",
            (text.strip(), created_by, now),
        )
        todo_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_todo(row)


def list_open_todos(db_path: Path) -> list[Todo]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM todos WHERE done = 0 ORDER BY id ASC"
        ).fetchall()
    return [_row_to_todo(row) for row in rows]


def complete_todo(db_path: Path, item_text: str) -> Todo | None:
    normalized = item_text.strip().lower()
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM todos WHERE done = 0 ORDER BY id ASC"
        ).fetchall()
        match = next(
            (row for row in rows if normalized in row["text"].lower()),
            None,
        )
        if match is None:
            return None
        conn.execute("UPDATE todos SET done = 1 WHERE id = ?", (match["id"],))
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (match["id"],)).fetchone()
    return _row_to_todo(row)


def remove_todo(db_path: Path, item_text: str) -> Todo | None:
    normalized = item_text.strip().lower()
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM todos WHERE done = 0 ORDER BY id ASC"
        ).fetchall()
        match = next(
            (row for row in rows if normalized in row["text"].lower()),
            None,
        )
        if match is None:
            return None
        conn.execute("DELETE FROM todos WHERE id = ?", (match["id"],))
    return _row_to_todo(match)
