import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from domus.categories import infer_category
from domus.config import Settings
from domus.dates import parse_category_hint, parse_due_date, extract_due_date_from_message, parse_apartment_hint, parse_assignee_hint
from domus.memory import build_openrouter_context
from domus.redaction import redact_for_llm
from domus.natural_language import try_parse_natural_add
from domus.meals import _extract_missing_meal_query, normalize_plan_meal_name, parse_add_recipe_phrase
from domus.recurrence import parse_reminder_phrase
from domus.relative_reminders import parse_relative_reminder_phrase
from domus.structured_add import try_parse_structured_add
from domus.text_utils import sanitize_command

logger = logging.getLogger(__name__)

IntentName = Literal[
    "add_todo",
    "complete_todo",
    "remove_todo",
    "update_todo",
    "list_todos",
    "export_list",
    "clear_shopping_list",
    "clear_todos",
    "suggest_meal",
    "log_meal",
    "plan_meal",
    "plan_week",
    "show_meal_plan",
    "missing_ingredients",
    "add_recurring_reminder",
    "add_relative_reminder",
    "list_reminders",
    "remove_reminder",
    "daily_briefing",
    "update_profile",
    "show_profile",
    "log_preference",
    "log_dispreference",
    "add_recipe",
    "who_did_what",
    "cancel_timer",
    "undo",
    "snooze_reminder",
    "help",
    "greeting",
    "thanks",
    "unknown",
]

VALID_INTENTS = {
    "add_todo",
    "complete_todo",
    "remove_todo",
    "update_todo",
    "list_todos",
    "export_list",
    "clear_shopping_list",
    "clear_todos",
    "suggest_meal",
    "log_meal",
    "plan_meal",
    "plan_week",
    "show_meal_plan",
    "missing_ingredients",
    "add_recurring_reminder",
    "add_relative_reminder",
    "list_reminders",
    "remove_reminder",
    "daily_briefing",
    "update_profile",
    "show_profile",
    "log_preference",
    "log_dispreference",
    "add_recipe",
    "who_did_what",
    "cancel_timer",
    "undo",
    "snooze_reminder",
    "help",
    "greeting",
    "thanks",
    "unknown",
}


@dataclass(frozen=True)
class Intent:
    name: IntentName
    item: str | None = None
    new_item: str | None = None
    due_date: str | None = None
    category: str | None = None
    apartment: str | None = None
    assignee: str | None = None
    recurrence: str | None = None
    delay_minutes: int | None = None


SYSTEM_PROMPT = """You parse household assistant commands for a Telegram bot.
Users write in casual, messy natural language — typos and unclear phrasing are normal.
Return ONLY valid JSON with this shape:
{"intents":[{"intent":"add_todo|complete_todo|remove_todo|update_todo|list_todos|export_list|clear_shopping_list|clear_todos|suggest_meal|log_meal|plan_meal|plan_week|show_meal_plan|missing_ingredients|add_recipe|add_recurring_reminder|list_reminders|remove_reminder|daily_briefing|help|greeting|thanks|unknown","item":string|null,"new_item":string|null,"due_date":"YYYY-MM-DD"|null,"category":"shopping|household|admin|maintenance|personal|general|breakfast|lunch|dinner|snack"|null,"recurrence":"daily|weekly:monday|monthly:1"|null}, ...]}

Rules:
- Interpret intent generously from context; do not require exact command wording.
- Return one or more intents if the user asks for multiple things in one message.
- add_todo: add a task or shopping item; extract due_date and category when mentioned
- complete_todo: mark an item as done or bought
- remove_todo: remove an item from the list without marking done
- update_todo: fix due date, rename, or recategorize a recent task
- update_profile: save user preferences (diet, apartment, allergies, dislikes)
- log_preference: user says they like or love a food (e.g. "I really like currywurst")
- show_profile: show saved preferences for the speaker
- list_todos: show open items
- export_list: export the list as plain text or CSV (item field "csv" for CSV format)
- clear_shopping_list: wipe all open shopping items
- clear_todos: wipe all open tasks (not just shopping)
- suggest_meal: user asks what to eat, meal ideas, dinner/breakfast suggestions
- log_meal: user says what they ate (e.g. "I had pasta for dinner")
- plan_meal: user decides to cook something (e.g. "let's make curry with rice tonight") — add missing ingredients to shopping list
- plan_week: user wants a dinner plan for the rest of the week with shopping list updates
- show_meal_plan: user asks to see the current weekly meal plan
- missing_ingredients: user asks what's still needed for a meal (read-only, no list changes)
- add_recipe: user saves a custom recipe with ingredients (e.g. "add meal grilled cheese: bread, cheese, butter"); item=recipe name, new_item=comma-separated ingredients, category=meal type when mentioned
- add_recurring_reminder: repeating household reminders (weekly trash, monthly rent)
- list_reminders: show recurring reminders and pending one-shot timers
- snooze_reminder: push a due task or timer to a later time
- remove_reminder: delete a recurring reminder
- daily_briefing: user asks for today's overview (tasks due, shopping, meal idea)
- help, greeting, thanks: social intents
- unknown: only if truly impossible to map
- Categories: shopping (groceries), household (cleaning/trash), admin (rent/bills), maintenance, personal (work/errands), general
- Infer due dates from phrases like "until tomorrow", "by friday", "due next week"
- Item text should be a short task label, not the full original sentence
- For add_todo with quotes, item is only the quoted text

Natural language examples:
"hello" -> {"intents":[{"intent":"greeting","item":null,"due_date":null,"category":null,"recurrence":null}]}
"add pay rent by friday category admin" -> {"intents":[{"intent":"add_todo","item":"pay rent","due_date":"YYYY-MM-DD","category":"admin","recurrence":null}]}
"I said the task is for tomorrow" -> {"intents":[{"intent":"update_todo","item":null,"due_date":"YYYY-MM-DD","category":null,"recurrence":null}]}
"I have a todo untill tomorrow where I have to do a power bi report for work" -> {"intents":[{"intent":"add_todo","item":"power bi report","due_date":"YYYY-MM-DD","category":"personal"}]}
"what should I eat for dinner?" -> {"intents":[{"intent":"suggest_meal","item":"dinner","due_date":null,"category":null}]}
"let's make curry with rice tonight" -> {"intents":[{"intent":"plan_meal","item":"curry with rice","due_date":null,"category":null,"recurrence":null}]}
"plan meals for this week" -> {"intents":[{"intent":"plan_week","item":null,"due_date":null,"category":null,"recurrence":null}]}
"what's missing for dinner?" -> {"intents":[{"intent":"missing_ingredients","item":"dinner","due_date":null,"category":null,"recurrence":null}]}
"add meal grilled cheese: bread, cheese, butter" -> {"intents":[{"intent":"add_recipe","item":"grilled cheese","new_item":"bread, cheese, butter","due_date":null,"category":"dinner","recurrence":null}]}
"remind us every Tuesday to take out the trash" -> {"intents":[{"intent":"add_recurring_reminder","item":"take out the trash","due_date":null,"category":null,"recurrence":"weekly:tuesday"}]}
"what's on today?" -> {"intents":[{"intent":"daily_briefing","item":null,"due_date":null,"category":null,"recurrence":null}]}
"could you show me the shopping list" -> {"intents":[{"intent":"list_todos","item":null,"due_date":null,"category":null}]}
"""


def _default_list_category(normalized: str) -> str | None:
    if "shopping list" in normalized or "shopping" in normalized.split("list")[0]:
        return "shopping"
    return None


def _looks_like_add_message(normalized: str) -> bool:
    return bool(
        re.search(
            r"\b(?:add|put)\s+.+?\s+(?:to|on)\s+(?:the\s+)?(?:list|todo|shopping)",
            normalized,
        )
        or re.search(r"\bwe need\s+", normalized)
    )


def _parse_correction_intents(text: str) -> list[Intent] | None:
    normalized = sanitize_command(text).strip().lower().rstrip(".!?")
    due = extract_due_date_from_message(text)

    if _looks_like_add_message(normalized) and not re.search(
        r"\bi (?:said|meant)\b", normalized
    ):
        return None

    if re.search(
        r"\b(?:i said|i meant)(?: to say)?(?: that)?(?: the task is| it is| that's)?(?: for)?\s*tomorrow\b",
        normalized,
    ) or re.search(r"\b(?:the task is|it is|that's|task is) for tomorrow\b", normalized):
        return [Intent(name="update_todo", due_date=due)]

    if re.search(r"\b(?:have to|need to) (?:do it|do that|do this) tomorrow\b", normalized):
        return [Intent(name="update_todo", due_date=due)]

    meant_match = re.search(r"\bi meant (.+)$", normalized)
    if meant_match:
        item = _normalize_item(meant_match.group(1))
        return [Intent(name="update_todo", item=item, due_date=due)]

    return None


def _parse_edit_intents(text: str) -> list[Intent] | None:
    normalized = sanitize_command(text).strip().lower().rstrip(".!?")
    due = extract_due_date_from_message(text)

    if re.search(
        r"\b(?:actually|that(?:'s| is)?|it(?:'s| is)?)\s+(?:due |for )?tomorrow\b",
        normalized,
    ):
        return [Intent(name="update_todo", due_date=due or extract_due_date_from_message("tomorrow"))]

    rename_match = re.search(
        r"\b(?:rename|change|call)\s+(?:that|it|the task)\s+(?:to|as)\s+(.+)$",
        normalized,
    )
    if rename_match:
        return [Intent(name="update_todo", new_item=_normalize_item(rename_match.group(1)))]

    category_match = re.search(
        r"\b(?:change|make|set)\s+(?:that|it|the task)\s+(?:to\s+)?(?:an?\s+)?"
        r"(?:category\s+)?(shopping|household|admin|maintenance|personal|general)\b",
        normalized,
    )
    if category_match:
        return [Intent(name="update_todo", category=category_match.group(1))]

    category_short = re.search(
        r"\b(?:that(?:'s| is)?|it(?:'s| is)?)\s+(?:an?\s+)?"
        r"(shopping|household|admin|maintenance|personal|general)\b",
        normalized,
    )
    if category_short:
        return [Intent(name="update_todo", category=category_short.group(1))]

    return None


def _parse_profile_intents(text: str) -> list[Intent] | None:
    normalized = sanitize_command(text).strip().lower().rstrip(".!?")

    if re.search(r"\b(?:my profile|who am i|show my profile)\b", normalized):
        return [Intent(name="show_profile")]

    diet_match = re.search(r"\bi(?:'m| am)\s+(vegetarian|vegan|pescatarian)\b", normalized)
    if diet_match:
        return [Intent(name="update_profile", item=diet_match.group(1), category="diet")]

    apartment_match = re.search(r"\bmy apartment is\s+(.+)$", normalized)
    if apartment_match:
        return [
            Intent(
                name="update_profile",
                item=_normalize_item(apartment_match.group(1)),
                category="apartment",
            )
        ]

    allergy_match = re.search(r"\bi(?:'m| am)?\s*allergic to\s+(.+)$", normalized)
    if allergy_match:
        return [
            Intent(
                name="update_profile",
                item=_normalize_item(allergy_match.group(1)),
                category="allergies",
            )
        ]

    dislike_match = re.search(r"\bi(?:'| do)? not like\s+(.+)$", normalized)
    if dislike_match:
        return [
            Intent(
                name="log_dispreference",
                item=_normalize_item(dislike_match.group(1)),
            )
        ]

    like_match = re.search(
        r"\bi(?: really| absolutely|)? (?:like|love|enjoy)\s+(.+)$",
        normalized,
    )
    if like_match:
        return [
            Intent(
                name="log_preference",
                item=_normalize_item(like_match.group(1)),
            )
        ]

    return None


def _merge_due_dates(text: str, intents: list[Intent]) -> list[Intent]:
    due = extract_due_date_from_message(text)
    if not due:
        return intents
    merged: list[Intent] = []
    for intent in intents:
        if intent.name == "add_todo" and intent.category == "shopping":
            merged.append(
                Intent(
                    name=intent.name,
                    item=intent.item,
                    new_item=intent.new_item,
                    due_date=None,
                    category=intent.category,
                    apartment=intent.apartment,
                    recurrence=intent.recurrence,
                    delay_minutes=intent.delay_minutes,
                )
            )
        elif intent.name == "add_todo" and not intent.due_date:
            merged.append(
                Intent(
                    name=intent.name,
                    item=intent.item,
                    new_item=intent.new_item,
                    due_date=due,
                    category=intent.category,
                    apartment=intent.apartment,
                    recurrence=intent.recurrence,
                    delay_minutes=intent.delay_minutes,
                )
            )
        else:
            merged.append(intent)
    return merged


def _build_add_intent(raw_item: str, default_category: str | None = None) -> Intent:
    text, category_hint = parse_category_hint(raw_item)
    text, apartment_hint = parse_apartment_hint(text)
    text, assignee_hint = parse_assignee_hint(text)
    text, due_date = parse_due_date(text)
    text = re.sub(r"\s+", " ", text).strip(" ,:-")
    return Intent(
        name="add_todo",
        item=text or None,
        due_date=due_date,
        category=infer_category(text, category_hint or default_category),
        apartment=apartment_hint,
        assignee=assignee_hint,
    )


def _parse_snooze_intents(text: str) -> list[Intent] | None:
    normalized = sanitize_command(text).strip().lower().rstrip(".!?")
    if not re.search(r"\bsnooze\b", normalized):
        return None
    from domus.snooze import parse_snooze_phrase

    item_hint, due_date, delay_minutes = parse_snooze_phrase(normalized)
    if due_date is None and delay_minutes is None:
        return None
    return [
        Intent(
            name="snooze_reminder",
            item=item_hint,
            due_date=due_date,
            delay_minutes=delay_minutes,
        )
    ]


def _parse_relative_intents(text: str) -> list[Intent] | None:
    normalized = sanitize_command(text).strip().lower().rstrip(".!?")
    relative = parse_relative_reminder_phrase(normalized)
    if relative:
        task, delay_minutes = relative
        return [Intent(name="add_relative_reminder", item=task, delay_minutes=delay_minutes)]
    return None


def _finalize_add_intents(intents: list[Intent]) -> list[Intent]:
    finalized: list[Intent] = []
    for intent in intents:
        if intent.name != "add_todo" or not intent.item:
            finalized.append(intent)
            continue
        text, apartment = parse_apartment_hint(intent.item)
        text, assignee = parse_assignee_hint(text)
        text, category_hint = parse_category_hint(text)
        text, due_date = parse_due_date(text)
        text = re.sub(r"\s+", " ", text).strip(" ,:-")
        finalized.append(
            Intent(
                name="add_todo",
                item=text or None,
                due_date=None if (intent.category or infer_category(text, category_hint)) == "shopping" else (intent.due_date or due_date),
                category=intent.category or infer_category(text, category_hint),
                apartment=intent.apartment or apartment,
                assignee=intent.assignee or assignee,
            )
        )
    return finalized


def _rules_resolve(text: str) -> list[Intent]:
    for parser in (
        _parse_correction_intents,
        _parse_edit_intents,
        _parse_profile_intents,
        _parse_snooze_intents,
        _parse_relative_intents,
    ):
        parsed = parser(text)
        if parsed:
            return parsed
    return _parse_with_rules(text)


def _has_actionable_intent(intents: list[Intent]) -> bool:
    return bool(intents) and not all(intent.name == "unknown" for intent in intents)


async def parse_intents(
    text: str,
    settings: Settings,
    *,
    private_mode: bool = False,
    db_path: Path | None = None,
    chat_id: int | None = None,
    user_id: int | None = None,
) -> list[Intent]:
    rule_intents = _rules_resolve(text)
    if _has_actionable_intent(rule_intents):
        logger.info("Rules parsed %d intent(s) for %r", len(rule_intents), text)
        return rule_intents

    if private_mode:
        logger.info("Private mode: skipping OpenRouter for %r", text)
        return rule_intents or [Intent(name="unknown")]

    if settings.openrouter_api_key:
        try:
            safe_text, _ = redact_for_llm(text, settings)
            memory_context = ""
            if db_path is not None:
                memory_context = build_openrouter_context(
                    db_path,
                    chat_id=chat_id,
                    user_id=user_id,
                )
            intents = await _parse_with_openrouter(
                safe_text,
                settings,
                memory_context=memory_context,
            )
            if intents and _has_actionable_intent(intents):
                logger.info("OpenRouter parsed %d intent(s) for %r", len(intents), text)
                return intents
            logger.warning("OpenRouter returned unknown; using rules for %r", text)
        except Exception:
            logger.exception("OpenRouter intent parsing failed; using rules")
    return rule_intents


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
        new_item=_normalize_item(data.get("new_item")),
        due_date=due_date,
        category=category,
        apartment=data.get("apartment"),
        recurrence=data.get("recurrence"),
        delay_minutes=data.get("delay_minutes"),
    )


def _intents_from_payload(parsed: dict | list) -> list[Intent]:
    if isinstance(parsed, list):
        return [_intent_from_dict(item) for item in parsed if isinstance(item, dict)]

    if "intents" in parsed and isinstance(parsed["intents"], list):
        return [_intent_from_dict(item) for item in parsed["intents"] if isinstance(item, dict)]

    if "intent" in parsed:
        return [_intent_from_dict(parsed)]

    return [Intent(name="unknown")]


async def _parse_with_openrouter(
    text: str,
    settings: Settings,
    *,
    memory_context: str = "",
) -> list[Intent]:
    from datetime import date

    today = date.today()
    system_prompt = (
        f"{SYSTEM_PROMPT}\nToday is {today.isoformat()} ({today.strftime('%A')}). "
        "Use this when resolving relative dates like tomorrow or friday."
    )
    if memory_context:
        system_prompt += f"\n\n{memory_context}"
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


def _parse_add_recipe_intents(normalized: str) -> list[Intent] | None:
    parsed = parse_add_recipe_phrase(normalized)
    if not parsed:
        return None
    name, ingredients, meal_type = parsed
    return [
        Intent(
            name="add_recipe",
            item=name,
            new_item="|".join(ingredients),
            category=meal_type,
        )
    ]


def _parse_meal_suggest_intents(normalized: str) -> list[Intent] | None:
    if re.search(
        r"(?:what should (?:we|i) (?:cook|make|eat)|"
        r"what (?:are we|should we) (?:cooking|making|having)(?: for)?|"
        r"(?:make|give)(?: me)? a recommendation for|"
        r"recommend(?:ation)?(?: for)?|"
        r"what(?:'s| is) for (?:dinner|lunch|breakfast)(?: tomorrow)?|"
        r"meal ideas?(?: for)?|"
        r"what (?:can|should) we (?:have|eat)(?: for)?)",
        normalized,
    ):
        meal_type = None
        for candidate in ("breakfast", "lunch", "dinner", "snack"):
            if candidate in normalized:
                meal_type = candidate
                break
        return [Intent(name="suggest_meal", item=meal_type)]
    return None


def _parse_clear_intents(normalized: str) -> list[Intent] | None:
    if re.search(r"(?:clear|wipe|empty)\s+(?:the\s+)?shopping\s+list", normalized):
        return [Intent(name="clear_shopping_list")]
    if re.search(
        r"(?:clear|wipe|empty)\s+(?:the\s+)?(?:(?:todo|to-do|task)s?\s*)?list\b|"
        r"(?:clear|wipe|empty)\s+(?:all\s+)?(?:my\s+)?(?:todos?|tasks)\b",
        normalized,
    ):
        return [Intent(name="clear_todos")]
    return None


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

    relative = parse_relative_reminder_phrase(normalized)
    if relative:
        task, delay_minutes = relative
        return [Intent(name="add_relative_reminder", item=task, delay_minutes=delay_minutes)]

    recurring = parse_reminder_phrase(normalized)
    if recurring:
        task, recurrence = recurring
        return [Intent(name="add_recurring_reminder", item=task, recurrence=recurrence)]

    if re.search(
        r"(?:show|list)(?: the)? recurring reminders|what reminders(?: are set)?|"
        r"where(?:'s| is) (?:the|my) reminder|"
        r"show my timers?|pending reminders?|"
        r"what timers? do i have",
        normalized,
    ):
        return [Intent(name="list_reminders")]

    if re.search(
        r"(?:cancel|delete|forget|never mind)(?: the| my| that)?(?: timer| reminder)|"
        r"cancel it(?: timer| reminder)?$",
        normalized,
    ):
        cancel_match = re.search(
            r"(?:cancel|delete|forget)(?: the| my)?(?: timer| reminder)(?: to| about| for)?\s+(.+)$",
            normalized,
        )
        hint = _normalize_item(cancel_match.group(1)) if cancel_match else None
        return [Intent(name="cancel_timer", item=hint)]

    if re.match(r"^(?:domus, )?undo(?: that| last action| last)?[!.?]*$", normalized):
        return [Intent(name="undo")]

    snooze_match = re.search(r"\bsnooze\b", normalized)
    if snooze_match:
        from domus.snooze import parse_snooze_phrase

        item_hint, due_date, delay_minutes = parse_snooze_phrase(normalized)
        if due_date is not None or delay_minutes is not None:
            return [
                Intent(
                    name="snooze_reminder",
                    item=item_hint,
                    due_date=due_date,
                    delay_minutes=delay_minutes,
                )
            ]

    remove_reminder_match = re.search(
        r"^(?:please |also |and )?(?:remove|delete)\s+(?:the )?(?:recurring )?reminder(?: for)?\s+(.+)$",
        normalized,
    )
    if remove_reminder_match:
        return [Intent(name="remove_reminder", item=_normalize_item(remove_reminder_match.group(1)))]

    remove_reminder_alt = re.search(
        r"^(?:please |also |and )?(?:remove|delete)\s+(?:the )?(.+?)\s+reminder$",
        normalized,
    )
    if remove_reminder_alt:
        return [Intent(name="remove_reminder", item=_normalize_item(remove_reminder_alt.group(1)))]

    if re.search(
        r"plan meals?(?: for)?(?: this| the)? week|weekly meal plan|plan dinners?(?: for)?(?: this| the)? week",
        normalized,
    ):
        return [Intent(name="plan_week")]

    if re.search(
        r"(?:show|what(?:'s| is))(?: the)? meal plan|meals? planned(?: for)?(?: this)? week|weekly meals?",
        normalized,
    ):
        return [Intent(name="show_meal_plan")]

    if re.search(
        r"who (?:did|completed|finished|checked off)(?: what| which tasks?)?(?: this week| lately| recently)?|"
        r"who(?:'s| is) been doing (?:the )?(?:tasks|chores)",
        normalized,
    ):
        return [Intent(name="who_did_what")]

    add_recipe = _parse_add_recipe_intents(normalized)
    if add_recipe:
        return add_recipe

    if re.search(
        r"what(?:'s| is) missing|what do (?:we|i) need(?: to buy)? for",
        normalized,
    ):
        query = _extract_missing_meal_query(normalized) or normalized
        return [Intent(name="missing_ingredients", item=query)]

    clear_intents = _parse_clear_intents(normalized)
    if clear_intents:
        return clear_intents

    if re.search(
        r"export(?: the)?(?: shopping)? list|download(?: the)? list|print(?: the)? list",
        normalized,
    ):
        export_format = "csv" if "csv" in normalized else "text"
        category = "shopping" if "shopping" in normalized else None
        return [Intent(name="export_list", item=export_format, category=category)]

    category_list = re.search(
        r"(?:show|what(?:'s| is) on)(?: the)?(?: my)? (?:the )?"
        r"(shopping|household|admin|maintenance|personal|general)(?:\s+list|\s+tasks)?",
        normalized,
    )
    if category_list:
        return [Intent(name="list_todos", category=category_list.group(1))]

    apartment_list = re.search(
        r"(?:show|what(?:'s| is) on).*?\bapartment\s+([a-z0-9]+)",
        normalized,
    )
    if apartment_list:
        return [Intent(name="list_todos", apartment=apartment_list.group(1))]

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

    meal_suggest = _parse_meal_suggest_intents(normalized)
    if meal_suggest:
        return meal_suggest

    if not re.search(
        r"\b(?:recommendation|recommend|suggest(?:ion)?|ideas?)\b",
        normalized,
    ) and (
        re.search(
            r"(?:let's|lets|we(?:'ll| will)|i want to|going to|gonna)\s+(?:make|cook|prepare)\s+",
            normalized,
        )
        or re.match(r"^(?:cook|make|prepare)\s+", normalized)
    ):
        meal_name = normalized
        for pattern in (
            r"(?:let's|lets|we(?:'ll| will)|i want to|going to|gonna)\s+(?:make|cook|prepare)\s+(.+)$",
            r"^(?:cook|make|prepare)\s+(.+)$",
        ):
            match = re.search(pattern, normalized)
            if match:
                meal_name = normalize_plan_meal_name(match.group(1))
                break
        else:
            meal_name = normalize_plan_meal_name(meal_name)
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
        r"(?:(?:add|put)\s+(.+?)\s+(?:to|on|off)\s+(?:the\s+)?(?:list|shopping list|todo list|to-do list)\s*$|"
        r"need\s+(?:to get|more)\s+(.+?)$)",
        normalized,
    )
    if add_match:
        item = next(group for group in add_match.groups() if group)
        category = _default_list_category(normalized)
        on_shopping_list = (
            category == "shopping"
            or "shopping list" in normalized
            or re.search(r"\bto the list\s*$", normalized)
        )
        if on_shopping_list and re.search(r"\s+and\s+|,", item):
            return [
                _build_add_intent(part, default_category="shopping")
                for part in _split_items(item)
            ]
        return [_build_add_intent(item, default_category=category)]

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
        if category == "shopping" and item and re.search(r"\s+and\s+|,", item):
            intents = [
                _build_add_intent(part, default_category="shopping")
                for part in _split_items(item)
            ]
        else:
            intents = [Intent(name="add_todo", item=item, due_date=due_date, category=category)]
        return _finalize_add_intents(_merge_due_dates(cleaned, intents))

    clear_intents = _parse_clear_intents(cleaned.lower())
    if clear_intents:
        return clear_intents

    snooze_intents = _parse_snooze_intents(cleaned)
    if snooze_intents:
        return snooze_intents

    if not re.match(
        r"^(?:please |could u |could you |)?(?:add|put|remove|delete|show|list|what|i said|i meant|remind)",
        cleaned,
        re.IGNORECASE,
    ):
        natural = try_parse_natural_add(cleaned)
        if natural:
            intents = [
                Intent(
                    name="add_todo",
                    item=natural.item,
                    due_date=natural.due_date,
                    category=natural.category,
                )
            ]
            return _finalize_add_intents(_merge_due_dates(cleaned, intents))

    intents: list[Intent] = []
    for clause in _split_clauses(cleaned):
        normalized = clause.strip().lower().rstrip(".!?")
        intents.extend(_parse_clause_intents(normalized))

    intents = _merge_due_dates(cleaned, intents)
    return _finalize_add_intents(intents) or [Intent(name="unknown")]
