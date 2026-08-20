import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Todo:
    id: int
    text: str
    created_by: str
    done: bool
    due_date: str | None
    category: str
    reminder_sent: bool
    created_at: str


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_todos(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(todos)")}
    if "category" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN category TEXT NOT NULL DEFAULT 'shopping'")
    if "reminder_sent" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN reminder_sent INTEGER NOT NULL DEFAULT 0")


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
                category TEXT NOT NULL DEFAULT 'general',
                reminder_sent INTEGER NOT NULL DEFAULT 0,
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

            CREATE TABLE IF NOT EXISTS notification_chats (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                subscribed_at TEXT NOT NULL
            );
            """
        )
        _migrate_todos(conn)


def _row_to_todo(row: sqlite3.Row) -> Todo:
    return Todo(
        id=row["id"],
        text=row["text"],
        created_by=row["created_by"],
        done=bool(row["done"]),
        due_date=row["due_date"],
        category=row["category"] if "category" in row.keys() else "general",
        reminder_sent=bool(row["reminder_sent"]) if "reminder_sent" in row.keys() else False,
        created_at=row["created_at"],
    )


def subscribe_chat(db_path: Path, chat_id: int, title: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO notification_chats (chat_id, title, subscribed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title
            """,
            (chat_id, title, now),
        )


def list_notification_chats(db_path: Path) -> list[int]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT chat_id FROM notification_chats").fetchall()
    return [row["chat_id"] for row in rows]


def add_todo(
    db_path: Path,
    text: str,
    created_by: str,
    *,
    due_date: str | None = None,
    category: str = "general",
) -> Todo:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO todos (text, created_by, due_date, category, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (text.strip(), created_by, due_date, category, now),
        )
        todo_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_todo(row)


def list_open_todos(db_path: Path, category: str | None = None) -> list[Todo]:
    query = "SELECT * FROM todos WHERE done = 0"
    params: list[str] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY due_date IS NULL, due_date ASC, id ASC"
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_todo(row) for row in rows]


def _find_open_todo(conn: sqlite3.Connection, item_text: str) -> sqlite3.Row | None:
    normalized = item_text.strip().lower()
    rows = conn.execute("SELECT * FROM todos WHERE done = 0 ORDER BY id ASC").fetchall()
    return next((row for row in rows if normalized in row["text"].lower()), None)


def complete_todo(db_path: Path, item_text: str) -> Todo | None:
    with connect(db_path) as conn:
        match = _find_open_todo(conn, item_text)
        if match is None:
            return None
        conn.execute("UPDATE todos SET done = 1 WHERE id = ?", (match["id"],))
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (match["id"],)).fetchone()
    return _row_to_todo(row)


def remove_todo(db_path: Path, item_text: str) -> Todo | None:
    with connect(db_path) as conn:
        match = _find_open_todo(conn, item_text)
        if match is None:
            return None
        conn.execute("DELETE FROM todos WHERE id = ?", (match["id"],))
    return _row_to_todo(match)


def list_due_todos_for_reminder(db_path: Path, today: date | None = None) -> list[Todo]:
    today = today or date.today()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM todos
            WHERE done = 0
              AND due_date IS NOT NULL
              AND due_date <= ?
              AND reminder_sent = 0
            ORDER BY due_date ASC, id ASC
            """,
            (today.isoformat(),),
        ).fetchall()
    return [_row_to_todo(row) for row in rows]


def clear_shopping_list(db_path: Path) -> int:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM todos WHERE category = 'shopping' AND done = 0"
        )
        return cursor.rowcount
