import re
from dataclasses import dataclass

from domus.categories import infer_category
from domus.dates import parse_category_hint, parse_due_date


@dataclass(frozen=True)
class NaturalAdd:
    item: str
    due_date: str | None
    category: str


def _normalize_task(text: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", text.strip(" ,:;-."))
    cleaned = re.sub(r"^(?:to\s+)?(?:do\s+)?(?:a\s+)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+for work$", "", cleaned, flags=re.IGNORECASE)
    return cleaned or None


def _extract_task_text(text: str) -> str | None:
    lowered = text.lower()
    patterns = [
        r"where i (?:have to|need to)\s+(?:do\s+)?(.+)$",
        r"(?:remind me to|i need to|i have to|i must|i should)\s+(.+)$",
        r"(?:todo|task)\s*[:\-]\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            return _normalize_task(match.group(1))
    return None


def _infer_work_category(text: str) -> str | None:
    if re.search(r"\b(for work|at work|work related|for the office)\b", text, re.IGNORECASE):
        return "personal"
    return None


def try_parse_natural_add(text: str) -> NaturalAdd | None:
    """Parse free-form messages like 'I have a todo until tomorrow where I have to do X'."""
    lowered = text.lower()
    if not re.search(
        r"\b(todo|task|remind me|need to|have to|must|should|until|untill|by tomorrow)\b",
        lowered,
    ):
        return None

    _, category_hint = parse_category_hint(text)
    working, due_date = parse_due_date(text)
    task = _extract_task_text(working)
    if not task:
        stripped = re.sub(
            r"^(?:i have a todo|i've got a todo|i have a task|new todo|new task)\s*",
            "",
            working,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(
            r"\b(?:until|untill|by|before|due)\s+(?:tomorrow|today|\w+)\b",
            "",
            stripped,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(
            r"\bwhere i (?:have to|need to)\s+(?:do\s+)?",
            "",
            stripped,
            flags=re.IGNORECASE,
        )
        task = _normalize_task(stripped)

    if not task:
        return None

    category = infer_category(task, category_hint or _infer_work_category(text))
    return NaturalAdd(item=task, due_date=due_date, category=category)
