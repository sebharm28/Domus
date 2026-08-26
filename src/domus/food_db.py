import json
import random
import sqlite3
from dataclasses import dataclass, field
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
    # Detailed ingredients with amounts, e.g. [{"name": "flour", "amount": "200 g"}].
    # `ingredients` stays a plain name list for the cards and the meal planner.
    ingredient_details: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    author: str | None = None


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
        _migrate_foods(conn)
        count = conn.execute("SELECT COUNT(*) AS c FROM foods").fetchone()["c"]
        if count == 0:
            for name, meal_type, ingredients, prep_time, notes in DEFAULT_FOODS:
                details = [{"name": item, "amount": ""} for item in ingredients]
                conn.execute(
                    """
                    INSERT INTO foods
                        (name, meal_type, ingredients, prep_time_min, notes,
                         ingredient_details, tags, author)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        meal_type,
                        json.dumps(ingredients),
                        prep_time,
                        notes,
                        json.dumps(details),
                        json.dumps([meal_type]),
                        "Domus",
                    ),
                )


def _migrate_foods(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(foods)")}
    if "ingredient_details" not in columns:
        conn.execute(
            "ALTER TABLE foods ADD COLUMN ingredient_details TEXT NOT NULL DEFAULT '[]'"
        )
    if "tags" not in columns:
        conn.execute("ALTER TABLE foods ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
    if "author" not in columns:
        conn.execute("ALTER TABLE foods ADD COLUMN author TEXT")

    # Backfill new columns for pre-existing rows so the UI has content to show.
    rows = conn.execute("SELECT id, meal_type, ingredients, ingredient_details, tags FROM foods").fetchall()
    for row in rows:
        updates: list[str] = []
        params: list = []
        if not json.loads(row["ingredient_details"] or "[]"):
            names = json.loads(row["ingredients"] or "[]")
            details = [{"name": item, "amount": ""} for item in names]
            updates.append("ingredient_details = ?")
            params.append(json.dumps(details))
        if not json.loads(row["tags"] or "[]") and row["meal_type"]:
            updates.append("tags = ?")
            params.append(json.dumps([row["meal_type"]]))
        if updates:
            params.append(row["id"])
            conn.execute(f"UPDATE foods SET {', '.join(updates)} WHERE id = ?", params)


def _row_to_food(row: sqlite3.Row) -> Food:
    keys = row.keys()
    details = []
    if "ingredient_details" in keys and row["ingredient_details"]:
        details = json.loads(row["ingredient_details"])
    tags = []
    if "tags" in keys and row["tags"]:
        tags = json.loads(row["tags"])
    author = row["author"] if "author" in keys else None
    return Food(
        id=row["id"],
        name=row["name"],
        meal_type=row["meal_type"],
        ingredients=json.loads(row["ingredients"]),
        prep_time_min=row["prep_time_min"],
        notes=row["notes"],
        ingredient_details=details,
        tags=tags,
        author=author,
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


def add_custom_food(
    db_path: Path,
    name: str,
    *,
    meal_type: str = "dinner",
    notes: str | None = "Added from your preferences",
) -> Food:
    title = " ".join(word.capitalize() for word in name.strip().split())
    ingredient = name.strip().lower()
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM foods WHERE lower(name) = lower(?)",
            (title,),
        ).fetchone()
        if row is not None:
            return _row_to_food(row)
        cursor = conn.execute(
            """
            INSERT INTO foods (name, meal_type, ingredients, prep_time_min, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, meal_type, json.dumps([ingredient]), None, notes),
        )
        row = conn.execute(
            "SELECT * FROM foods WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _row_to_food(row)


def get_food(db_path: Path, food_id: int) -> Food | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM foods WHERE id = ?", (food_id,)).fetchone()
    return _row_to_food(row) if row else None


def _clean_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for tag in tags or []:
        tag = str(tag).strip()
        if tag and tag.lower() not in {t.lower() for t in cleaned}:
            cleaned.append(tag)
    return cleaned


def add_recipe(
    db_path: Path,
    name: str,
    *,
    meal_type: str = "dinner",
    ingredient_details: list[dict] | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    author: str | None = None,
    prep_time_min: int | None = None,
) -> Food:
    """Create a recipe with amounts per ingredient, tags and an author."""
    title = " ".join(word.capitalize() for word in name.strip().split())
    if not title:
        raise ValueError("Recipe name is required.")

    details: list[dict] = []
    names: list[str] = []
    for item in ingredient_details or []:
        iname = str(item.get("name", "")).strip()
        if not iname:
            continue
        amount = str(item.get("amount", "") or "").strip()
        details.append({"name": iname, "amount": amount})
        names.append(iname)

    tag_list = _clean_tags(tags)
    if meal_type and meal_type.lower() not in {t.lower() for t in tag_list}:
        tag_list.insert(0, meal_type)

    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM foods WHERE lower(name) = lower(?)", (title,)
        ).fetchone()
        if existing is not None:
            raise ValueError(f'A recipe called "{title}" already exists.')
        cursor = conn.execute(
            """
            INSERT INTO foods
                (name, meal_type, ingredients, prep_time_min, notes,
                 ingredient_details, tags, author)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                meal_type or "dinner",
                json.dumps(names),
                prep_time_min,
                notes,
                json.dumps(details),
                json.dumps(tag_list),
                author,
            ),
        )
        row = conn.execute("SELECT * FROM foods WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_food(row)


def update_recipe(
    db_path: Path,
    food_id: int,
    *,
    notes: str | None = None,
    tags: list[str] | None = None,
) -> Food | None:
    """Update a recipe's markdown notes and/or its tag list."""
    fields: list[str] = []
    params: list = []
    if notes is not None:
        fields.append("notes = ?")
        params.append(notes)
    if tags is not None:
        fields.append("tags = ?")
        params.append(json.dumps(_clean_tags(tags)))
    if not fields:
        return get_food(db_path, food_id)
    params.append(food_id)
    with connect(db_path) as conn:
        conn.execute(f"UPDATE foods SET {', '.join(fields)} WHERE id = ?", params)
        row = conn.execute("SELECT * FROM foods WHERE id = ?", (food_id,)).fetchone()
    return _row_to_food(row) if row else None


def list_tags(db_path: Path) -> list[str]:
    """Distinct recipe tags (case-insensitive), for the filter UI."""
    seen: dict[str, str] = {}
    for food in list_foods(db_path):
        for tag in food.tags:
            if tag.lower() not in seen:
                seen[tag.lower()] = tag
    return sorted(seen.values(), key=str.lower)


def _likes_score(food: Food, profiles: list) -> int:
    score = 0
    blob = food.name.lower()
    for profile in profiles:
        if not profile.likes:
            continue
        for like in profile.likes.split(","):
            like = like.strip().lower()
            if like and like in blob:
                score += 1
    return score


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
    liked = [food for food in candidates if _likes_score(food, profiles or []) > 0]
    other = [food for food in candidates if food not in liked]
    random.shuffle(liked)
    random.shuffle(other)
    ranked = liked + other
    return ranked[:count]


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
