import re

from domus.config import Settings


def _compile_patterns(raw: list[str]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for pattern in raw:
        pattern = pattern.strip()
        if not pattern:
            continue
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error:
            compiled.append(re.compile(re.escape(pattern), re.IGNORECASE))
    return compiled


def redact_for_llm(text: str, settings: Settings) -> tuple[str, list[str]]:
    """Redact sensitive fragments before text is sent to OpenRouter."""
    if not settings.redaction_enabled or not settings.redaction_patterns:
        return text, []

    redacted_labels: list[str] = []
    result = text
    for index, pattern in enumerate(_compile_patterns(settings.redaction_patterns), start=1):
        token = f"[REDACTED_{index}]"

        def _replace(match: re.Match[str], *, token: str = token) -> str:
            label = match.group(0).strip()
            if label and label not in redacted_labels:
                redacted_labels.append(label)
            return token

        result = pattern.sub(_replace, result)
    return result, redacted_labels
