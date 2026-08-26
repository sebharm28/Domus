import re
from datetime import datetime, timedelta, timezone

from domus import db


def parse_relative_reminder_phrase(text: str) -> tuple[str, int] | None:
    normalized = text.strip().lower().rstrip(".!?")
    match = re.search(
        r"^remind(?: us| me)?(?: to)? in (\d+)\s*"
        r"(minutes?|mins?|hours?|hrs?)"
        r"(?:\s+(?:to|about|that))?\s*(.*)$",
        normalized,
    )
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    task = match.group(3).strip(" .") or "Reminder"
    minutes = amount * 60 if unit.startswith("hour") or unit.startswith("hr") else amount
    if minutes <= 0:
        return None
    return task, minutes


def handle_add_relative_reminder(
    text: str,
    db_path,
    created_by: str,
    *,
    chat_id: int,
    task: str | None = None,
    delay_minutes: int | None = None,
) -> str:
    if task and delay_minutes:
        parsed_task, minutes = task, delay_minutes
    else:
        parsed = parse_relative_reminder_phrase(text)
        if not parsed:
            return (
                'Try e.g. "remind me in 30 minutes the oven is on" or '
                '"remind us in 2 hours to take out the laundry".'
            )
        parsed_task, minutes = parsed

    fire_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    reminder = db.add_one_shot_reminder(
        db_path,
        parsed_task,
        fire_at,
        chat_id,
        created_by,
    )
    local_time = fire_at.astimezone().strftime("%H:%M")
    return (
        f'Reminder set: "{reminder.text}" in {minutes} minute(s) '
        f"(around {local_time})."
    )
