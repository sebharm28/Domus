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
    "unknown",
]


@dataclass(frozen=True)
class Intent:
    name: IntentName
    item: str | None = None


SYSTEM_PROMPT = """You parse household assistant commands for a Telegram bot.
Return ONLY valid JSON with this shape:
{"intent":"add_todo|complete_todo|remove_todo|list_todos|help|unknown","item":string|null}

Intent meanings:
- add_todo: add something to the shared shopping/to-do list
- complete_todo: mark an item as done or bought
- remove_todo: remove an item from the list without marking done
- list_todos: show open list items
- help: user asks what you can do
- unknown: cannot map confidently

Examples:
"add milk to the list" -> {"intent":"add_todo","item":"milk"}
"what's on the list?" -> {"intent":"list_todos","item":null}
"check off bread" -> {"intent":"complete_todo","item":"bread"}
"remove eggs" -> {"intent":"remove_todo","item":"eggs"}
"what can you do?" -> {"intent":"help","item":null}
"""


async def parse_intent(text: str, settings: Settings) -> Intent:
    if settings.openrouter_api_key:
        try:
            return await _parse_with_openrouter(text, settings)
        except Exception:
            logger.exception("OpenRouter intent parsing failed; using fallback rules")
    return _parse_with_rules(text)


async def _parse_with_openrouter(text: str, settings: Settings) -> Intent:
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
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    intent_name = parsed.get("intent", "unknown")
    item = parsed.get("item")
    if intent_name not in {
        "add_todo",
        "complete_todo",
        "remove_todo",
        "list_todos",
        "help",
        "unknown",
    }:
        intent_name = "unknown"
    return Intent(name=intent_name, item=item)


def _parse_with_rules(text: str) -> Intent:
    normalized = text.strip().lower()

    if re.search(r"\b(help|what can you do)\b", normalized):
        return Intent(name="help")

    add_match = re.search(
        r"(?:add|put)\s+(.+?)\s+(?:to|on)\s+(?:the\s+)?(?:list|shopping list)\s*$",
        normalized,
    )
    if add_match:
        return Intent(name="add_todo", item=add_match.group(1).strip())

    complete_match = re.search(
        r"(?:check off|mark|done with|bought|got)\s+(.+)$",
        normalized,
    )
    if complete_match:
        return Intent(name="complete_todo", item=complete_match.group(1).strip())

    remove_match = re.search(r"(?:remove|delete)\s+(.+)$", normalized)
    if remove_match:
        return Intent(name="remove_todo", item=remove_match.group(1).strip())

    if re.search(
        r"(?:^list(?: items| todos)?$|^show(?: the)?(?: list| shopping list)?$|what(?:'s| is) on (?:the )?(?:list|shopping list))",
        normalized,
    ):
        return Intent(name="list_todos")

    return Intent(name="unknown")
