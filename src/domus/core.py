"""Platform-agnostic Domus core (the "brain").

This module is the stable entry point that every frontend should build on —
the Telegram adapter (:mod:`domus.telegram_bot`), the prototype web/desktop UI
in the top-level ``ui/`` folder, and any future native mobile app.

Nothing here imports a specific messaging platform. A frontend only needs to:

1. build a :class:`Settings` (see :func:`get_settings`), and
2. hand user text to :func:`handle_user_message`, then render the reply and the
   current shopping/task list.

Keeping this boundary explicit means new frontends never have to touch the
Telegram code, and the Telegram bot never has to know about the UI.
"""

from __future__ import annotations

import os
from pathlib import Path

from domus.config import (
    DEFAULT_BRIEFING_HOUR,
    DEFAULT_DB_PATH,
    DEFAULT_OPENROUTER_MODEL,
    Settings,
    get_settings,
)
from domus.db import (
    Todo,
    delete_todo_by_id,
    init_db,
    list_open_todos,
    set_todo_done,
)
from domus.food_db import Food, init_food_tables, list_foods
from domus.meals import handle_plan_meal
from domus.router import route_message
from domus.todos import _add_or_merge_todo

__all__ = [
    "Settings",
    "Todo",
    "Food",
    "get_settings",
    "build_settings",
    "init_storage",
    "handle_user_message",
    "list_open_todos",
    "add_item",
    "delete_item",
    "set_todo_done",
    "list_recipes",
    "plan_recipe",
    "route_message",
]


def build_settings(*, database_path: Path | None = None) -> Settings:
    """Build :class:`Settings` for a non-Telegram frontend.

    Unlike :func:`get_settings`, this does not require ``TELEGRAM_BOT_TOKEN`` —
    UI/desktop/mobile frontends never talk to Telegram. The optional OpenRouter
    key still enables smarter intent parsing when present.
    """
    return Settings(
        telegram_bot_token="",
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip() or None,
        openrouter_model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip(),
        database_path=database_path or Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH))),
        briefing_hour=int(os.getenv("BRIEFING_HOUR", str(DEFAULT_BRIEFING_HOUR))),
    )


def init_storage(db_path: Path) -> None:
    """Create the database schema and seed tables if they do not exist yet."""
    init_db(db_path)
    init_food_tables(db_path)


def add_item(
    db_path: Path,
    name: str,
    *,
    category: str = "shopping",
    created_by: str = "You",
    due_date: str | None = None,
) -> Todo | None:
    """Add (or quantity-merge) an item directly, without going through chat.

    Shopping items merge quantities the same way a chat "add" does; other
    categories are appended as tasks.
    """
    _reply, todo = _add_or_merge_todo(
        db_path,
        name,
        created_by,
        due_date=due_date,
        category=category,
    )
    return todo


def delete_item(db_path: Path, todo_id: int) -> Todo | None:
    """Remove an item/task entirely by id."""
    return delete_todo_by_id(db_path, todo_id)


def list_recipes(db_path: Path) -> list[Food]:
    """All known recipes/meal ideas, for a recipe-overview screen."""
    return list_foods(db_path)


def plan_recipe(db_path: Path, name: str, *, created_by: str = "You") -> str:
    """Plan a recipe by name, adding any missing ingredients to the list."""
    return handle_plan_meal(name, db_path, created_by, meal_name=name)


async def handle_user_message(
    text: str,
    settings: Settings,
    *,
    chat_id: int,
    user_id: int,
    display_name: str,
    username: str | None = None,
    private_mode: bool = False,
) -> str:
    """Route a single natural-language message through the assistant brain.

    This is a thin, frontend-neutral wrapper around :func:`route_message`. The
    ``chat_id``/``user_id`` are opaque integers a frontend uses to keep separate
    households and speakers apart; they carry no Telegram-specific meaning.
    """
    return await route_message(
        text,
        settings,
        chat_id=chat_id,
        telegram_user_id=user_id,
        display_name=display_name,
        username=username,
        private_mode=private_mode,
    )
