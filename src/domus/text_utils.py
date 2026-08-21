import re


def sanitize_command(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r",?\s*(?:thanks?|thank you|thx|danke)[!.]*\s*$", "", cleaned, flags=re.IGNORECASE)
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
