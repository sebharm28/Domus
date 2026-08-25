import re

PRIVATE_MARKER = re.compile(r"/private\b", re.IGNORECASE)
PRIVATE_PREFIX = re.compile(r"^/private\s+", re.IGNORECASE)


def apply_private_mode(text: str, *, reply_to_bot: bool = False) -> tuple[str, bool]:
    """Strip /private marker and report whether this turn is rules-only."""
    cleaned = text.strip()
    if PRIVATE_PREFIX.search(cleaned):
        without = PRIVATE_PREFIX.sub("", cleaned, count=1).strip()
        return without or cleaned, True
    if reply_to_bot and PRIVATE_MARKER.search(cleaned):
        without = PRIVATE_MARKER.sub("", cleaned, count=1).strip(" ,:;-")
        return without or cleaned, True
    return cleaned, False
