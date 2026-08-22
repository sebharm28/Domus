import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

import httpx

from domus.categories import infer_category
from domus.config import Settings
from domus.dates import parse_category_hint, parse_due_date
from domus.natural_language import try_parse_natural_add
from domus.structured_add import try_parse_structured_add
from domus.text_utils import sanitize_command

logger = logging.getLogger(__name__)

IntentName = Literal[
    "add_todo",
    "complete_todo",
    "remove_todo",
    "list_todos",
    "suggest_meal",
    "log_meal",
    "plan_meal",
    "daily_briefing",
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
    "suggest_meal",
    "log_meal",
    "plan_meal",
    "daily_briefing",
    "help",
    "greeting",
    "thanks",
    "unknown",
}


@dataclass(frozen=True)
class Intent:
    name: IntentName
    item: str | None = None
    due_date: str | None = None
    category: str | None = None


SYSTEM_PROMPT = """You parse household assistant commands for a Telegram bot.
Users write in casual, messy natural language — typos and unclear phrasing are normal.
Return ONLY valid JSON with this shape:
{"intents":[{"intent":"add_todo|complete_todo|remove_todo|list_todos|suggest_meal|log_meal|plan_meal|daily_briefing|help|greeting|thanks|unknown","item":string|null,"due_date":"YYYY-MM-DD"|null,"category":"shopping|household|admin|maintenance|personal|general"|null}, ...]}

Rules:
- Interpret intent generously from context; do not require exact command wording.
- Return one or more intents if the user asks for multiple things in one message.
- add_todo: add a task or shopping item; extract due_date and category when mentioned
- complete_todo: mark an item as done or bought
- remove_todo: remove an item from the list without marking done
- list_todos: show open items
- suggest_meal: user asks what to eat, meal ideas, dinner/breakfast suggestions
- log_meal: user says what they ate (e.g. "I had pasta for dinner")
- plan_meal: user decides to cook something (e.g. "let's make curry with rice tonight") — add missing ingredients to shopping list
- daily_briefing: user asks for today's overview (tasks due, shopping, meal idea)
- help, greeting, thanks: social intents
- unknown: only if truly impossible to map
- Categories: shopping (groceries), household (cleaning/trash), admin (rent/bills), maintenance, personal (work/errands), general
- Infer due dates from phrases like "until tomorrow", "by friday", "due next week"
- Item text should be a short task label, not the full original sentence
- For add_todo with quotes, item is only the quoted text

Natural language examples:
"hello" -> {"intents":[{"intent":"greeting","item":null,"due_date":null,"category":null}]}
"add \"find a loving girl friend\" to my todo list until tomorrow" -> {"intents":[{"intent":"add_todo","item":"find a loving girl friend","due_date":"YYYY-MM-DD","category":"personal"}]}
"I have a todo untill tomorrow where I have to do a power bi report for work" -> {"intents":[{"intent":"add_todo","item":"power bi report","due_date":"YYYY-MM-DD","category":"personal"}]}
"what should I eat for dinner?" -> {"intents":[{"intent":"suggest_meal","item":"dinner","due_date":null,"category":null}]}
"let's make curry with rice tonight" -> {"intents":[{"intent":"plan_meal","item":"curry with rice","due_date":null,"category":null}]}
"what's on today?" -> {"intents":[{"intent":"daily_briefing","item":null,"due_date":null,"category":null}]}
"could you show me the shopping list" -> {"intents":[{"intent":"list_todos","item":null,"due_date":null,"category":null}]}
"""


def _build_add_intent(raw_item: str, default_category: str | None = None) -> Intent:
    text, category_hint = parse_category_hint(raw_item)
    text, due_date = parse_due_date(text)
    text = re.sub(r"\s+", " ", text).strip(" ,:-")
    return Intent(
        name="add_todo",
        item=text or None,
        due_date=due_date,
        category=infer_category(text, category_hint or default_category),
    )


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

    item = _normalize_item(data.get("item"))
    due_date = data.get("due_date")
    category = data.get("category")
    if intent_name == "add_todo" and item:
        item, parsed_due = parse_due_date(item)
        due_date = due_date or parsed_due
        item, category_hint = parse_category_hint(item)
        category = infer_category(item, category or category_hint)

    return Intent(
        name=intent_name,
        item=item,
        due_date=due_date,
        category=category,
    )


def _intents_from_payload(parsed: dict | list) -> list[Intent]:
    if isinstance(parsed, list):
        return [_intent_from_dict(item) for item in parsed if isinstance(item, dict)]

    if "intents" in parsed and isinstance(parsed["intents"], list):
        return [_intent_from_dict(item) for item in parsed["intents"] if isinstance(item, dict)]

    if "intent" in parsed:
        return [_intent_from_dict(parsed)]

    return [Intent(name="unknown")]


async def _parse_with_openrouter(text: str, settings: Settings) -> list[Intent]:
    from datetime import date

    today = date.today()
    system_prompt = (
        f"{SYSTEM_PROMPT}\nToday is {today.isoformat()} ({today.strftime('%A')}). "
        "Use this when resolving relative dates like tomorrow or friday."
    )
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
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
    parts = re.split(r"(?<=[.!?])\s+|[\n;]+|\s*,\s*(?=please\s)", text.strip(), flags=re.IGNORECASE)
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

    if re.search(
        r"(?:show(?: me)?(?: everything| the)?(?: on)?(?: the)? (?:list|shopping list|todo list|tasks)|"
        r"share (?:the )?(?:current )?(?:shopping )?list|what(?:'s| is) on (?:the |my )?(?:list|shopping list|todo list)|"
        r"^list(?: items| todos)?$)",
        normalized,
    ):
        return [Intent(name="list_todos")]

    if re.search(
        r"(?:what(?:'s| is) on today|daily briefing|morning briefing|what do i need to do today|"
        r"what(?:'s| is) on for today|today's briefing|brief me)",
        normalized,
    ):
        return [Intent(name="daily_briefing")]

    if re.search(
        r"(?:let's|lets|we(?:'ll| will)|i want to|going to|gonna)\s+(?:make|cook|prepare)\s+",
        normalized,
    ) or re.match(r"^(?:cook|make|prepare)\s+", normalized):
        meal_name = normalized
        for pattern in (
            r"(?:let's|lets|we(?:'ll| will)|i want to|going to|gonna)\s+(?:make|cook|prepare)\s+(.+)$",
            r"^(?:cook|make|prepare)\s+(.+)$",
        ):
            match = re.search(pattern, normalized)
            if match:
                meal_name = match.group(1).strip()
                break
        return [Intent(name="plan_meal", item=meal_name)]

    if re.search(
        r"(?:what should i eat|what can i eat|what to eat|meal idea|dinner idea|lunch idea|breakfast idea|"
        r"suggest (?:a )?(?:meal|food|dinner|lunch|breakfast)|what(?:'s| is) for (?:dinner|lunch|breakfast))",
        normalized,
    ):
        meal_type = None
        for candidate in ("breakfast", "lunch", "dinner", "snack"):
            if candidate in normalized:
                meal_type = candidate
                break
        return [Intent(name="suggest_meal", item=meal_type)]

    if re.search(r"\b(i had|i ate|we had|we ate)\b", normalized):
        return [Intent(name="log_meal", item=normalized)]

    need_match = re.match(r"^(?:please |could u |could you |also |and )?we need\s+(.+)$", normalized)
    if need_match:
        return [_build_add_intent(item) for item in _split_items(need_match.group(1))]

    add_match = re.search(
        r"^(?:please |could u |could you |also |and )?"
        r"(?:(?:add|put)\s+(.+?)\s+(?:to|on|off)\s+(?:the\s+)?(?:list|shopping list|todo list)\s*$|"
        r"need\s+(?:to get|more)\s+(.+?)$)",
        normalized,
    )
    if add_match:
        item = next(group for group in add_match.groups() if group)
        return [_build_add_intent(item, default_category="shopping")]

    task_add_match = re.match(
        r"^(?:please |could u |could you |also |and )?add\s+(.+)$",
        normalized,
    )
    if task_add_match:
        return [_build_add_intent(task_add_match.group(1))]

    remove_match = re.search(
        r"^(?:please |also |and |after )?"
        r"(?:(?:remove|delete|deleting)\s+(?:the\s+)?(?:todo\s+)?(.+?)(?:\s+(?:from|off)\s+(?:the\s+)?(?:list|shopping list|todo list))?$|"
        r"(?:we )?(?:do not|don't|no longer)\s+need\s+(.+?)(?:\s+any(?:\s+)?(?:longer|more))?$)",
        normalized,
    )
    if remove_match:
        item = next(group for group in remove_match.groups() if group)
        return [Intent(name="remove_todo", item=_normalize_item(item))]

    complete_match = re.search(
        r"^(?:please |also |and )?(?:check off|mark|done with|bought|got)\s+(?:the\s+)?(.+?)(?:\s+because\b.*)?$",
        normalized,
    )
    if complete_match:
        return [Intent(name="complete_todo", item=_normalize_item(complete_match.group(1)))]

    return []


def _parse_with_rules(text: str) -> list[Intent]:
    cleaned = sanitize_command(text)

    structured = try_parse_structured_add(cleaned)
    if structured:
        item, due_date, category = structured
        return [Intent(name="add_todo", item=item, due_date=due_date, category=category)]

    if not re.match(r"^(?:add|put|remove|delete|show|list|what)", cleaned, re.IGNORECASE):
        natural = try_parse_natural_add(cleaned)
        if natural:
            return [
                Intent(
                    name="add_todo",
                    item=natural.item,
                    due_date=natural.due_date,
                    category=natural.category,
                )
            ]

    intents: list[Intent] = []
    for clause in _split_clauses(cleaned):
        normalized = clause.strip().lower().rstrip(".!?")
        intents.extend(_parse_clause_intents(normalized))

    return intents or [Intent(name="unknown")]
