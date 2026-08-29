"""Phase A German input — map common phrases to English before rule parsing."""

import re

# (pattern, replacement) — applied in order to normalized lowercase text.
_GERMAN_RULES: tuple[tuple[str, str], ...] = (
    (r"^füge\s+(.+?)\s+(?:zur|zum)\s+(?:einkaufs)?liste\s+hinzu\.?$", r"add \1 to the list"),
    (r"^wir brauchen\s+(.+)$", r"we need \1"),
    (r"^was steht heute an\??$", "what's on today?"),
    (r"^was fehlt(?: zum abendessen)?\??$", "what's missing for dinner?"),
    (r"^was soll(?:en)? wir (?:kochen|essen)\??$", "what should we cook?"),
    (r"^plane(?: die)?(?: mahlzeiten)?(?: für)?(?: diese)? woche\.?$", "plan meals for this week"),
    (r"^erinnere uns(?: daran)?(?: jeden)?\s+(montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)\s+(?:an|dass)\s+(.+)$", r"remind us every \1 to \2"),
    (r"^erinnere mich in\s+(\d+)\s+min(?:uten)?(?: daran)?(?:,)?\s+(?:dass\s+)?(.+)$", r"remind me in \1 minutes \2"),
    (r"^zeig(?: mir)?(?: die)? einkaufsliste\.?$", "show me the shopping list"),
    (r"^was steht auf der liste\??$", "what's on the list?"),
    (r"^milch(?: ist)?(?: ab)?gehakt\.?$", "check off milk"),
    (r"^entferne\s+(.+?)\s+(?:von der liste|von der einkaufsliste)\.?$", r"remove \1 from the list"),
)

_WEEKDAY_MAP = {
    "montag": "monday",
    "dienstag": "tuesday",
    "mittwoch": "wednesday",
    "donnerstag": "thursday",
    "freitag": "friday",
    "samstag": "saturday",
    "sonntag": "sunday",
}


def normalize_german_input(text: str) -> str:
    """Return English-equivalent command when a known German pattern matches."""
    normalized = text.strip().lower().rstrip(".!?")
    if not normalized:
        return text

    for pattern, replacement in _GERMAN_RULES:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        result = match.expand(replacement)
        for de, en in _WEEKDAY_MAP.items():
            result = re.sub(rf"\b{de}\b", en, result, flags=re.IGNORECASE)
        return result
    return text
