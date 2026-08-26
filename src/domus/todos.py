from pathlib import Path

from domus import db
from domus.dates import format_due_date
from domus.intents import Intent
from domus.person_context import format_assignee_label, handle_who_did_what, resolve_assignee_user_id
from domus.shopping import (
    effective_quantity,
    format_shopping_display,
    parse_item_quantity,
)
from domus.briefing import handle_daily_briefing
from domus.context import record_intent_context, resolve_action_target, resolve_context_todo_id, CONTEXT_PRONOUNS, is_context_pronoun
from domus import profiles as profile_handlers
from domus.meals import (
    handle_add_recipe,
    handle_log_meal,
    handle_missing_ingredients,
    handle_plan_meal,
    handle_plan_week,
    handle_show_meal_plan,
    handle_suggest_meal,
)
from domus.reminders import (
    handle_add_recurring_reminder,
    handle_cancel_timer,
    handle_list_reminders,
    handle_remove_reminder,
)
from domus.relative_reminders import handle_add_relative_reminder
from domus.snooze import handle_snooze_reminder
from domus.undo import (
    handle_undo,
    record_add,
    record_clear,
    record_complete,
    record_remove,
)


def format_todo_list(todos: list[db.Todo], db_path: Path | None = None) -> str:
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
            label = format_shopping_display(todo) if todo.category == "shopping" else todo.text
            apt = f" [{todo.apartment}]" if todo.apartment else ""
            assignee = format_assignee_label(db_path, todo.assigned_to_user_id) if db_path else None
            assign = f" → {assignee}" if assignee else ""
            lines.append(f"• {label}{apt}{assign} — due: {due}")
    return "\n".join(lines)


def _format_added(todo: db.Todo, db_path: Path | None = None) -> str:
    due = format_due_date(todo.due_date)
    label = format_shopping_display(todo) if todo.category == "shopping" else todo.text
    apt = f" [{todo.apartment}]" if todo.apartment else ""
    assignee = format_assignee_label(db_path, todo.assigned_to_user_id) if db_path else None
    assign = f", assigned to {assignee}" if assignee else ""
    return f'Added "{label}"{apt} ({todo.category}, due: {due}{assign}).'


def _add_or_merge_todo(
    db_path: Path,
    item: str,
    created_by: str,
    *,
    due_date: str | None,
    category: str,
    created_by_user_id: int | None = None,
    assigned_to_user_id: int | None = None,
    apartment: str | None = None,
    chat_id: int | None = None,
) -> tuple[str, db.Todo | None]:
    item_name, quantity = parse_item_quantity(item)
    add_qty = quantity if quantity is not None else 1
    if category == "shopping":
        due_date = None
    if category == "shopping":
        existing = db.find_open_shopping_match(db_path, item_name)
        if existing:
            previous_text = existing.text
            previous_quantity = effective_quantity(existing)
            new_qty = previous_quantity + add_qty
            updated = db.update_todo(
                db_path,
                existing.id,
                text=item_name,
                quantity=new_qty,
            )
            label = format_shopping_display(updated)
            if chat_id is not None:
                record_add(
                    db_path,
                    chat_id,
                    updated,
                    merged=True,
                    previous_text=previous_text,
                    previous_quantity=previous_quantity,
                )
            return f'Updated to {label} on the shopping list.', updated

    todo = db.add_todo(
        db_path,
        item_name,
        created_by,
        due_date=due_date,
        category=category,
        quantity=add_qty if category == "shopping" else None,
        created_by_user_id=created_by_user_id,
        apartment=apartment,
        assigned_to_user_id=assigned_to_user_id,
    )
    if chat_id is not None:
        record_add(db_path, chat_id, todo)
    return _format_added(todo, db_path), todo


def format_export_list(
    db_path: Path,
    *,
    export_format: str = "text",
    category: str | None = None,
) -> str:
    todos = db.list_open_todos(db_path, category=category)
    if not todos:
        label = f"{category} list" if category else "list"
        return f"The {label} is empty."

    if export_format == "csv":
        lines = ["item,quantity,category"]
        for todo in todos:
            if todo.category == "shopping":
                name, _ = parse_item_quantity(todo.text)
                qty = effective_quantity(todo)
                lines.append(f"{name},{qty},{todo.category}")
            else:
                lines.append(f'"{todo.text}",,{todo.category}')
        return "\n".join(lines)

    grouped: dict[str, list[db.Todo]] = {}
    for todo in todos:
        grouped.setdefault(todo.category, []).append(todo)

    lines = [f"Open items ({len(todos)}):"]
    for cat in sorted(grouped):
        lines.append(f"\n{cat.title()}:")
        for todo in grouped[cat]:
            label = format_shopping_display(todo) if todo.category == "shopping" else todo.text
            due = format_due_date(todo.due_date)
            if todo.due_date:
                lines.append(f"• {label} — due: {due}")
            else:
                lines.append(f"• {label}")
    return "\n".join(lines)


def handle_clear_shopping_list(db_path: Path, chat_id: int | None = None) -> str:
    todos = db.list_open_todos(db_path, category="shopping")
    count = db.clear_shopping_list(db_path)
    if count == 0:
        return "The shopping list is already empty."
    if chat_id is not None and todos:
        record_clear(db_path, chat_id, "clear_shopping_list", todos)
    noun = "item" if count == 1 else "items"
    return f"Cleared {count} {noun} from the shopping list."


def handle_clear_todos(db_path: Path, chat_id: int | None = None) -> str:
    todos = db.list_open_todos(db_path)
    count = db.clear_all_todos(db_path)
    if count == 0:
        return "The list is already empty."
    if chat_id is not None and todos:
        record_clear(db_path, chat_id, "clear_todos", todos)
    noun = "item" if count == 1 else "items"
    return f"Cleared {count} open {noun} from the list."


def handle_intents(
    intents: list[Intent],
    db_path: Path,
    created_by: str,
    *,
    chat_id: int | None = None,
    telegram_user_id: int | None = None,
) -> str:
    ordered = sorted(
        intents,
        key=lambda intent: 1 if intent.name == "list_todos" else 0,
    )
    replies: list[str] = []
    for intent in ordered:
        if intent.name == "unknown":
            continue
        reply = handle_intent(
            intent,
            db_path,
            created_by,
            chat_id=chat_id,
            telegram_user_id=telegram_user_id,
        )
        if reply and reply not in replies:
            replies.append(reply)

    if replies:
        return "\n".join(replies)

    return (
        "I didn't understand that yet. Try:\n"
        "• add milk to the list\n"
        "• add pay rent by friday category admin\n"
        "• show me the shopping list\n"
        "• export the list\n"
        "• clear the shopping list\n"
        "• empty the todo list\n"
        "• remove milk from the list\n"
        "• undo\n"
        "• cancel the reminder\n"
        "• snooze pay rent until tomorrow\n"
        "• what should I eat for dinner?\n"
        "• let's make curry with rice tonight\n"
        "• plan meals for this week\n"
        "• what's missing for dinner?\n"
        "• remind us every Tuesday to take out the trash\n"
        "• I said the task is for tomorrow\n"
        "• what's on today?"
    )


def handle_intent(
    intent: Intent,
    db_path: Path,
    created_by: str,
    *,
    chat_id: int | None = None,
    telegram_user_id: int | None = None,
) -> str:
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
            "• export the list\n"
            "• clear the shopping list\n"
            "• empty the todo list\n"
            "• remove milk from the list\n"
            "• cancel the reminder\n"
            "• snooze that until tomorrow\n"
            "• undo\n"
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
        todos = db.list_open_todos(
            db_path,
            category=intent.category,
            apartment=intent.apartment,
        )
        if not todos:
            if intent.category:
                return f"No open {intent.category} tasks."
            if intent.apartment:
                return f"No open tasks for apartment {intent.apartment}."
            return "The list is empty."
        return format_todo_list(todos, db_path)

    if intent.name == "export_list":
        export_format = "csv" if (intent.item or "").lower() == "csv" else "text"
        return format_export_list(
            db_path,
            export_format=export_format,
            category=intent.category,
        )

    if intent.name == "clear_shopping_list":
        return handle_clear_shopping_list(db_path, chat_id=chat_id)

    if intent.name == "clear_todos":
        return handle_clear_todos(db_path, chat_id=chat_id)

    if intent.name == "daily_briefing":
        return handle_daily_briefing(db_path)

    if intent.name == "cancel_timer":
        return handle_cancel_timer(db_path, chat_id, text_hint=intent.item)

    if intent.name == "undo":
        return handle_undo(db_path, chat_id)

    if intent.name == "snooze_reminder":
        return handle_snooze_reminder(
            intent.item or "",
            db_path,
            chat_id=chat_id,
            item_hint=intent.item,
            due_date=intent.due_date,
            delay_minutes=intent.delay_minutes,
        )

    if intent.name == "suggest_meal":
        profiles = db.list_user_profiles(db_path)
        return handle_suggest_meal(
            "",
            db_path,
            meal_type=intent.item,
            profiles=profiles,
        )

    if intent.name == "plan_meal":
        return handle_plan_meal(intent.item or "", db_path, created_by, meal_name=intent.item)

    if intent.name == "plan_week":
        profiles = db.list_user_profiles(db_path)
        return handle_plan_week(db_path, created_by, profiles=profiles)

    if intent.name == "show_meal_plan":
        return handle_show_meal_plan(db_path)

    if intent.name == "missing_ingredients":
        return handle_missing_ingredients(intent.item or "", db_path, meal_name=intent.item)

    if intent.name == "add_recipe":
        profile = db.get_user_profile(db_path, telegram_user_id) if telegram_user_id else None
        author = profile.display_name if profile else created_by
        return handle_add_recipe(intent, db_path, author=author)

    if intent.name == "add_recurring_reminder":
        return handle_add_recurring_reminder(
            intent.item or "",
            db_path,
            created_by,
            task=intent.item,
            recurrence=intent.recurrence,
        )

    if intent.name == "add_relative_reminder":
        if chat_id is None:
            return "I need a group chat to schedule a timed reminder."
        reply = handle_add_relative_reminder(
            intent.item or "",
            db_path,
            created_by,
            chat_id=chat_id,
            task=intent.item,
            delay_minutes=intent.delay_minutes,
        )
        if chat_id is not None:
            record_intent_context(db_path, chat_id, intent, todo_id=None)
        return reply

    if intent.name == "list_reminders":
        return handle_list_reminders(db_path, chat_id=chat_id)

    if intent.name == "remove_reminder":
        return handle_remove_reminder(db_path, intent.item)

    if intent.name == "log_meal":
        return handle_log_meal(intent.item or "", db_path, created_by)

    if intent.name == "who_did_what":
        return handle_who_did_what(db_path)

    if intent.name == "add_todo":
        if not intent.item:
            return "What should I add?"
        assigned_to_user_id = resolve_assignee_user_id(
            db_path,
            intent.assignee,
            current_user_id=telegram_user_id,
        )
        reply, todo = _add_or_merge_todo(
            db_path,
            intent.item,
            created_by,
            due_date=intent.due_date,
            category=intent.category or "general",
            created_by_user_id=telegram_user_id,
            assigned_to_user_id=assigned_to_user_id,
            apartment=intent.apartment or _default_apartment(db_path, telegram_user_id),
            chat_id=chat_id,
        )
        if chat_id is not None and todo is not None:
            record_intent_context(db_path, chat_id, intent, todo_id=todo.id)
        return reply

    if intent.name == "complete_todo":
        todo = resolve_action_target(db_path, chat_id, intent.item)
        if todo is None:
            if intent.item and not is_context_pronoun(intent.item):
                return f'I could not find an open item matching "{intent.item}".'
            return "Which item should I check off?"
        snapshot = todo
        todo = db.complete_todo_by_id(
            db_path,
            todo.id,
            completed_by_user_id=telegram_user_id,
        )
        if todo is None:
            return "Which item should I check off?"
        if chat_id is not None:
            record_complete(db_path, chat_id, snapshot)
            record_intent_context(db_path, chat_id, intent, todo_id=todo.id)
        return f'Checked off "{todo.text}".'

    if intent.name == "remove_todo":
        todo = resolve_action_target(db_path, chat_id, intent.item)
        if todo is None:
            if intent.item and not is_context_pronoun(intent.item):
                return f'I could not find an open item matching "{intent.item}".'
            return "Which item should I remove?"
        snapshot = todo
        todo = db.remove_todo_by_id(db_path, todo.id)
        if todo is None:
            return "Which item should I remove?"
        if chat_id is not None:
            record_remove(db_path, chat_id, snapshot)
            record_intent_context(db_path, chat_id, intent, clear_todo=True)
        return f'Removed "{todo.text}" from the list.'

    if intent.name == "update_todo":
        return handle_update_todo(intent, db_path, chat_id)

    if intent.name in ("update_profile", "show_profile", "log_preference", "log_dispreference"):
        if telegram_user_id is None:
            return "I couldn't identify who sent that message."
        return profile_handlers.handle_intent(intent, db_path, telegram_user_id)

    return ""


def _default_apartment(db_path: Path, telegram_user_id: int | None) -> str | None:
    if telegram_user_id is None:
        return None
    profile = db.get_user_profile(db_path, telegram_user_id)
    return profile.apartment if profile else None


def _resolve_update_target(
    intent: Intent,
    db_path: Path,
    chat_id: int | None,
) -> db.Todo | None:
    context_id = resolve_context_todo_id(db_path, chat_id) if chat_id is not None else None

    if intent.item and not intent.new_item and not intent.category:
        if context_id is not None:
            todo = db.get_open_todo(db_path, context_id)
            if todo is not None:
                return todo
        return db.get_latest_open_todo_without_due(db_path) or db.get_latest_open_todo(db_path)

    if context_id is not None:
        todo = db.get_open_todo(db_path, context_id)
        if todo is not None:
            return todo

    if intent.item and intent.item.lower() not in CONTEXT_PRONOUNS:
        matches = db.find_open_todos_partial(db_path, intent.item)
        if matches:
            return matches[0]

    return db.get_latest_open_todo_without_due(db_path) or db.get_latest_open_todo(db_path)


def handle_update_todo(
    intent: Intent,
    db_path: Path,
    chat_id: int | None = None,
) -> str:
    replies: list[str] = []

    if intent.item:
        for stray in ("loving girl friend", "find a loving"):
            wrong = db.remove_todo(db_path, stray)
            if wrong:
                replies.append(f'Removed mistaken entry "{wrong.text}".')

    todo = _resolve_update_target(intent, db_path, chat_id)
    if todo is None:
        if intent.item:
            return f'I could not find a task matching "{intent.item}".'
        return "I couldn't find a recent task to update."

    current = todo
    changes: list[str] = []

    new_text = intent.new_item
    if not new_text and intent.item and not intent.category:
        new_text = intent.item

    if new_text:
        if new_text.strip().lower() != todo.text.strip().lower():
            current = db.update_todo(db_path, current.id, text=new_text)
            changes.append(f'renamed to "{current.text}"')

    if intent.due_date:
        current = db.update_todo(db_path, current.id, due_date=intent.due_date)
        changes.append(f"due: {format_due_date(current.due_date)}")

    if intent.category:
        current = db.update_todo(db_path, current.id, category=intent.category)
        changes.append(f"category: {current.category}")

    if not changes:
        replies.append(f'Got it — you mean "{current.text}".')
        return " ".join(replies)

    if chat_id is not None:
        record_intent_context(db_path, chat_id, intent, todo_id=current.id)

    replies.append(f'Updated "{current.text}" — {"; ".join(changes)}.')
    return " ".join(replies)
