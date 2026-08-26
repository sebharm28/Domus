import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from domus import db
from domus.context import is_context_pronoun, resolve_context_todo_id
from domus.dates import extract_due_date_from_message, format_due_date, parse_due_date


def parse_snooze_phrase(text: str) -> tuple[str | None, str | None, int | None]:
    """Return (item_hint, due_date_iso, delay_minutes)."""
    normalized = text.strip().lower().rstrip(".!?")

    relative = re.search(
        r"^snooze(?: the| my| that| it)?(?: reminder| timer| task)?(?: for| in)?\s+"
        r"(\d+)\s*(minutes?|mins?|hours?|hrs?)"
        r"(?:\s+(?:about|to|for)\s+(.+))?$",
        normalized,
    )
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        minutes = amount * 60 if unit.startswith("hour") or unit.startswith("hr") else amount
        hint = (relative.group(3) or "").strip(" .") or None
        return hint, None, minutes

    absolute = re.search(
        r"^snooze(?: the| my)?(?: reminder| timer| task)?(?: about| for)?\s+"
        r"(.+?)\s+(?:until|to|for)\s+(.+)$",
        normalized,
    )
    if absolute:
        item = absolute.group(1).strip(" .")
        when_text = absolute.group(2).strip(" .")
        _, due_date = parse_due_date(when_text)
        if due_date:
            return item, due_date, None

    short = re.search(
        r"^snooze(?: that| it| the reminder| the timer)?(?: until| to| for)?\s+(.+)$",
        normalized,
    )
    if short:
        when_text = short.group(1).strip(" .")
        _, due_date = parse_due_date(when_text)
        if due_date:
            return None, due_date, None
        relative_short = re.search(
            r"^(\d+)\s*(minutes?|mins?|hours?|hrs?)$",
            when_text,
        )
        if relative_short:
            amount = int(relative_short.group(1))
            unit = relative_short.group(2)
            minutes = amount * 60 if unit.startswith("hour") or unit.startswith("hr") else amount
            return None, None, minutes

    return None, None, None


def _find_recurring(db_path: Path, item: str) -> db.Reminder | None:
    normalized = item.strip().lower()
    for reminder in db.list_reminders(db_path):
        if normalized in reminder.text.lower():
            return reminder
    return None


def _resolve_snooze_target(
    db_path: Path,
    chat_id: int | None,
    item_hint: str | None,
) -> tuple[str, object] | None:
    if item_hint and not is_context_pronoun(item_hint):
        todos = [todo for todo in db.find_open_todos_partial(db_path, item_hint) if todo.due_date]
        if todos:
            return "todo", todos[0]
        recurring = _find_recurring(db_path, item_hint)
        if recurring is not None:
            return "recurring", recurring
        if chat_id is not None:
            pending = [
                reminder
                for reminder in db.list_pending_one_shot_reminders(db_path, chat_id)
                if item_hint.lower() in reminder.text.lower()
            ]
            if pending:
                return "one_shot", pending[-1]

    if chat_id is not None:
        context = db.get_chat_context(db_path, chat_id)
        if context and context.last_intent == "add_relative_reminder":
            pending = db.list_pending_one_shot_reminders(db_path, chat_id)
            if context.last_item:
                matched = [
                    reminder
                    for reminder in pending
                    if context.last_item.lower() in reminder.text.lower()
                ]
                if matched:
                    return "one_shot", matched[-1]
            if len(pending) == 1:
                return "one_shot", pending[0]

        context_id = resolve_context_todo_id(db_path, chat_id)
        if context_id is not None:
            todo = db.get_open_todo(db_path, context_id)
            if todo is not None and todo.due_date:
                return "todo", todo

        pending = db.list_pending_one_shot_reminders(db_path, chat_id)
        if len(pending) == 1:
            return "one_shot", pending[-1]

    todos = db.list_due_todos_for_reminder(db_path, date.today())
    if len(todos) == 1:
        return "todo", todos[0]

    return None


def handle_snooze_reminder(
    text: str,
    db_path: Path,
    *,
    chat_id: int | None = None,
    item_hint: str | None = None,
    due_date: str | None = None,
    delay_minutes: int | None = None,
) -> str:
    if due_date is None and delay_minutes is None:
        parsed_hint, parsed_due, parsed_delay = parse_snooze_phrase(text)
        item_hint = item_hint or parsed_hint
        due_date = parsed_due or extract_due_date_from_message(text)
        delay_minutes = delay_minutes if delay_minutes is not None else parsed_delay

    if due_date is None and delay_minutes is None:
        return (
            'Try e.g. "snooze pay rent until tomorrow" or '
            '"snooze the reminder for 30 minutes".'
        )

    target = _resolve_snooze_target(db_path, chat_id, item_hint)
    if target is None:
        if item_hint:
            return f'I could not find a reminder or due task matching "{item_hint}".'
        return "I couldn't find a recent reminder or due task to snooze."

    kind, obj = target

    if kind == "todo":
        todo = obj
        old_due = todo.due_date
        old_reminder_sent = todo.reminder_sent
        if due_date:
            updated = db.update_todo(db_path, todo.id, due_date=due_date)
            when = format_due_date(updated.due_date)
        else:
            assert delay_minutes is not None
            assert todo.due_date is not None
            new_due = date.fromisoformat(todo.due_date) + timedelta(minutes=delay_minutes)
            updated = db.update_todo(db_path, todo.id, due_date=new_due.isoformat())
            when = format_due_date(updated.due_date)
        if chat_id is not None:
            from domus.undo import record_snooze

            record_snooze(
                db_path,
                chat_id,
                "snooze_todo",
                {
                    "todo_id": todo.id,
                    "due_date": old_due,
                    "reminder_sent": old_reminder_sent,
                },
            )
        return f'Snoozed "{updated.text}" until {when}.'

    if kind == "recurring":
        reminder = obj
        old_next_due = reminder.next_due
        if due_date:
            new_due = date.fromisoformat(due_date)
        else:
            assert delay_minutes is not None
            new_due = date.fromisoformat(reminder.next_due) + timedelta(minutes=delay_minutes)
        updated = db.set_reminder_next_due(db_path, reminder.id, new_due)
        when = format_due_date(updated.next_due)
        if chat_id is not None:
            from domus.undo import record_snooze

            record_snooze(
                db_path,
                chat_id,
                "snooze_recurring",
                {"reminder_id": reminder.id, "next_due": old_next_due},
            )
        return f'Snoozed recurring reminder "{updated.text}" to {when}.'

    reminder = obj
    old_fire_at = reminder.fire_at
    if delay_minutes is not None:
        fire_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    else:
        assert due_date is not None
        fire_at = datetime.fromisoformat(f"{due_date}T09:00:00").replace(tzinfo=timezone.utc)
    updated = db.update_one_shot_fire_at(db_path, reminder.id, fire_at)
    clock = fire_at.astimezone().strftime("%H:%M")
    if chat_id is not None:
        from domus.undo import record_snooze

        record_snooze(
            db_path,
            chat_id,
            "snooze_one_shot",
            {"reminder_id": reminder.id, "fire_at": old_fire_at},
        )
    if delay_minutes is not None:
        return f'Snoozed timer "{updated.text}" by {delay_minutes} minute(s) (around {clock}).'
    return f'Snoozed timer "{updated.text}" to {format_due_date(due_date)} ({clock}).'
