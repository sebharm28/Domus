import re
from datetime import date, datetime, timedelta
from pathlib import Path

from domus import db, food_db
from domus.db import list_open_todos
from domus.shopping import format_shopping_display, shopping_item_name


def infer_meal_type(text: str) -> str | None:
    lowered = text.lower()
    for meal_type in ("breakfast", "lunch", "dinner", "snack"):
        if meal_type in lowered:
            return meal_type
    if "morning" in lowered:
        return "breakfast"
    if "noon" in lowered or "midday" in lowered:
        return "lunch"
    if "evening" in lowered or "tonight" in lowered:
        return "dinner"
    hour = datetime.now().hour
    if hour < 11:
        return "breakfast"
    if hour < 15:
        return "lunch"
    return "dinner"


def _shopping_items(db_path: Path) -> set[str]:
    todos = list_open_todos(db_path, category="shopping")
    return {shopping_item_name(todo).lower() for todo in todos}


def _has_ingredient(ingredient: str, shopping_items: set[str]) -> bool:
    ingredient_lower = ingredient.lower()
    return any(
        ingredient_lower in item or item in ingredient_lower
        for item in shopping_items
    )


def _compare_ingredients(
    ingredients: list[str],
    shopping_items: set[str],
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    already_have: list[str] = []
    for ingredient in ingredients:
        if _has_ingredient(ingredient, shopping_items):
            already_have.append(ingredient)
        else:
            missing.append(ingredient)
    return missing, already_have


def _extract_missing_meal_query(text: str) -> str | None:
    normalized = text.strip().lower().rstrip(".!?")
    patterns = [
        r"what(?:'s| is) missing(?: for| from)?\s+(.+)$",
        r"what do (?:we|i) need(?: to buy)? for\s+(.+)$",
        r"what(?:'s| is) missing for (?:dinner|lunch|breakfast|tonight)\??$",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            if match.lastindex:
                return match.group(1).strip(" .")
            return normalized.split()[-1] if "dinner" in normalized or "lunch" in normalized else "dinner"
    if re.search(r"missing for (?:dinner|tonight)|need for (?:dinner|tonight)", normalized):
        return "dinner"
    return None


def _week_end(today: date) -> date:
    return today + timedelta(days=(6 - today.weekday()))


def _extract_meal_name(text: str) -> str | None:
    normalized = text.strip().lower().rstrip(".!?")
    patterns = [
        r"(?:let's|lets|we(?:'ll| will)|i want to|going to|gonna)\s+(?:make|cook|prepare)\s+(.+)$",
        r"^(?:cook|make|prepare)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            name = match.group(1).strip()
            name = re.sub(
                r"\s+for\s+(?:breakfast|lunch|dinner|snack|tonight|today)\s*$",
                "",
                name,
            )
            name = re.sub(r"\s+(?:for\s+)?(?:tonight|today)\s*$", "", name)
            return name.strip(" .")
    return None


def format_meal_suggestions(
    foods: list[food_db.Food],
    meal_type: str,
    shopping_items: set[str],
) -> str:
    if not foods:
        return "I don't have meal ideas in the database yet."

    lines = [f"Here are some {meal_type} ideas:"]
    for food in foods:
        line = f"• {food.name}"
        if food.prep_time_min:
            line += f" (~{food.prep_time_min} min)"
        if food.notes:
            line += f" — {food.notes}"
        available = [item for item in food.ingredients if _has_ingredient(item, shopping_items)]
        if available:
            line += f"\n  You already have: {', '.join(available)}"
        lines.append(line)
    lines.append("\nSay e.g. \"Domus, let's make pasta aglio e olio tonight\" to add missing ingredients.")
    return "\n".join(lines)


def handle_suggest_meal(
    text: str,
    db_path: Path,
    meal_type: str | None = None,
    *,
    profiles: list | None = None,
) -> str:
    resolved_type = meal_type or infer_meal_type(text) or "dinner"
    foods = food_db.suggest_foods(
        db_path,
        meal_type=resolved_type,
        count=3,
        profiles=profiles,
    )
    if not foods and profiles:
        return (
            f"I couldn't find {resolved_type} ideas that fit everyone's preferences. "
            "Try updating profiles or broadening diet settings."
        )
    return format_meal_suggestions(foods, resolved_type, _shopping_items(db_path))


def handle_plan_meal(text: str, db_path: Path, created_by: str, meal_name: str | None = None) -> str:
    raw = (meal_name or text).strip()
    resolved_name = _extract_meal_name(raw) or raw
    if not resolved_name:
        return 'Tell me what you want to cook, e.g. "let\'s make curry with rice tonight".'

    food = food_db.find_food_by_name(db_path, resolved_name)
    if food is None:
        return f'I could not find "{resolved_name}" in the meal database yet.'

    shopping_items = _shopping_items(db_path)
    missing, already_have = _compare_ingredients(food.ingredients, shopping_items)

    for ingredient in missing:
        db.add_todo(db_path, ingredient, created_by, category="shopping")

    lines = [f'Planning "{food.name}":']
    if missing:
        lines.append(f"Added to the shopping list: {', '.join(missing)}.")
    else:
        lines.append("You already have everything on the list — nothing new to add.")

    if already_have:
        lines.append(f"You already have: {', '.join(already_have)}.")

    return " ".join(lines)


def _resolve_food_for_missing(
    db_path: Path,
    query: str | None,
) -> food_db.Food | None:
    if not query:
        return None

    lowered = query.strip().lower()
    if lowered in {"dinner", "lunch", "breakfast", "tonight", "today"}:
        today = date.today().isoformat()
        entry = food_db.get_meal_plan_for_day(db_path, today)
        if entry and entry.food_id:
            foods = food_db.list_foods(db_path)
            return next((food for food in foods if food.id == entry.food_id), None)
        if entry:
            return food_db.find_food_by_name(db_path, entry.dish)
        meal_type = infer_meal_type(lowered) or "dinner"
        suggestions = food_db.suggest_foods(db_path, meal_type=meal_type, count=1)
        return suggestions[0] if suggestions else None

    return food_db.find_food_by_name(db_path, query)


def handle_missing_ingredients(
    text: str,
    db_path: Path,
    meal_name: str | None = None,
) -> str:
    query = meal_name or _extract_missing_meal_query(text) or text.strip()
    food = _resolve_food_for_missing(db_path, query)
    if food is None:
        return (
            'Tell me which meal to check, e.g. "what\'s missing for pasta aglio e olio?" '
            'or plan the week first with "plan meals for this week".'
        )

    shopping_items = _shopping_items(db_path)
    missing, already_have = _compare_ingredients(food.ingredients, shopping_items)

    if not missing:
        have_text = f" You already have: {', '.join(already_have)}." if already_have else ""
        return f'For "{food.name}", you have everything on the list.{have_text}'

    lines = [f'For "{food.name}", you still need: {", ".join(missing)}.']
    if already_have:
        lines.append(f"You already have: {', '.join(already_have)}.")
    return " ".join(lines)


def handle_show_meal_plan(db_path: Path, today: date | None = None) -> str:
    today = today or date.today()
    end = _week_end(today)
    entries = food_db.get_meal_plan_range(db_path, today.isoformat(), end.isoformat())
    if not entries:
        return 'No meal plan yet. Try "plan meals for this week".'

    lines = [f"Meal plan ({today.strftime('%a %d %b')} – {end.strftime('%a %d %b')}):"]
    for entry in entries:
        day = date.fromisoformat(entry.day)
        lines.append(f"• {day.strftime('%a')}: {entry.dish}")
    return "\n".join(lines)


def handle_plan_week(
    db_path: Path,
    created_by: str,
    today: date | None = None,
    *,
    profiles: list | None = None,
) -> str:
    today = today or date.today()
    end = _week_end(today)
    food_db.clear_meal_plan_range(db_path, today.isoformat(), end.isoformat())

    planned: list[food_db.MealPlanEntry] = []
    used_food_ids: set[int] = set()
    day = today

    while day <= end:
        suggestions = food_db.suggest_foods(
            db_path,
            meal_type="dinner",
            count=1,
            exclude_ids=used_food_ids,
            profiles=profiles,
        )
        if not suggestions:
            break
        food = suggestions[0]
        used_food_ids.add(food.id)
        entry = food_db.save_meal_plan_entry(db_path, day.isoformat(), food)
        planned.append(entry)
        day += timedelta(days=1)

    if not planned:
        return "I couldn't build a meal plan — no dinner ideas in the database."

    all_ingredients: list[str] = []
    seen: set[str] = set()
    for entry in planned:
        for ingredient in entry.ingredients:
            key = ingredient.lower()
            if key not in seen:
                seen.add(key)
                all_ingredients.append(ingredient)

    shopping_items = _shopping_items(db_path)
    missing, _ = _compare_ingredients(all_ingredients, shopping_items)
    for ingredient in missing:
        db.add_todo(db_path, ingredient, created_by, category="shopping")
        shopping_items.add(ingredient.lower())

    lines = [handle_show_meal_plan(db_path, today=today)]
    if missing:
        lines.append(f"\nAdded {len(missing)} item(s) to the shopping list: {', '.join(missing)}.")
    else:
        lines.append("\nYour shopping list already covers this week's meals.")
    return "\n".join(lines)


def handle_log_meal(text: str, db_path: Path, created_by: str) -> str:
    match = re.search(
        r"(?:i had|i ate|we had|we ate|had|ate)\s+(.+?)(?:\s+for\s+(breakfast|lunch|dinner|snack))?$",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return "Tell me what you ate, e.g. \"I had pasta for dinner\"."

    food_name = match.group(1).strip(" .!")
    food = food_db.find_food_by_name(db_path, food_name)
    if food is None:
        return f'I could not find "{food_name}" in the meal database yet.'
    food_db.log_meal(db_path, food.id, created_by)
    return f'Noted — you had "{food.name}". I will suggest something different next time.'
