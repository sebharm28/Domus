from pathlib import Path

from domus import db
from domus.intents import Intent


def format_todo_list(todos: list[db.Todo]) -> str:
    if not todos:
        return "The list is empty."
    lines = ["Shopping list:"]
    lines.extend(f"• {todo.text}" for todo in todos)
    return "\n".join(lines)


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
        "• we need butter\n"
        "• we don't need paper any longer\n"
        "• what's on the list?"
    )


def handle_intent(intent: Intent, db_path: Path, created_by: str) -> str:
    if intent.name == "greeting":
        return "Hi! I'm here — need anything added to the list or checked off?"

    if intent.name == "thanks":
        return "You're welcome! Happy to help."

    if intent.name == "help":
        return (
            "I can manage your shared shopping list:\n"
            "• Domus, add milk to the list\n"
            "• Domus, what's on the list?\n"
            "• Domus, check off milk\n"
            "• Domus, remove milk"
        )

    if intent.name == "list_todos":
        return format_todo_list(db.list_open_todos(db_path))

    if intent.name == "add_todo":
        if not intent.item:
            return "What should I add to the list?"
        todo = db.add_todo(db_path, intent.item, created_by)
        return f'Added "{todo.text}" to the list.'

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
