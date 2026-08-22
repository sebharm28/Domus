import calendar
import re
from datetime import date, timedelta

from domus.dates import WEEKDAYS


def parse_recurrence_key(recurrence: str) -> tuple[str, str | None]:
    if recurrence == "daily":
        return "daily", None
    if recurrence.startswith("weekly:"):
        return "weekly", recurrence.split(":", 1)[1]
    if recurrence.startswith("monthly:"):
        return "monthly", recurrence.split(":", 1)[1]
    raise ValueError(f"Unknown recurrence: {recurrence}")


def format_recurrence(recurrence: str) -> str:
    kind, value = parse_recurrence_key(recurrence)
    if kind == "daily":
        return "every day"
    if kind == "weekly":
        return f"every {value.title()}"
    if kind == "monthly":
        day = int(value)
        suffix = "th"
        if day % 10 == 1 and day != 11:
            suffix = "st"
        elif day % 10 == 2 and day != 12:
            suffix = "nd"
        elif day % 10 == 3 and day != 13:
            suffix = "rd"
        return f"on the {day}{suffix} of each month"
    return recurrence


def first_due_date(recurrence: str, today: date | None = None) -> date:
    today = today or date.today()
    kind, value = parse_recurrence_key(recurrence)

    if kind == "daily":
        return today

    if kind == "weekly":
        target = WEEKDAYS[value.lower()]
        days_ahead = (target - today.weekday()) % 7
        return today + timedelta(days=days_ahead)

    if kind == "monthly":
        day = int(value)
        last_day = calendar.monthrange(today.year, today.month)[1]
        candidate = date(today.year, today.month, min(day, last_day))
        if candidate >= today:
            return candidate
        return _monthly_on_day(today.year, today.month + 1, day)

    raise ValueError(f"Unknown recurrence: {recurrence}")


def next_due_date(recurrence: str, current_due: date) -> date:
    kind, value = parse_recurrence_key(recurrence)

    if kind == "daily":
        return current_due + timedelta(days=1)

    if kind == "weekly":
        return current_due + timedelta(days=7)

    if kind == "monthly":
        day = int(value)
        year, month = current_due.year, current_due.month + 1
        if month > 12:
            year += 1
            month = 1
        return _monthly_on_day(year, month, day)

    raise ValueError(f"Unknown recurrence: {recurrence}")


def _monthly_on_day(year: int, month: int, day: int) -> date:
    while month > 12:
        month -= 12
        year += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def parse_reminder_phrase(text: str) -> tuple[str, str] | None:
    normalized = text.strip().lower().rstrip(".!?")

    daily_match = re.search(
        r"^remind(?: us| me)?(?: to)?(?: every day| daily)\s+(?:to\s+)?(.+)$",
        normalized,
    )
    if daily_match:
        return daily_match.group(1).strip(), "daily"

    weekly_match = re.search(
        r"^remind(?: us| me)?(?: to)? every (?:week on )?"
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"(?:\s+to|\s+that we|\s+that i|\s+to)\s+(.+)$",
        normalized,
    )
    if weekly_match:
        weekday = weekly_match.group(1)
        task = weekly_match.group(2).strip()
        return task, f"weekly:{weekday}"

    weekly_alt = re.search(
        r"^remind(?: us| me)?(?: to)? every (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(.+)$",
        normalized,
    )
    if weekly_alt:
        task = weekly_alt.group(2).strip()
        if task.startswith("to "):
            task = task[3:]
        return task, f"weekly:{weekly_alt.group(1)}"

    monthly_match = re.search(
        r"^remind(?: us| me)?(?: to)? on the (\d{1,2})(?:st|nd|rd|th)? of each month(?: to)?\s+(.+)$",
        normalized,
    )
    if monthly_match:
        day = int(monthly_match.group(1))
        return monthly_match.group(2).strip(), f"monthly:{day}"

    return None
