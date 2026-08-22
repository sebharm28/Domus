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


def handle_list_reminders(db_path: Path) -> str:
    reminders = db.list_reminders(db_path)
    if not reminders:
        return "No recurring reminders are set."

    lines = ["Recurring reminders:"]
    for reminder in reminders:
        schedule = format_recurrence(reminder.recurrence)
        next_due = format_due_date(reminder.next_due)
        lines.append(f"• {reminder.text} — {schedule}, next: {next_due}")
    return "\n".join(lines)


def handle_remove_reminder(db_path: Path, item: str | None) -> str:
    if not item:
        return "Which recurring reminder should I remove?"
    reminder = db.remove_reminder(db_path, item)
    if reminder is None:
        return f'I could not find a recurring reminder matching "{item}".'
    return f'Removed recurring reminder: "{reminder.text}".'
