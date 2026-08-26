from pathlib import Path

from domus import db
from domus.intents import Intent

CONTEXT_PRONOUNS = frozenset(
    {
        "that",
        "it",
        "this",
        "the task",
        "the other task",
        "the item",
    }
)


def is_context_pronoun(item: str | None) -> bool:
    if not item:
        return True
    return item.strip().lower() in CONTEXT_PRONOUNS


def resolve_context_todo_id(db_path: Path, chat_id: int) -> int | None:
    context = db.get_chat_context(db_path, chat_id)
    if context is None or context.last_todo_id is None:
        return None
    todo = db.get_open_todo(db_path, context.last_todo_id)
    return todo.id if todo else None


def resolve_action_target(
    db_path: Path,
    chat_id: int | None,
    item: str | None,
) -> db.Todo | None:
    """Resolve a todo for remove/complete when the item is vague or a pronoun."""
    if item and not is_context_pronoun(item):
        matches = db.find_open_todos_partial(db_path, item)
        if matches:
            return matches[0]

    if chat_id is not None:
        context_id = resolve_context_todo_id(db_path, chat_id)
        if context_id is not None:
            todo = db.get_open_todo(db_path, context_id)
            if todo is not None:
                return todo

    return None


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
