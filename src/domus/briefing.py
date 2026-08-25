from datetime import date
from pathlib import Path

from domus import db, food_db
from domus.dates import format_due_date
from domus.meals import infer_meal_type
from domus.shopping import format_shopping_display


def build_daily_briefing(db_path: Path, today: date | None = None) -> str:
    today = today or date.today()
    due_today = db.list_todos_due_on(db_path, today)
    overdue = db.list_overdue_todos(db_path, today)
    shopping = db.list_open_todos(db_path, category="shopping")
    highlighted_ids = {todo.id for todo in due_today} | {todo.id for todo in overdue}
    other_open = [
        todo
        for todo in db.list_open_todos(db_path)
        if todo.category != "shopping" and todo.id not in highlighted_ids
    ]

    lines = [f"Daily briefing — {today.strftime('%a, %d %b %Y')}", ""]

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


def handle_daily_briefing(db_path: Path) -> str:
    return build_daily_briefing(db_path)
