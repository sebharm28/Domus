import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from domus.db import connect


@dataclass(frozen=True)
class MealPlanEntry:
    id: int
    day: str
    dish: str
    ingredients: list[str]
    food_id: int | None = None


@dataclass(frozen=True)
class Food:
    id: int
    name: str
    meal_type: str
    ingredients: list[str]
    prep_time_min: int | None
    notes: str | None


DEFAULT_FOODS: list[tuple[str, str, list[str], int, str]] = [
    ("Scrambled eggs on toast", "breakfast", ["eggs", "bread", "butter"], 10, "Quick and filling"),
    ("Oatmeal with fruit", "breakfast", ["oats", "milk", "banana"], 10, "Healthy start"),
    ("Greek yogurt bowl", "breakfast", ["yogurt", "berries", "honey"], 5, "No cooking needed"),
    ("Pasta aglio e olio", "dinner", ["pasta", "garlic", "olive oil", "parsley"], 20, "Simple classic"),
    ("Tomato pasta", "dinner", ["pasta", "tomatoes", "garlic", "olive oil"], 25, "Comfort food"),
    ("Stir-fried rice", "dinner", ["rice", "eggs", "vegetables", "soy sauce"], 20, "Use leftover rice"),
    ("Chicken wrap", "lunch", ["tortilla", "chicken", "salad", "yogurt sauce"], 15, "Easy to pack"),
    ("Tuna salad sandwich", "lunch", ["bread", "tuna", "corn", "yogurt"], 10, "No stove needed"),
    ("Vegetable soup", "dinner", ["potatoes", "carrots", "onion", "stock"], 35, "Good for batch cooking"),
    ("Shakshuka", "breakfast", ["eggs", "tomatoes", "pepper", "onion"], 25, "One-pan meal"),
    ("Rice and beans", "dinner", ["rice", "beans", "onion", "spices"], 30, "Budget friendly"),
    ("Avocado toast", "breakfast", ["bread", "avocado", "lemon", "eggs"], 10, "Fast brunch"),
    ("Pizza toast", "lunch", ["bread", "tomato sauce", "cheese", "oregano"], 15, "Student classic"),
    ("Curry with rice", "dinner", ["rice", "coconut milk", "vegetables", "curry paste"], 30, "Warm and filling"),
    ("Salmon bowl", "dinner", ["salmon", "rice", "cucumber", "soy sauce"], 25, "Light but satisfying"),
    ("Caprese salad", "lunch", ["mozzarella", "tomatoes", "basil", "olive oil"], 10, "Fresh option"),
    ("Pancakes", "breakfast", ["flour", "eggs", "milk", "butter"], 20, "Weekend treat"),
    ("Hummus plate", "lunch", ["hummus", "bread", "cucumber", "tomatoes"], 5, "Minimal prep"),
]


def init_food_tables(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                meal_type TEXT NOT NULL,
                ingredients TEXT NOT NULL DEFAULT '[]',
                prep_time_min INTEGER,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS meal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_id INTEGER NOT NULL,
                eaten_at TEXT NOT NULL,
                created_by TEXT,
                FOREIGN KEY (food_id) REFERENCES foods(id)
            );

            CREATE TABLE IF NOT EXISTS meal_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL UNIQUE,
                dish TEXT NOT NULL,
                food_id INTEGER,
                ingredients TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (food_id) REFERENCES foods(id)
            );
            """
        )
        count = conn.execute("SELECT COUNT(*) AS c FROM foods").fetchone()["c"]
        if count == 0:
            for name, meal_type, ingredients, prep_time, notes in DEFAULT_FOODS:
                conn.execute(
                    """
                    INSERT INTO foods (name, meal_type, ingredients, prep_time_min, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, meal_type, json.dumps(ingredients), prep_time, notes),
                )


def _row_to_food(row: sqlite3.Row) -> Food:
    return Food(
        id=row["id"],
        name=row["name"],
        meal_type=row["meal_type"],
        ingredients=json.loads(row["ingredients"]),
        prep_time_min=row["prep_time_min"],
        notes=row["notes"],
    )


def list_foods(db_path: Path, meal_type: str | None = None) -> list[Food]:
    query = "SELECT * FROM foods"
    params: list[str] = []
    if meal_type:
        query += " WHERE meal_type = ?"
        params.append(meal_type)
    query += " ORDER BY name ASC"
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_food(row) for row in rows]


def recent_food_ids(db_path: Path, days: int = 2) -> set[int]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT food_id FROM meal_history WHERE eaten_at >= ?",
            (cutoff,),
        ).fetchall()
    return {row["food_id"] for row in rows}


def log_meal(db_path: Path, food_id: int, created_by: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO meal_history (food_id, eaten_at, created_by) VALUES (?, ?, ?)",
            (food_id, now, created_by),
        )


def find_food_by_name(db_path: Path, name: str) -> Food | None:
    normalized = name.strip().lower()
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM foods").fetchall()
    match = next((row for row in rows if normalized in row["name"].lower()), None)
    return _row_to_food(match) if match else None


def suggest_foods(
    db_path: Path,
    meal_type: str | None = None,
    count: int = 3,
    *,
    exclude_ids: set[int] | None = None,
    profiles: list | None = None,
) -> list[Food]:
    from domus.diet import filter_foods_for_household

    recent = recent_food_ids(db_path)
    blocked = recent | (exclude_ids or set())
    candidates = [food for food in list_foods(db_path, meal_type) if food.id not in blocked]
    if not candidates:
        candidates = [food for food in list_foods(db_path, meal_type) if food.id not in (exclude_ids or set())]
    if not candidates:
        candidates = list_foods(db_path, meal_type)
    candidates = filter_foods_for_household(candidates, profiles or [])
    if not candidates:
        candidates = [food for food in list_foods(db_path, meal_type) if food.id not in blocked]
        if not candidates:
            candidates = list_foods(db_path, meal_type)
    if not candidates:
        return []
    random.shuffle(candidates)
    return candidates[:count]


def _row_to_meal_plan(row: sqlite3.Row) -> MealPlanEntry:
    return MealPlanEntry(
        id=row["id"],
        day=row["day"],
        dish=row["dish"],
        ingredients=json.loads(row["ingredients"]),
        food_id=row["food_id"],
    )


def clear_meal_plan_range(db_path: Path, start_day: str, end_day: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "DELETE FROM meal_plans WHERE day >= ? AND day <= ?",
            (start_day, end_day),
        )


def save_meal_plan_entry(db_path: Path, day: str, food: Food) -> MealPlanEntry:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO meal_plans (day, dish, food_id, ingredients)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(day) DO UPDATE SET
                dish = excluded.dish,
                food_id = excluded.food_id,
                ingredients = excluded.ingredients
            """,
            (day, food.name, food.id, json.dumps(food.ingredients)),
        )
        row = conn.execute("SELECT * FROM meal_plans WHERE day = ?", (day,)).fetchone()
    return _row_to_meal_plan(row)


def get_meal_plan_range(db_path: Path, start_day: str, end_day: str) -> list[MealPlanEntry]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM meal_plans
            WHERE day >= ? AND day <= ?
            ORDER BY day ASC
            """,
            (start_day, end_day),
        ).fetchall()
    return [_row_to_meal_plan(row) for row in rows]


def get_meal_plan_for_day(db_path: Path, day: str) -> MealPlanEntry | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM meal_plans WHERE day = ?", (day,)).fetchone()
    return _row_to_meal_plan(row) if row else None
