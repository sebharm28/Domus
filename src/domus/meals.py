import re
from datetime import datetime
from pathlib import Path

from domus import food_db
from domus.db import list_open_todos


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
    return {todo.text.lower() for todo in todos}


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
        available = [item for item in food.ingredients if item.lower() in shopping_items]
        if available:
            line += f"\n  You already have: {', '.join(available)}"
        lines.append(line)
    lines.append("\nSay e.g. \"Domus, I had pasta for dinner\" to remember what you ate.")
    return "\n".join(lines)


def handle_suggest_meal(text: str, db_path: Path, meal_type: str | None = None) -> str:
    resolved_type = meal_type or infer_meal_type(text) or "dinner"
    foods = food_db.suggest_foods(db_path, meal_type=resolved_type, count=3)
    return format_meal_suggestions(foods, resolved_type, _shopping_items(db_path))


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
