from pathlib import Path

from domus import db
from domus.dates import format_due_date
from domus.intents import Intent


def format_todo_list(todos: list[db.Todo]) -> str:
    if not todos:
        return "The list is empty."

    grouped: dict[str, list[db.Todo]] = {}
    for todo in todos:
        grouped.setdefault(todo.category, []).append(todo)

    lines = ["Open tasks:"]
    for category in sorted(grouped):
        lines.append(f"\n{category.title()}:")
        for todo in grouped[category]:
            due = format_due_date(todo.due_date)
            lines.append(f"• {todo.text} — due: {due}")
    return "\n".join(lines)


def _format_added(todo: db.Todo) -> str:
    due = format_due_date(todo.due_date)
    return f'Added "{todo.text}" ({todo.category}, due: {due}).'


def handle_intents(intents: list[Intent], db_path: Path, created_by: str) -> str:
    ordered = sorted(
        intents,
        key=lambda intent: 1 if intent.name == "list_todos" else 0,
    )
    replies: list[str] = []
    for intent in ordered:
        if intent.name == "unknown":
            continue
        reply = handle_intent(intent, db_path, created_by)
        if reply and reply not in replies:
            replies.append(reply)

    if replies:
        return "\n".join(replies)

    return (
        "I didn't understand that yet. Try:\n"
        "• add milk to the list\n"
        "• add pay rent by friday category admin\n"
        "• show me the shopping list\n"
        "• remove milk from the list"
    )


def handle_intent(intent: Intent, db_path: Path, created_by: str) -> str:
    if intent.name == "greeting":
        return "Hi! What should I add, remove, or remind you about?"

    if intent.name == "thanks":
        return "You're welcome — happy to help."

    if intent.name == "help":
        return (
            "I can manage shared tasks and shopping items:\n"
            "• add milk to the list\n"
            "• add pay rent by friday category admin\n"
            "• show me the shopping list\n"
            "• remove milk from the list\n"
            "• check off milk"
        )

    if intent.name == "list_todos":
        return format_todo_list(db.list_open_todos(db_path))

    if intent.name == "add_todo":
        if not intent.item:
            return "What should I add?"
        todo = db.add_todo(
            db_path,
            intent.item,
            created_by,
            due_date=intent.due_date,
            category=intent.category or "general",
        )
        return _format_added(todo)

    if intent.name == "complete_todo":
        if not intent.item:
            return "Which item should I check off?"
        todo = db.complete_todo(db_path, intent.item)
        if todo is None:
            return f'I could not find an open item matching "{intent.item}".'
        return f'Checked off "{todo.text}".'

    if intent.name == "remove_todo":
        if not intent.item:
            return "Which item should I remove?"
        todo = db.remove_todo(db_path, intent.item)
        if todo is None:
            return f'I could not find an open item matching "{intent.item}".'
        return f'Removed "{todo.text}" from the list.'

    return ""
