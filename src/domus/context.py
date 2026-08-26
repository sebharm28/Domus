from pathlib import Path

from domus import db
from domus.intents import Intent


def resolve_context_todo_id(db_path: Path, chat_id: int) -> int | None:
    context = db.get_chat_context(db_path, chat_id)
    if context is None or context.last_todo_id is None:
        return None
    todo = db.get_open_todo(db_path, context.last_todo_id)
    return todo.id if todo else None


def record_intent_context(
    db_path: Path,
    chat_id: int,
    intent: Intent,
    *,
    todo_id: int | None = None,
    clear_todo: bool = False,
) -> None:
    db.update_chat_context(
        db_path,
        chat_id,
        last_intent=intent.name,
        last_item=intent.item or intent.new_item,
        last_todo_id=todo_id,
        clear_todo=clear_todo,
    )
