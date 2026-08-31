"""Meal plan payloads for the UI (calendar week Mon–Sun)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from domus import db, food_db


def calendar_week_bounds(week_offset: int = 0, today: date | None = None) -> tuple[date, date]:
    """Monday–Sunday for the calendar week (week_offset 0 = this week)."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def meal_plan_payload(
    db_path: Path,
    *,
    week_offset: int = 0,
    apartment: str | None = None,
    today: date | None = None,
) -> dict:
    if apartment:
        food_db.prune_old_meal_plans(db_path, apartment)
    start, end = calendar_week_bounds(week_offset, today)
    entries = {
        entry.day: entry
        for entry in food_db.get_meal_plan_range(
            db_path,
            start.isoformat(),
            end.isoformat(),
            apartment=apartment,
        )
    }
    days: list[dict] = []
    day = start
    while day <= end:
        iso = day.isoformat()
        entry = entries.get(iso)
        days.append(
            {
                "day": iso,
                "weekday": day.strftime("%a"),
                "label": day.strftime("%d %b"),
                "is_today": day == (today or date.today()),
                "dish": entry.dish if entry else None,
                "food_id": entry.food_id if entry else None,
                "id": entry.id if entry else None,
            }
        )
        day += timedelta(days=1)
    return {
        "apartment": apartment,
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "week_offset": week_offset,
        "days": days,
    }


def set_meal_plan_day(
    db_path: Path,
    day: str,
    dish: str,
    *,
    apartment: str | None = None,
) -> food_db.MealPlanEntry:
    """Assign a recipe or free-text dish to a calendar day."""
    cleaned = dish.strip()
    if not cleaned:
        raise ValueError("Dish name required")
    food = food_db.find_food_by_name(db_path, cleaned)
    if food is not None:
        entry = food_db.save_meal_plan_entry(db_path, day, food, apartment=apartment)
    else:
        entry = food_db.save_meal_plan_dish(db_path, day, cleaned, apartment=apartment)
    if apartment:
        food_db.prune_old_meal_plans(db_path, apartment)
    return entry


def suggest_meal_plan_day(
    db_path: Path,
    day: str,
    *,
    apartment: str | None = None,
    profiles: list | None = None,
) -> food_db.MealPlanEntry:
    suggestions = food_db.suggest_foods(
        db_path,
        meal_type="dinner",
        count=1,
        profiles=profiles,
    )
    if not suggestions:
        raise ValueError("No dinner ideas in the database")
    entry = food_db.save_meal_plan_entry(
        db_path,
        day,
        suggestions[0],
        apartment=apartment,
    )
    if apartment:
        food_db.prune_old_meal_plans(db_path, apartment)
    return entry


def plan_calendar_week(
    db_path: Path,
    *,
    week_offset: int = 0,
    apartment: str | None = None,
    created_by: str = "You",
    profiles: list | None = None,
    today: date | None = None,
    replace: bool = True,
) -> tuple[list[food_db.MealPlanEntry], list[str]]:
    """Plan dinners Mon–Sun for a calendar week; returns entries and missing ingredients added."""
    from domus.meals import _compare_ingredients, _shopping_items

    start, end = calendar_week_bounds(week_offset, today)
    if replace:
        food_db.clear_meal_plan_range(
            db_path,
            start.isoformat(),
            end.isoformat(),
            apartment=apartment,
        )

    planned: list[food_db.MealPlanEntry] = []
    used_food_ids: set[int] = set()
    day = start
    while day <= end:
        iso = day.isoformat()
        if not replace:
            existing = food_db.get_meal_plan_for_day(db_path, iso, apartment=apartment)
            if existing:
                day += timedelta(days=1)
                continue
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
        planned.append(
            food_db.save_meal_plan_entry(db_path, iso, food, apartment=apartment)
        )
        day += timedelta(days=1)

    missing_added: list[str] = []
    if planned:
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
            missing_added.append(ingredient)

    if apartment:
        food_db.prune_old_meal_plans(db_path, apartment)

    return planned, missing_added
