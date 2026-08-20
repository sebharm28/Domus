import re
from datetime import date, timedelta
from typing import Callable


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _next_weekday(target_weekday: int, today: date) -> date:
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def parse_due_date(text: str, today: date | None = None) -> tuple[str, str | None]:
    """Extract a due date phrase from text and return cleaned text + ISO date."""
    today = today or date.today()
    working = text.strip()
    due_date: date | None = None

    patterns: list[tuple[str, Callable[[re.Match[str]], date]]] = [
        (r"\b(?:until|untill|by|before|due)\s+(\d{4}-\d{2}-\d{2})\b", lambda m: date.fromisoformat(m.group(1))),
        (r"\b(?:until|untill|by|before|due)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lambda m: _next_weekday(WEEKDAYS[m.group(1).lower()], today)),
        (r"\b(?:until|untill|by|before|due)\s+(tomorrow)\b", lambda _m: today + timedelta(days=1)),
        (r"\b(?:until|untill|by|before|due)\s+(today)\b", lambda _m: today),
        (r"\bby\s+(\d{4}-\d{2}-\d{2})\b", lambda m: date.fromisoformat(m.group(1))),
        (r"\bon\s+(\d{4}-\d{2}-\d{2})\b", lambda m: date.fromisoformat(m.group(1))),
        (r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lambda m: _next_weekday(WEEKDAYS[m.group(1).lower()], today)),
        (r"\bon\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lambda m: _next_weekday(WEEKDAYS[m.group(1).lower()], today)),
        (r"\btomorrow\b", lambda _m: today + timedelta(days=1)),
        (r"\btoday\b", lambda _m: today),
    ]

    for pattern, parser in patterns:
        match = re.search(pattern, working, flags=re.IGNORECASE)
        if not match:
            continue
        due_date = parser(match)
        working = (working[: match.start()] + working[match.end() :]).strip(" ,:-")
        break

    return working, due_date.isoformat() if due_date else None


def parse_category_hint(text: str) -> tuple[str, str | None]:
    """Extract explicit category hints like 'category: admin' from text."""
    match = re.search(
        r"\b(?:category|cat)\s*[:\-]?\s*(shopping|household|admin|maintenance|personal|general)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return text, None
    cleaned = (text[: match.start()] + text[match.end() :]).strip(" ,:-")
    return cleaned, match.group(1).lower()


def format_due_date(due_date: str | None) -> str:
    if not due_date:
        return "no date"
    try:
        parsed = date.fromisoformat(due_date)
    except ValueError:
        return due_date
    return parsed.strftime("%a, %d %b %Y")
