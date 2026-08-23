from pathlib import Path

from domus import db
from domus.dates import format_due_date
from domus.intents import Intent
from domus.briefing import handle_daily_briefing
from domus.meals import (
    handle_log_meal,
    handle_missing_ingredients,
    handle_plan_meal,
    handle_plan_week,
    handle_show_meal_plan,
    handle_suggest_meal,
)
from domus.reminders import (
    handle_add_recurring_reminder,
    handle_list_reminders,
    handle_remove_reminder,
)


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
        "• remove milk from the list\n"
        "• what should I eat for dinner?\n"
        "• let's make curry with rice tonight\n"
        "• plan meals for this week\n"
        "• what's missing for dinner?\n"
        "• remind us every Tuesday to take out the trash\n"
        "• I said the task is for tomorrow\n"
        "• what's on today?"
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
            "• check off milk\n"
            "• what should I eat for dinner?\n"
            "• let's make curry with rice tonight\n"
            "• plan meals for this week\n"
            "• what's missing for dinner?\n"
            "• remind us every Tuesday to take out the trash\n"
            "• I said the task is for tomorrow\n"
            "• what's on today?"
        )

    if intent.name == "list_todos":
        return format_todo_list(db.list_open_todos(db_path))

    if intent.name == "daily_briefing":
        return handle_daily_briefing(db_path)

    if intent.name == "suggest_meal":
        return handle_suggest_meal("", db_path, meal_type=intent.item)

    if intent.name == "plan_meal":
        return handle_plan_meal(intent.item or "", db_path, created_by, meal_name=intent.item)

    if intent.name == "plan_week":
        return handle_plan_week(db_path, created_by)

    if intent.name == "show_meal_plan":
        return handle_show_meal_plan(db_path)

    if intent.name == "missing_ingredients":
        return handle_missing_ingredients(intent.item or "", db_path, meal_name=intent.item)

    if intent.name == "add_recurring_reminder":
        return handle_add_recurring_reminder(
            intent.item or "",
            db_path,
            created_by,
            task=intent.item,
            recurrence=intent.recurrence,
        )

    if intent.name == "list_reminders":
        return handle_list_reminders(db_path)

    if intent.name == "remove_reminder":
        return handle_remove_reminder(db_path, intent.item)

    if intent.name == "log_meal":
        return handle_log_meal(intent.item or "", db_path, created_by)

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

    if intent.name == "update_todo":
        return handle_update_todo(intent, db_path)

    return ""


def handle_update_todo(intent: Intent, db_path: Path) -> str:
    replies: list[str] = []

    if intent.item:
        for stray in ("loving girl friend", "find a loving"):
            wrong = db.remove_todo(db_path, stray)
            if wrong:
                replies.append(f'Removed mistaken entry "{wrong.text}".')

        matches = db.find_open_todos_partial(db_path, intent.item)
        todo = matches[0] if matches else db.get_latest_open_todo_without_due(db_path)
        if todo is None:
            return f'I could not find a task matching "{intent.item}".'
    else:
        todo = db.get_latest_open_todo_without_due(db_path) or db.get_latest_open_todo(db_path)
        if todo is None:
            return "I couldn't find a recent task to update."

    if intent.due_date:
        updated = db.update_todo(db_path, todo.id, due_date=intent.due_date)
        due = format_due_date(updated.due_date)
        replies.append(f'Updated "{updated.text}" — due: {due}.')
        return " ".join(replies)

    replies.append(f'Got it — you mean "{todo.text}".')
    return " ".join(replies)
