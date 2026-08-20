import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

import httpx

from domus.config import Settings

logger = logging.getLogger(__name__)

IntentName = Literal[
    "add_todo",
    "complete_todo",
    "remove_todo",
    "list_todos",
    "help",
    "greeting",
    "thanks",
    "unknown",
]

VALID_INTENTS = {
    "add_todo",
    "complete_todo",
    "remove_todo",
    "list_todos",
    "help",
    "greeting",
    "thanks",
    "unknown",
}


@dataclass(frozen=True)
class Intent:
    name: IntentName
    item: str | None = None


SYSTEM_PROMPT = """You parse household assistant commands for a Telegram bot.
Return ONLY valid JSON with this shape:
{"intents":[{"intent":"add_todo|complete_todo|remove_todo|list_todos|help|greeting|thanks|unknown","item":string|null}, ...]}

Rules:
- Return one or more intents if the user asks for multiple things in one message.
- add_todo: add something to the shared shopping/to-do list
- complete_todo: mark an item as done or bought
- remove_todo: remove an item from the list without marking done
- list_todos: show open list items
- help: user asks what you can do
- greeting: hi, hello, hey, or other friendly hellos
- thanks: thank you, thanks, danke, or other gratitude
- unknown: cannot map confidently

Natural language examples:
"hello" -> {"intents":[{"intent":"greeting","item":null}]}
"thank you" -> {"intents":[{"intent":"thanks","item":null}]}
"we need butter" -> {"intents":[{"intent":"add_todo","item":"butter"}]}
"we do not need paper any longer" -> {"intents":[{"intent":"remove_todo","item":"paper"}]}
"we need butter. we do not need paper any longer." -> {"intents":[{"intent":"add_todo","item":"butter"},{"intent":"remove_todo","item":"paper"}]}
"I bought the milk" -> {"intents":[{"intent":"complete_todo","item":"milk"}]}
"what's on the list?" -> {"intents":[{"intent":"list_todos","item":null}]}
"""


async def parse_intents(text: str, settings: Settings) -> list[Intent]:
    if settings.openrouter_api_key:
        try:
            intents = await _parse_with_openrouter(text, settings)
            if intents and not all(intent.name == "unknown" for intent in intents):
                logger.info("OpenRouter parsed %d intent(s) for %r", len(intents), text)
                return intents
            logger.warning("OpenRouter returned unknown; using fallback rules for %r", text)
        except Exception:
            logger.exception("OpenRouter intent parsing failed; using fallback rules")
    return _parse_with_rules(text)


def _parse_json_content(content: str) -> dict | list:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = re.sub(r'"intent:([a-z_]+)"', r'"intent":"\1"', cleaned)
        repaired = re.sub(r"'intent':", '"intent":', repaired)
        return json.loads(repaired)


def _normalize_item(item: str | None) -> str | None:
    if not item:
        return None
    cleaned = item.strip().strip(".")
    if cleaned.lower().startswith("the "):
        cleaned = cleaned[4:]
    return cleaned or None


def _intent_from_dict(data: dict) -> Intent:
    intent_name = data.get("intent", "unknown")
    if intent_name not in VALID_INTENTS:
        intent_name = "unknown"
    return Intent(name=intent_name, item=_normalize_item(data.get("item")))


def _intents_from_payload(parsed: dict | list) -> list[Intent]:
    if isinstance(parsed, list):
        return [_intent_from_dict(item) for item in parsed if isinstance(item, dict)]

    if "intents" in parsed and isinstance(parsed["intents"], list):
        return [_intent_from_dict(item) for item in parsed["intents"] if isinstance(item, dict)]

    if "intent" in parsed:
        return [_intent_from_dict(parsed)]

    return [Intent(name="unknown")]


async def _parse_with_openrouter(text: str, settings: Settings) -> list[Intent]:
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/sebharm28/Domus",
        "X-Title": "Domus",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        if response.status_code == 404:
            detail = response.text[:200]
            raise RuntimeError(
                f"Model {settings.openrouter_model!r} unavailable on OpenRouter: {detail}"
            )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    parsed = _parse_json_content(content)
    intents = _intents_from_payload(parsed)
    return intents or [Intent(name="unknown")]


def _split_items(raw: str) -> list[str]:
    parts = re.split(r",\s*|\s+and\s+", raw.strip())
    items: list[str] = []
    for part in parts:
        item = _normalize_item(part)
        if item:
            items.append(item)
    return items


def _split_clauses(text: str) -> list[str]:
    parts = re.split(r"[.!?\n]+", text.strip())
    return [part.strip(" ,:;-") for part in parts if part.strip(" ,:;-")]


def _parse_clause_intents(normalized: str) -> list[Intent]:
    if re.match(
        r"^(?:hi|hello|hey|good (?:morning|evening|night)|guten (?:tag|morgen|abend)|moin|servus)(?: there)?[!.,]*$",
        normalized,
    ):
        return [Intent(name="greeting")]

    if re.match(
        r"^(?:thanks?|thank you|thx|danke(?: schön| dir)?|vielen dank)[!.,]*$",
        normalized,
    ):
        return [Intent(name="thanks")]

    if re.search(r"\b(help|what can you do)\b", normalized):
        return [Intent(name="help")]

    need_match = re.match(r"^(?:also |and )?we need\s+(.+)$", normalized)
    if need_match:
        return [Intent(name="add_todo", item=item) for item in _split_items(need_match.group(1))]

    add_match = re.search(
        r"^(?:also |and )?(?:(?:add|put)\s+(.+?)\s+(?:to|on)\s+(?:the\s+)?(?:list|shopping list)\s*$|need\s+(?:to get|more)\s+(.+?)$)",
        normalized,
    )
    if add_match:
        item = next(group for group in add_match.groups() if group)
        return [Intent(name="add_todo", item=_normalize_item(item))]

    remove_match = re.search(
        r"^(?:also |and )?(?:(?:remove|delete)\s+(.+?)$|(?:we )?(?:do not|don't|no longer)\s+need\s+(.+?)(?:\s+any(?:\s+)?(?:longer|more))?$)",
        normalized,
    )
    if remove_match:
        item = next(group for group in remove_match.groups() if group)
        return [Intent(name="remove_todo", item=_normalize_item(item))]

    complete_match = re.search(
        r"^(?:also |and )?(?:check off|mark|done with|bought|got)\s+(?:the\s+)?(.+?)(?:\s+because\b.*)?$",
        normalized,
    )
    if complete_match:
        return [Intent(name="complete_todo", item=_normalize_item(complete_match.group(1)))]

    if re.search(
        r"(?:^list(?: items| todos)?$|^show(?: the)?(?: list| shopping list)?$|what(?:'s| is) on (?:the )?(?:list|shopping list))",
        normalized,
    ):
        return [Intent(name="list_todos")]

    return []


def _parse_clause(normalized: str) -> Intent | None:
    intents = _parse_clause_intents(normalized)
    return intents[0] if intents else None


def _parse_with_rules(text: str) -> list[Intent]:
    intents: list[Intent] = []
    for clause in _split_clauses(text):
        normalized = clause.strip().lower().rstrip(".!?")
        intents.extend(_parse_clause_intents(normalized))

    return intents or [Intent(name="unknown")]
