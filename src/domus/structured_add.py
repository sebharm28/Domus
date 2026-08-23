import re

from domus.categories import infer_category
from domus.dates import parse_due_date, extract_due_date_from_message
from domus.text_utils import extract_quoted_text, sanitize_command


def try_parse_structured_add(text: str) -> tuple[str, str | None, str | None] | None:
    """Parse explicit add commands like: add "task" to my todo list until tomorrow."""
    cleaned = sanitize_command(text)
    cleaned = re.sub(r"^(?:please|could you|could u)\s+", "", cleaned, flags=re.IGNORECASE)
    lowered = cleaned.lower()
    message_due = extract_due_date_from_message(text)

    quoted = extract_quoted_text(cleaned)
    if quoted and re.search(r"\badd\b", lowered) and re.search(r"\blist\b", lowered):
        _, due_date = parse_due_date(cleaned)
        default_category = "shopping" if "shopping" in lowered else None
        return quoted, due_date or message_due, infer_category(quoted, default_category)

    patterns = [
        r"^add\s+(.+?)\s+to\s+(?:my\s+|the\s+)?(?:to[- ]?do\s+)?list(?:\s|$|[.!?])",
        r"^add\s+(.+?)\s+to\s+(?:my\s+|the\s+)?shopping\s+list(?:\s|$|[.!?])",
        r"^put\s+(.+?)\s+(?:to|on)\s+(?:the\s+)?(?:shopping\s+)?list(?:\s|$|[.!?])",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if not match:
            continue
        item = match.group(1).strip(" ,:;-")
        item, due_date = parse_due_date(item)
        item = re.sub(r"\s+", " ", item).strip(" ,:;-")
        default_category = "shopping" if "shopping" in lowered else None
        return item, due_date or message_due, infer_category(item, default_category)

    return None
