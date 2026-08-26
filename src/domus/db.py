import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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
    quantity: int | None = None
    apartment: str | None = None
    created_by_user_id: int | None = None
    assigned_to_user_id: int | None = None
    completed_by_user_id: int | None = None
    completed_at: str | None = None


@dataclass(frozen=True)
class ConversationTurn:
    id: int
    chat_id: int
    user_id: int | None
    role: str
    text: str
    intent_json: str | None
    created_at: str


@dataclass(frozen=True)
class MemoryFact:
    id: int
    user_id: int | None
    fact_key: str
    fact_value: str
    source: str | None
    updated_at: str


@dataclass(frozen=True)
class CompletionStat:
    display_name: str
    count: int
    samples: list[str]


@dataclass(frozen=True)
class Reminder:
    id: int
    text: str
    recurrence: str
    next_due: str
    created_by: str


@dataclass(frozen=True)
class UserProfile:
    telegram_user_id: int
    display_name: str
    username: str | None
    apartment: str | None
    diet: str | None
    allergies: str | None
    dislikes: str | None
    likes: str | None
    updated_at: str


@dataclass(frozen=True)
class ChatContext:
    chat_id: int
    last_todo_id: int | None
    last_intent: str | None
    last_item: str | None
    updated_at: str


@dataclass(frozen=True)
class OneShotReminder:
    id: int
    text: str
    fire_at: str
    chat_id: int
    created_by: str
    sent: bool


@dataclass(frozen=True)
class ChatLastAction:
    chat_id: int
    action: str
    payload: str
    updated_at: str


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
    if "quantity" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN quantity INTEGER")
        quantity_prefix = re.compile(r"^(\d+)\s+(.+)$")
        rows = conn.execute(
            "SELECT id, text FROM todos WHERE category = 'shopping'"
        ).fetchall()
        for row in rows:
            match = quantity_prefix.match(row["text"].strip())
            if match:
                conn.execute(
                    "UPDATE todos SET quantity = ?, text = ? WHERE id = ?",
                    (int(match.group(1)), match.group(2).strip(), row["id"]),
                )


def _migrate_reminders(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(reminders)")}
    if "created_by" not in columns:
        conn.execute("ALTER TABLE reminders ADD COLUMN created_by TEXT NOT NULL DEFAULT 'unknown'")


def _migrate_wave2(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_user_id INTEGER PRIMARY KEY,
            display_name TEXT NOT NULL,
            username TEXT,
            apartment TEXT,
            diet TEXT,
            allergies TEXT,
            dislikes TEXT,
            likes TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_context (
            chat_id INTEGER PRIMARY KEY,
            last_todo_id INTEGER,
            last_intent TEXT,
            last_item TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "likes" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN likes TEXT")
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(todos)")}
    if "created_by_user_id" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN created_by_user_id INTEGER")
    if "apartment" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN apartment TEXT")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS one_shot_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            fire_at TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS chat_last_action (
            chat_id INTEGER PRIMARY KEY,
            action TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )


def _migrate_wave3(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(todos)")}
    if "assigned_to_user_id" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN assigned_to_user_id INTEGER")
    if "completed_by_user_id" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN completed_by_user_id INTEGER")
    if "completed_at" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN completed_at TEXT")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversation_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            intent_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            fact_key TEXT NOT NULL,
            fact_value TEXT NOT NULL,
            source TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, fact_key)
        );
        """
    )


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
                quantity INTEGER,
                apartment TEXT,
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
                recurrence TEXT NOT NULL,
                next_due TEXT NOT NULL,
                created_by TEXT NOT NULL DEFAULT 'unknown'
            );

            CREATE TABLE IF NOT EXISTS notification_chats (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                subscribed_at TEXT NOT NULL
            );
            """
        )
        _migrate_todos(conn)
        _migrate_reminders(conn)
        _migrate_wave2(conn)
        _migrate_wave3(conn)


def _row_to_todo(row: sqlite3.Row) -> Todo:
    quantity = None
    if "quantity" in row.keys() and row["quantity"] is not None:
        quantity = int(row["quantity"])
    return Todo(
        id=row["id"],
        text=row["text"],
        created_by=row["created_by"],
        done=bool(row["done"]),
        due_date=row["due_date"],
        category=row["category"] if "category" in row.keys() else "general",
        reminder_sent=bool(row["reminder_sent"]) if "reminder_sent" in row.keys() else False,
        created_at=row["created_at"],
        quantity=quantity,
    apartment=row["apartment"] if "apartment" in row.keys() else None,
    created_by_user_id=row["created_by_user_id"] if "created_by_user_id" in row.keys() else None,
    assigned_to_user_id=row["assigned_to_user_id"] if "assigned_to_user_id" in row.keys() else None,
    completed_by_user_id=row["completed_by_user_id"] if "completed_by_user_id" in row.keys() else None,
    completed_at=row["completed_at"] if "completed_at" in row.keys() else None,
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
    quantity: int | None = None,
    created_by_user_id: int | None = None,
    apartment: str | None = None,
    assigned_to_user_id: int | None = None,
) -> Todo:
    if category == "shopping":
        due_date = None
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO todos (
                text, created_by, due_date, category, quantity,
                created_by_user_id, apartment, assigned_to_user_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                text.strip(),
                created_by,
                due_date,
                category,
                quantity,
                created_by_user_id,
                apartment,
                assigned_to_user_id,
                now,
            ),
        )
        todo_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_todo(row)


def list_open_todos(
    db_path: Path,
    category: str | None = None,
    apartment: str | None = None,
) -> list[Todo]:
    query = "SELECT * FROM todos WHERE done = 0"
    params: list[str] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if apartment:
        query += " AND LOWER(apartment) = LOWER(?)"
        params.append(apartment)
    query += " ORDER BY due_date IS NULL, due_date ASC, id ASC"
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_todo(row) for row in rows]


def list_todos_due_on(db_path: Path, day: date) -> list[Todo]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM todos
            WHERE done = 0 AND due_date = ?
            ORDER BY category ASC, id ASC
            """,
            (day.isoformat(),),
        ).fetchall()
    return [_row_to_todo(row) for row in rows]


def list_overdue_todos(db_path: Path, today: date | None = None) -> list[Todo]:
    today = today or date.today()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM todos
            WHERE done = 0
              AND due_date IS NOT NULL
              AND due_date < ?
            ORDER BY due_date ASC, id ASC
            """,
            (today.isoformat(),),
        ).fetchall()
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


def set_todo_done(
    db_path: Path,
    todo_id: int,
    done: bool = True,
    *,
    completed_by_user_id: int | None = None,
) -> Todo | None:
    """Mark a todo done/undone by id (used by direct UI check-off toggles)."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if row is None:
            return None
        if done:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE todos
                SET done = 1,
                    completed_by_user_id = COALESCE(?, completed_by_user_id),
                    completed_at = COALESCE(completed_at, ?)
                WHERE id = ?
                """,
                (completed_by_user_id, now, todo_id),
            )
        else:
            conn.execute(
                """
                UPDATE todos SET done = 0, completed_by_user_id = NULL, completed_at = NULL
                WHERE id = ?
                """,
                (todo_id,),
            )
        updated = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_todo(updated)


def remove_todo(db_path: Path, item_text: str) -> Todo | None:
    with connect(db_path) as conn:
        match = _find_open_todo(conn, item_text)
        if match is None:
            return None
        conn.execute("DELETE FROM todos WHERE id = ?", (match["id"],))
    return _row_to_todo(match)


def delete_todo_by_id(db_path: Path, todo_id: int) -> Todo | None:
    """Delete a todo by id (used by direct UI remove actions)."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    return _row_to_todo(row)


def get_open_todo(db_path: Path, todo_id: int) -> Todo | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM todos WHERE id = ? AND done = 0",
            (todo_id,),
        ).fetchone()
    return _row_to_todo(row) if row else None


def get_latest_open_todo(db_path: Path) -> Todo | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM todos
            WHERE done = 0
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    return _row_to_todo(row) if row else None


def get_latest_open_todo_without_due(db_path: Path) -> Todo | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM todos
            WHERE done = 0 AND due_date IS NULL
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    return _row_to_todo(row) if row else None


def update_todo(
    db_path: Path,
    todo_id: int,
    *,
    due_date: str | None = None,
    text: str | None = None,
    quantity: int | None = None,
    category: str | None = None,
) -> Todo:
    fields: list[str] = []
    params: list[str | int] = []
    if due_date is not None:
        fields.append("due_date = ?")
        params.append(due_date)
        fields.append("reminder_sent = 0")
    if text is not None:
        fields.append("text = ?")
        params.append(text.strip())
    if quantity is not None:
        fields.append("quantity = ?")
        params.append(quantity)
    if category is not None:
        fields.append("category = ?")
        params.append(category)
    if not fields:
        raise ValueError("Nothing to update")

    params.append(todo_id)
    with connect(db_path) as conn:
        conn.execute(
            f"UPDATE todos SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_todo(row)


def find_open_shopping_match(db_path: Path, item_text: str) -> Todo | None:
    from domus.shopping import shopping_item_name

    normalized = item_text.strip().lower()
    for todo in list_open_todos(db_path, category="shopping"):
        existing = shopping_item_name(todo).lower()
        if normalized == existing or normalized in existing or existing in normalized:
            return todo
    return None


def find_open_todos_partial(db_path: Path, item_text: str) -> list[Todo]:
    normalized = item_text.strip().lower()
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM todos WHERE done = 0 ORDER BY id DESC"
        ).fetchall()
    return [
        _row_to_todo(row)
        for row in rows
        if normalized in row["text"].lower() or row["text"].lower() in normalized
    ]


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


def mark_todo_reminded(db_path: Path, todo_id: int) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE todos SET reminder_sent = 1 WHERE id = ?", (todo_id,))


def clear_shopping_list(db_path: Path) -> int:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM todos WHERE category = 'shopping' AND done = 0"
        )
        return cursor.rowcount


def clear_all_todos(db_path: Path) -> int:
    with connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM todos WHERE done = 0")
        return cursor.rowcount


def remove_todo_by_id(db_path: Path, todo_id: int) -> Todo | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM todos WHERE id = ? AND done = 0",
            (todo_id,),
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    return _row_to_todo(row)


def complete_todo_by_id(
    db_path: Path,
    todo_id: int,
    *,
    completed_by_user_id: int | None = None,
) -> Todo | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM todos WHERE id = ? AND done = 0",
            (todo_id,),
        ).fetchone()
        if row is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            UPDATE todos
            SET done = 1,
                completed_by_user_id = COALESCE(?, completed_by_user_id),
                completed_at = COALESCE(completed_at, ?)
            WHERE id = ?
            """,
            (completed_by_user_id, now, todo_id),
        )
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_todo(row)


def _row_to_user(row: sqlite3.Row) -> UserProfile:
    return UserProfile(
        telegram_user_id=row["telegram_user_id"],
        display_name=row["display_name"],
        username=row["username"],
        apartment=row["apartment"],
        diet=row["diet"],
        allergies=row["allergies"],
        dislikes=row["dislikes"],
        likes=row["likes"],
        updated_at=row["updated_at"],
    )


def upsert_user_profile(
    db_path: Path,
    telegram_user_id: int,
    display_name: str,
    *,
    username: str | None = None,
) -> UserProfile:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_user_id, display_name, username, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                display_name = excluded.display_name,
                username = COALESCE(excluded.username, users.username),
                updated_at = excluded.updated_at
            """,
            (telegram_user_id, display_name.strip(), username, now),
        )
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    return _row_to_user(row)


def get_user_profile(db_path: Path, telegram_user_id: int) -> UserProfile | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    return _row_to_user(row) if row else None


def list_user_profiles(db_path: Path) -> list[UserProfile]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY display_name ASC").fetchall()
    return [_row_to_user(row) for row in rows]


def update_user_profile(
    db_path: Path,
    telegram_user_id: int,
    *,
    apartment: str | None = None,
    diet: str | None = None,
    allergies: str | None = None,
    dislikes: str | None = None,
    likes: str | None = None,
) -> UserProfile:
    fields: list[str] = []
    params: list[str | int] = []
    for column, value in (
        ("apartment", apartment),
        ("diet", diet),
        ("allergies", allergies),
        ("dislikes", dislikes),
        ("likes", likes),
    ):
        if value is not None:
            fields.append(f"{column} = ?")
            params.append(value.strip())
    if not fields:
        raise ValueError("Nothing to update")

    now = datetime.now(timezone.utc).isoformat()
    fields.append("updated_at = ?")
    params.extend([now, telegram_user_id])
    with connect(db_path) as conn:
        conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE telegram_user_id = ?",
            params,
        )
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"User {telegram_user_id} not found")
    return _row_to_user(row)


def append_user_profile_list(
    db_path: Path,
    telegram_user_id: int,
    field: str,
    value: str,
) -> UserProfile:
    allowed = {"allergies", "dislikes", "likes"}
    if field not in allowed:
        raise ValueError(f"Unsupported profile list field: {field}")

    profile = get_user_profile(db_path, telegram_user_id)
    if profile is None:
        raise ValueError("Profile not found")

    existing = getattr(profile, field) or ""
    items = [item.strip() for item in existing.split(",") if item.strip()]
    normalized = value.strip()
    if normalized.lower() not in {item.lower() for item in items}:
        items.append(normalized)
    return update_user_profile(db_path, telegram_user_id, **{field: ", ".join(items)})


def restore_todo_due_state(
    db_path: Path,
    todo_id: int,
    *,
    due_date: str | None,
    reminder_sent: bool,
) -> Todo:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE todos SET due_date = ?, reminder_sent = ? WHERE id = ?",
            (due_date, int(reminder_sent), todo_id),
        )
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if row is None:
        raise ValueError(f"Todo {todo_id} not found")
    return _row_to_todo(row)


def delete_todo(db_path: Path, todo_id: int) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))


def restore_todo(db_path: Path, snapshot: dict) -> Todo:
    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM todos WHERE id = ?",
            (snapshot["id"],),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE todos
                SET done = ?, due_date = ?, category = ?, reminder_sent = ?,
                    quantity = ?, apartment = ?, text = ?
                WHERE id = ?
                """,
                (
                    int(snapshot["done"]),
                    snapshot["due_date"],
                    snapshot["category"],
                    int(snapshot["reminder_sent"]),
                    snapshot.get("quantity"),
                    snapshot.get("apartment"),
                    snapshot["text"],
                    snapshot["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO todos (
                    id, text, created_by, done, due_date, category,
                    reminder_sent, quantity, apartment, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot["id"],
                    snapshot["text"],
                    snapshot["created_by"],
                    int(snapshot["done"]),
                    snapshot["due_date"],
                    snapshot["category"],
                    int(snapshot["reminder_sent"]),
                    snapshot.get("quantity"),
                    snapshot.get("apartment"),
                    snapshot["created_at"],
                ),
            )
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (snapshot["id"],)).fetchone()
    return _row_to_todo(row)


def save_last_action(
    db_path: Path,
    chat_id: int,
    action: str,
    payload: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chat_last_action (chat_id, action, payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                action = excluded.action,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (chat_id, action, payload, now),
        )


def get_last_action(db_path: Path, chat_id: int) -> ChatLastAction | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM chat_last_action WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    if row is None:
        return None
    return ChatLastAction(
        chat_id=row["chat_id"],
        action=row["action"],
        payload=row["payload"],
        updated_at=row["updated_at"],
    )


def clear_last_action(db_path: Path, chat_id: int) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM chat_last_action WHERE chat_id = ?", (chat_id,))


def _row_to_chat_context(row: sqlite3.Row) -> ChatContext:
    return ChatContext(
        chat_id=row["chat_id"],
        last_todo_id=row["last_todo_id"],
        last_intent=row["last_intent"],
        last_item=row["last_item"],
        updated_at=row["updated_at"],
    )


def get_chat_context(db_path: Path, chat_id: int) -> ChatContext | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM chat_context WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return _row_to_chat_context(row) if row else None


def update_chat_context(
    db_path: Path,
    chat_id: int,
    *,
    last_todo_id: int | None = None,
    last_intent: str | None = None,
    last_item: str | None = None,
    clear_todo: bool = False,
) -> ChatContext:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_chat_context(db_path, chat_id)
    todo_id = None if clear_todo else last_todo_id
    if todo_id is None and not clear_todo and existing:
        todo_id = existing.last_todo_id
    intent = last_intent if last_intent is not None else (existing.last_intent if existing else None)
    item = last_item if last_item is not None else (existing.last_item if existing else None)

    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chat_context (chat_id, last_todo_id, last_intent, last_item, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                last_todo_id = excluded.last_todo_id,
                last_intent = excluded.last_intent,
                last_item = excluded.last_item,
                updated_at = excluded.updated_at
            """,
            (chat_id, todo_id, intent, item, now),
        )
        row = conn.execute(
            "SELECT * FROM chat_context WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return _row_to_chat_context(row)


def add_one_shot_reminder(
    db_path: Path,
    text: str,
    fire_at: datetime,
    chat_id: int,
    created_by: str,
) -> OneShotReminder:
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO one_shot_reminders (text, fire_at, chat_id, created_by, sent)
            VALUES (?, ?, ?, ?, 0)
            """,
            (text.strip(), fire_at.isoformat(), chat_id, created_by),
        )
        reminder_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM one_shot_reminders WHERE id = ?",
            (reminder_id,),
        ).fetchone()
    return _row_to_one_shot(row)


def list_due_one_shot_reminders(
    db_path: Path,
    now: datetime | None = None,
) -> list[OneShotReminder]:
    now = now or datetime.now(timezone.utc)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM one_shot_reminders
            WHERE sent = 0 AND fire_at <= ?
            ORDER BY fire_at ASC, id ASC
            """,
            (now.isoformat(),),
        ).fetchall()
    return [_row_to_one_shot(row) for row in rows]


def mark_one_shot_sent(db_path: Path, reminder_id: int) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE one_shot_reminders SET sent = 1 WHERE id = ?",
            (reminder_id,),
        )


def list_pending_one_shot_reminders(
    db_path: Path,
    chat_id: int | None = None,
) -> list["OneShotReminder"]:
    now = datetime.now(timezone.utc).isoformat()
    query = """
        SELECT * FROM one_shot_reminders
        WHERE sent = 0 AND fire_at > ?
    """
    params: list[str | int] = [now]
    if chat_id is not None:
        query += " AND chat_id = ?"
        params.append(chat_id)
    query += " ORDER BY fire_at ASC, id ASC"
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_one_shot(row) for row in rows]


def list_recent_one_shot_reminders(
    db_path: Path,
    chat_id: int,
    *,
    within_hours: int = 24,
) -> list["OneShotReminder"]:
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=within_hours)).isoformat()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM one_shot_reminders
            WHERE chat_id = ? AND sent = 1 AND fire_at >= ?
            ORDER BY fire_at DESC, id DESC
            """,
            (chat_id, cutoff),
        ).fetchall()
    return [_row_to_one_shot(row) for row in rows]


def cancel_one_shot_reminder(
    db_path: Path,
    chat_id: int,
    *,
    text_hint: str | None = None,
) -> OneShotReminder | None:
    pending = list_pending_one_shot_reminders(db_path, chat_id=chat_id)
    if not pending:
        return None
    target = pending[-1]
    if text_hint:
        hint = text_hint.strip().lower()
        matched = next(
            (reminder for reminder in pending if hint in reminder.text.lower()),
            None,
        )
        if matched is not None:
            target = matched
    with connect(db_path) as conn:
        conn.execute("DELETE FROM one_shot_reminders WHERE id = ?", (target.id,))
    return target


def update_one_shot_fire_at(
    db_path: Path,
    reminder_id: int,
    fire_at: datetime,
) -> OneShotReminder:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE one_shot_reminders SET fire_at = ? WHERE id = ?",
            (fire_at.isoformat(), reminder_id),
        )
        row = conn.execute(
            "SELECT * FROM one_shot_reminders WHERE id = ?",
            (reminder_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"One-shot reminder {reminder_id} not found")
    return _row_to_one_shot(row)


def set_reminder_next_due(
    db_path: Path,
    reminder_id: int,
    next_due: date,
) -> Reminder:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE reminders SET next_due = ? WHERE id = ?",
            (next_due.isoformat(), reminder_id),
        )
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    if row is None:
        raise ValueError(f"Reminder {reminder_id} not found")
    return _row_to_reminder(row)


def restore_one_shot_reminder(
    db_path: Path,
    snapshot: dict,
) -> OneShotReminder:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO one_shot_reminders (id, text, fire_at, chat_id, created_by, sent)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                snapshot["id"],
                snapshot["text"],
                snapshot["fire_at"],
                snapshot["chat_id"],
                snapshot["created_by"],
            ),
        )
        row = conn.execute(
            "SELECT * FROM one_shot_reminders WHERE id = ?",
            (snapshot["id"],),
        ).fetchone()
    return _row_to_one_shot(row)


def _row_to_one_shot(row: sqlite3.Row) -> OneShotReminder:
    return OneShotReminder(
        id=row["id"],
        text=row["text"],
        fire_at=row["fire_at"],
        chat_id=row["chat_id"],
        created_by=row["created_by"],
        sent=bool(row["sent"]),
    )


def _row_to_reminder(row: sqlite3.Row) -> Reminder:
    return Reminder(
        id=row["id"],
        text=row["text"],
        recurrence=row["recurrence"],
        next_due=row["next_due"],
        created_by=row["created_by"] if "created_by" in row.keys() else "unknown",
    )


def add_reminder(
    db_path: Path,
    text: str,
    recurrence: str,
    created_by: str,
    *,
    next_due: date | None = None,
) -> Reminder:
    from domus.recurrence import first_due_date

    due = next_due or first_due_date(recurrence)
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders (text, recurrence, next_due, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (text.strip(), recurrence, due.isoformat(), created_by),
        )
        reminder_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return _row_to_reminder(row)


def list_reminders(db_path: Path) -> list[Reminder]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reminders ORDER BY next_due ASC, id ASC"
        ).fetchall()
    return [_row_to_reminder(row) for row in rows]


def list_due_recurring_reminders(db_path: Path, today: date | None = None) -> list[Reminder]:
    today = today or date.today()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM reminders
            WHERE next_due <= ?
            ORDER BY next_due ASC, id ASC
            """,
            (today.isoformat(),),
        ).fetchall()
    return [_row_to_reminder(row) for row in rows]


def advance_reminder(db_path: Path, reminder_id: int) -> Reminder:
    from domus.recurrence import next_due_date

    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        if row is None:
            raise ValueError(f"Reminder {reminder_id} not found")
        reminder = _row_to_reminder(row)
        current_due = date.fromisoformat(reminder.next_due)
        new_due = next_due_date(reminder.recurrence, current_due)
        conn.execute(
            "UPDATE reminders SET next_due = ? WHERE id = ?",
            (new_due.isoformat(), reminder_id),
        )
        updated = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return _row_to_reminder(updated)


def _find_reminder(conn: sqlite3.Connection, item_text: str) -> sqlite3.Row | None:
    normalized = item_text.strip().lower()
    rows = conn.execute("SELECT * FROM reminders ORDER BY id ASC").fetchall()
    return next((row for row in rows if normalized in row["text"].lower()), None)


def remove_reminder(db_path: Path, item_text: str) -> Reminder | None:
    with connect(db_path) as conn:
        match = _find_reminder(conn, item_text)
        if match is None:
            return None
        conn.execute("DELETE FROM reminders WHERE id = ?", (match["id"],))
    return _row_to_reminder(match)


def resolve_user_id_by_name(
    db_path: Path,
    name: str,
    *,
    current_user_id: int | None = None,
) -> int | None:
    normalized = name.strip().lower()
    if normalized in {"me", "myself", "mine"}:
        return current_user_id
    for profile in list_user_profiles(db_path):
        candidates = {
            profile.display_name.lower(),
            (profile.username or "").lower(),
        }
        if normalized in candidates or normalized in profile.display_name.lower():
            return profile.telegram_user_id
    return None


def get_user_display_name(db_path: Path, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    profile = get_user_profile(db_path, user_id)
    return profile.display_name if profile else None


def record_conversation_turn(
    db_path: Path,
    *,
    chat_id: int,
    user_id: int | None,
    role: str,
    text: str,
    intent_json: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO conversation_turns (chat_id, user_id, role, text, intent_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chat_id, user_id, role, text.strip(), intent_json, now),
        )


def list_recent_turns(
    db_path: Path,
    *,
    chat_id: int,
    limit: int = 5,
) -> list[ConversationTurn]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM conversation_turns
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()
    return [
        ConversationTurn(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            role=row["role"],
            text=row["text"],
            intent_json=row["intent_json"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def upsert_memory_fact(
    db_path: Path,
    *,
    user_id: int,
    fact_key: str,
    fact_value: str,
    source: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO memory_facts (user_id, fact_key, fact_value, source, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, fact_key) DO UPDATE SET
                fact_value = excluded.fact_value,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (user_id, fact_key.strip(), fact_value.strip(), source, now),
        )


def list_memory_facts(
    db_path: Path,
    *,
    user_id: int | None = None,
    limit: int = 20,
) -> list[MemoryFact]:
    query = "SELECT * FROM memory_facts"
    params: list[int] = []
    if user_id is not None:
        query += " WHERE user_id = ?"
        params.append(user_id)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        MemoryFact(
            id=row["id"],
            user_id=row["user_id"],
            fact_key=row["fact_key"],
            fact_value=row["fact_value"],
            source=row["source"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def list_completion_stats(db_path: Path, *, days: int = 7) -> list[CompletionStat]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                COALESCE(u.display_name, 'Unknown') AS display_name,
                COUNT(*) AS count,
                GROUP_CONCAT(t.text, '||') AS samples
            FROM todos t
            LEFT JOIN users u ON t.completed_by_user_id = u.telegram_user_id
            WHERE t.done = 1
              AND t.completed_at IS NOT NULL
              AND t.completed_at >= ?
            GROUP BY t.completed_by_user_id, display_name
            ORDER BY count DESC, display_name ASC
            """,
            (since,),
        ).fetchall()
    stats: list[CompletionStat] = []
    for row in rows:
        samples = [part for part in (row["samples"] or "").split("||") if part][:5]
        stats.append(
            CompletionStat(
                display_name=row["display_name"],
                count=int(row["count"]),
                samples=samples,
            )
        )
    return stats


def list_held_reminders(db_path: Path, today: date | None = None) -> list[Todo]:
    """Open todos due on or before today that still have not been reminded."""
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

