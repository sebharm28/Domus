from datetime import datetime, timezone
from pathlib import Path

from domus import db
from domus.dates import format_due_date
from domus.recurrence import format_recurrence, parse_reminder_phrase


def handle_add_recurring_reminder(
    text: str,
    db_path: Path,
    created_by: str,
    *,
    task: str | None = None,
    recurrence: str | None = None,
) -> str:
    if task and recurrence:
        parsed_task, parsed_recurrence = task, recurrence
    else:
        parsed = parse_reminder_phrase(text)
        if not parsed:
            return (
                'Try e.g. "remind us every Tuesday to take out the trash" or '
                '"remind me on the 1st of each month to pay rent".'
            )
        parsed_task, parsed_recurrence = parsed

    reminder = db.add_reminder(db_path, parsed_task, parsed_recurrence, created_by)
    schedule = format_recurrence(reminder.recurrence)
    next_due = format_due_date(reminder.next_due)
    return f'Set recurring reminder: "{reminder.text}" ({schedule}, next: {next_due}).'


def _format_fire_at(fire_at: str) -> str:
    when = datetime.fromisoformat(fire_at)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone().strftime("%H:%M")


def _minutes_until(fire_at: str) -> int:
    when = datetime.fromisoformat(fire_at)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = when - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds() // 60))


def handle_list_reminders(db_path: Path, chat_id: int | None = None) -> str:
    recurring = db.list_reminders(db_path)
    pending = db.list_pending_one_shot_reminders(db_path, chat_id=chat_id)
    recent = db.list_recent_one_shot_reminders(db_path, chat_id) if chat_id is not None else []

    if not recurring and not pending and not recent:
        return "No recurring reminders or pending timers."

    lines: list[str] = []

    if recurring:
        lines.append("Recurring reminders:")
        for reminder in recurring:
            schedule = format_recurrence(reminder.recurrence)
            next_due = format_due_date(reminder.next_due)
            lines.append(f"• {reminder.text} — {schedule}, next: {next_due}")

    if pending:
        if lines:
            lines.append("")
        lines.append("Pending timers:")
        for reminder in pending:
            minutes = _minutes_until(reminder.fire_at)
            clock = _format_fire_at(reminder.fire_at)
            if minutes <= 0:
                lines.append(f'• {reminder.text} — due now ({clock})')
            elif minutes < 60:
                lines.append(f'• {reminder.text} — in {minutes} min ({clock})')
            else:
                hours = minutes // 60
                lines.append(f'• {reminder.text} — in {hours} hr ({clock})')

    if recent and not pending:
        if lines:
            lines.append("")
        lines.append("Recent timers:")
        for reminder in recent[:3]:
            clock = _format_fire_at(reminder.fire_at)
            lines.append(f'• {reminder.text} — fired at {clock}')

    return "\n".join(lines)


def handle_remove_reminder(db_path: Path, item: str | None) -> str:
    if not item:
        return "Which recurring reminder should I remove?"
    reminder = db.remove_reminder(db_path, item)
    if reminder is None:
        return f'I could not find a recurring reminder matching "{item}".'
    return f'Removed recurring reminder: "{reminder.text}".'


def handle_cancel_timer(
    db_path: Path,
    chat_id: int | None,
    *,
    text_hint: str | None = None,
) -> str:
    if chat_id is None:
        return "I couldn't tell which chat to cancel the timer in."
    cancelled = db.cancel_one_shot_reminder(db_path, chat_id, text_hint=text_hint)
    if cancelled is None:
        return "No pending timers to cancel."
    from domus.undo import record_cancel_timer

    record_cancel_timer(db_path, chat_id, cancelled)
    return f'Cancelled timer: "{cancelled.text}".'
