import re

from domus.dates import parse_due_date
from domus.text_utils import extract_quoted_text, sanitize_command


def try_parse_structured_add(text: str) -> tuple[str, str | None, str | None] | None:
    """Parse explicit add commands like: add "task" to my todo list until tomorrow."""
    cleaned = sanitize_command(text)
    lowered = cleaned.lower()

    quoted = extract_quoted_text(cleaned)
    if quoted and re.search(r"\badd\b", lowered) and re.search(r"\blist\b", lowered):
        _, due_date = parse_due_date(cleaned)
        default_category = "shopping" if "shopping" in lowered else "general"
        return quoted, due_date, default_category

    patterns = [
        r"^add\s+(.+?)\s+to\s+(?:my\s+)?(?:to[- ]?do\s+)?list(?:\s|$)",
        r"^add\s+(.+?)\s+to\s+(?:my\s+)?shopping\s+list(?:\s|$)",
        r"^put\s+(.+?)\s+(?:to|on)\s+(?:the\s+)?(?:shopping\s+)?list(?:\s|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if not match:
            continue
        item = match.group(1).strip(" ,:;-")
        item, due_date = parse_due_date(item)
        item = re.sub(r"\s+", " ", item).strip(" ,:;-")
        category = "shopping" if "shopping" in lowered else "general"
        return item, due_date, category

    return None
