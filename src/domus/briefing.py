from datetime import date, timedelta
from pathlib import Path

from domus import db, food_db
from domus.dates import format_due_date
from domus.db import Todo
from domus.meals import infer_meal_type
from domus.shopping import format_shopping_display


def _matches_apartment(todo: Todo, apartment: str | None) -> bool:
    if not apartment:
        return True
    if not todo.apartment:
        return False
    return todo.apartment.strip().lower() == apartment.strip().lower()


def _filter_apartment(todos: list[Todo], apartment: str | None) -> list[Todo]:
    if not apartment:
        return todos
    return [todo for todo in todos if _matches_apartment(todo, apartment)]


def _todo_line(todo: Todo) -> dict:
    return {
        "id": todo.id,
        "text": todo.text,
        "category": todo.category,
        "due_date": todo.due_date,
        "due_label": format_due_date(todo.due_date),
        "apartment": todo.apartment,
    }


def daily_briefing_payload(
    db_path: Path,
    *,
    apartment: str | None = None,
    today: date | None = None,
) -> dict:
    """Structured daily briefing for UI cards (optionally scoped to one apartment)."""
    today = today or date.today()
    due_today = _filter_apartment(db.list_todos_due_on(db_path, today), apartment)
    overdue = _filter_apartment(db.list_overdue_todos(db_path, today), apartment)
    held = _filter_apartment(db.list_held_reminders(db_path, today), apartment)
    if apartment:
        shopping = db.list_open_todos(db_path, category="shopping", apartment=apartment)
        open_todos = db.list_open_todos(db_path, apartment=apartment)
    else:
        shopping = db.list_open_todos(db_path, category="shopping")
        open_todos = db.list_open_todos(db_path)

    highlighted_ids = {todo.id for todo in due_today} | {todo.id for todo in overdue}
    other_open = [
        todo
        for todo in open_todos
        if todo.category != "shopping" and todo.id not in highlighted_ids
    ]

    meal_type = infer_meal_type("")
    suggestions = food_db.suggest_foods(db_path, meal_type=meal_type, count=1)
    meal_idea = None
    if suggestions:
        food = suggestions[0]
        meal_idea = {
            "name": food.name,
            "meal_type": meal_type,
            "prep_time_min": food.prep_time_min,
        }

    return {
        "date": today.isoformat(),
        "date_label": today.strftime("%a, %d %b %Y"),
        "apartment": apartment,
        "held": [_todo_line(todo) for todo in held[:5]],
        "due_today": [_todo_line(todo) for todo in due_today],
        "overdue": [_todo_line(todo) for todo in overdue],
        "shopping": {
            "count": len(shopping),
            "preview": [format_shopping_display(todo) for todo in shopping[:5]],
        },
        "other_open": {
            "count": len(other_open),
            "items": [_todo_line(todo) for todo in other_open[:3]],
        },
        "meal_idea": meal_idea,
        "text": build_daily_briefing(db_path, today=today, apartment=apartment),
    }


def build_daily_briefing(
    db_path: Path,
    today: date | None = None,
    *,
    apartment: str | None = None,
) -> str:
    today = today or date.today()
    due_today = _filter_apartment(db.list_todos_due_on(db_path, today), apartment)
    overdue = _filter_apartment(db.list_overdue_todos(db_path, today), apartment)
    held = _filter_apartment(db.list_held_reminders(db_path, today), apartment)
    if apartment:
        shopping = db.list_open_todos(db_path, category="shopping", apartment=apartment)
        open_todos = db.list_open_todos(db_path, apartment=apartment)
    else:
        shopping = db.list_open_todos(db_path, category="shopping")
        open_todos = db.list_open_todos(db_path)
    highlighted_ids = {todo.id for todo in due_today} | {todo.id for todo in overdue}
    other_open = [
        todo
        for todo in open_todos
        if todo.category != "shopping" and todo.id not in highlighted_ids
    ]

    header = f"Daily briefing — {today.strftime('%a, %d %b %Y')}"
    if apartment:
        header += f" ({apartment})"
    lines = [header, ""]

    if held:
        lines.append("Held overnight (quiet hours):")
        for todo in held[:5]:
            due = format_due_date(todo.due_date)
            lines.append(f"• {todo.text} — due: {due}")
        if len(held) > 5:
            lines.append(f"• …and {len(held) - 5} more")
        lines.append("")

    if due_today:
        lines.append("Due today:")
        for todo in due_today:
            lines.append(f"• {todo.text} ({todo.category})")
        lines.append("")
    else:
        lines.append("Due today: nothing scheduled.")
        lines.append("")

    if overdue:
        lines.append("Overdue:")
        for todo in overdue:
            lines.append(f"• {todo.text} — was due {format_due_date(todo.due_date)}")
        lines.append("")

    if shopping:
        preview = ", ".join(format_shopping_display(todo) for todo in shopping[:5])
        extra = f" (+{len(shopping) - 5} more)" if len(shopping) > 5 else ""
        lines.append(f"Shopping list ({len(shopping)}): {preview}{extra}")
        lines.append("")

    if other_open:
        lines.append(f"Other open tasks: {len(other_open)}")
        for todo in other_open[:3]:
            due = format_due_date(todo.due_date)
            lines.append(f"• {todo.text} — due: {due}")
        if len(other_open) > 3:
            lines.append(f"• …and {len(other_open) - 3} more")
        lines.append("")

    meal_type = infer_meal_type("")
    suggestions = food_db.suggest_foods(db_path, meal_type=meal_type, count=1)
    if suggestions:
        food = suggestions[0]
        line = f"{meal_type.title()} idea: {food.name}"
        if food.prep_time_min:
            line += f" (~{food.prep_time_min} min)"
        lines.append(line)

    return "\n".join(lines).strip()


def handle_daily_briefing(db_path: Path, *, apartment: str | None = None) -> str:
    return build_daily_briefing(db_path, apartment=apartment)


def build_evening_briefing(db_path: Path, today: date | None = None) -> str:
    today = today or date.today()
    tomorrow = today + timedelta(days=1)
    due_tomorrow = db.list_todos_due_on(db_path, tomorrow)
    meal_entry = food_db.get_meal_plan_for_day(db_path, tomorrow.isoformat())
    shopping = db.list_open_todos(db_path, category="shopping")

    lines = [f"Evening summary — {today.strftime('%a, %d %b %Y')}", ""]

    if due_tomorrow:
        lines.append(f"Due tomorrow ({tomorrow.strftime('%a, %d %b')}):")
        for todo in due_tomorrow:
            lines.append(f"• {todo.text} ({todo.category})")
        lines.append("")
    else:
        lines.append("Due tomorrow: nothing scheduled.")
        lines.append("")

    if meal_entry:
        lines.append(f"Planned dinner tomorrow: {meal_entry.dish}")
    else:
        suggestion = food_db.suggest_foods(db_path, meal_type="dinner", count=1)
        if suggestion:
            food = suggestion[0]
            lines.append(f"Dinner idea for tomorrow: {food.name}")
        else:
            lines.append("No meal plan for tomorrow yet.")
    lines.append("")

    if shopping:
        preview = ", ".join(format_shopping_display(todo) for todo in shopping[:4])
        extra = f" (+{len(shopping) - 4} more)" if len(shopping) > 4 else ""
        lines.append(f"Shopping list ({len(shopping)}): {preview}{extra}")

    return "\n".join(lines).strip()


def handle_evening_briefing(db_path: Path) -> str:
    return build_evening_briefing(db_path)
