import json
from datetime import date, datetime
from pathlib import Path

from domus import db


def _todo_snapshot(todo: db.Todo) -> dict:
    return {
        "id": todo.id,
        "text": todo.text,
        "created_by": todo.created_by,
        "done": todo.done,
        "due_date": todo.due_date,
        "category": todo.category,
        "reminder_sent": todo.reminder_sent,
        "created_at": todo.created_at,
        "quantity": todo.quantity,
        "apartment": todo.apartment,
    }


def record_action(
    db_path: Path,
    chat_id: int,
    action: str,
    payload: dict,
) -> None:
    db.save_last_action(db_path, chat_id, action, json.dumps(payload))


def record_add(
    db_path: Path,
    chat_id: int | None,
    todo: db.Todo,
    *,
    merged: bool = False,
    previous_text: str | None = None,
    previous_quantity: int | None = None,
) -> None:
    if chat_id is None:
        return
    payload = {"todo": _todo_snapshot(todo), "merged": merged}
    if merged:
        payload["previous_text"] = previous_text
        payload["previous_quantity"] = previous_quantity
    record_action(db_path, chat_id, "add_todo", payload)


def record_remove(db_path: Path, chat_id: int | None, todo: db.Todo) -> None:
    if chat_id is None:
        return
    record_action(db_path, chat_id, "remove_todo", {"todo": _todo_snapshot(todo)})


def record_complete(db_path: Path, chat_id: int | None, todo: db.Todo) -> None:
    if chat_id is None:
        return
    record_action(db_path, chat_id, "complete_todo", {"todo": _todo_snapshot(todo)})


def record_clear(
    db_path: Path,
    chat_id: int | None,
    action: str,
    todos: list[db.Todo],
) -> None:
    if chat_id is None:
        return
    record_action(
        db_path,
        chat_id,
        action,
        {"todos": [_todo_snapshot(todo) for todo in todos]},
    )


def record_cancel_timer(db_path: Path, chat_id: int | None, reminder: db.OneShotReminder) -> None:
    if chat_id is None:
        return
    record_action(
        db_path,
        chat_id,
        "cancel_timer",
        {
            "id": reminder.id,
            "text": reminder.text,
            "fire_at": reminder.fire_at,
            "chat_id": reminder.chat_id,
            "created_by": reminder.created_by,
        },
    )


def record_snooze(
    db_path: Path,
    chat_id: int | None,
    action: str,
    payload: dict,
) -> None:
    if chat_id is None:
        return
    record_action(db_path, chat_id, action, payload)


def handle_undo(db_path: Path, chat_id: int | None) -> str:
    if chat_id is None:
        return "I couldn't tell which chat to undo in."

    entry = db.get_last_action(db_path, chat_id)
    if entry is None:
        return "Nothing to undo."

    payload = json.loads(entry.payload)
    action = entry.action

    if action == "add_todo":
        data = payload["todo"]
        if payload.get("merged"):
            db.update_todo(
                db_path,
                data["id"],
                text=payload.get("previous_text") or data["text"],
                quantity=payload.get("previous_quantity"),
            )
            db.clear_last_action(db_path, chat_id)
            return "Undid the last shopping update."
        db.delete_todo(db_path, data["id"])
        db.clear_last_action(db_path, chat_id)
        return f'Undid add: removed "{data["text"]}".'

    if action == "remove_todo":
        todo = db.restore_todo(db_path, payload["todo"])
        db.clear_last_action(db_path, chat_id)
        return f'Undid remove: put "{todo.text}" back on the list.'

    if action == "complete_todo":
        todo = db.restore_todo(db_path, payload["todo"])
        db.clear_last_action(db_path, chat_id)
        return f'Undid check-off: reopened "{todo.text}".'

    if action in ("clear_shopping_list", "clear_todos"):
        restored = [db.restore_todo(db_path, item) for item in payload.get("todos", [])]
        db.clear_last_action(db_path, chat_id)
        label = "shopping list" if action == "clear_shopping_list" else "list"
        return f"Undid clear: restored {len(restored)} item(s) to the {label}."

    if action == "cancel_timer":
        db.restore_one_shot_reminder(db_path, payload)
        db.clear_last_action(db_path, chat_id)
        return f'Undid cancel: restored timer "{payload["text"]}".'

    if action == "snooze_todo":
        db.restore_todo_due_state(
            db_path,
            payload["todo_id"],
            due_date=payload["due_date"],
            reminder_sent=bool(payload.get("reminder_sent")),
        )
        db.clear_last_action(db_path, chat_id)
        return "Undid snooze: restored the previous due date."

    if action == "snooze_recurring":
        db.set_reminder_next_due(
            db_path,
            payload["reminder_id"],
            date.fromisoformat(payload["next_due"]),
        )
        db.clear_last_action(db_path, chat_id)
        return "Undid snooze: restored the recurring reminder schedule."

    if action == "snooze_one_shot":
        db.update_one_shot_fire_at(
            db_path,
            payload["reminder_id"],
            datetime.fromisoformat(payload["fire_at"]),
        )
        db.clear_last_action(db_path, chat_id)
        return "Undid snooze: restored the previous timer."

    return "I couldn't undo that action."
