import re

_WAKE_WORD = re.compile(r"\bdomus\b", re.IGNORECASE)


def strip_wake_word(text: str) -> str:
    """Remove the Domus wake word and tidy spacing."""
    cleaned = _WAKE_WORD.sub(" ", text).strip(" ,:;-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or text.strip()


def normalize_assistant_message(text: str) -> str:
    """Normalize user text before intent parsing (wake word, spacing, polite filler)."""
    cleaned = strip_wake_word(text)
    cleaned = sanitize_command(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([!.,?])", r"\1", cleaned)
    return cleaned


def sanitize_command(text: str) -> str:
    cleaned = text.strip()
    if not re.match(
        r"^(?:thanks?|thank you|thx|danke(?: schön| dir)?|vielen dank)[!.?\s]*$",
        cleaned,
        flags=re.IGNORECASE,
    ):
        cleaned = re.sub(
            r",?\s*(?:thanks?|thank you|thx|danke)[!.]*\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    cleaned = re.sub(r"^\s*(?:please|pls)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,:;-")


def extract_quoted_text(text: str) -> str | None:
    match = re.search(r'"([^"]+)"', text)
    if match:
        return match.group(1).strip()
    match = re.search(r"'([^']+)'", text)
    if match:
        return match.group(1).strip()
    return None
