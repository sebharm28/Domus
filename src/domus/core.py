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
    DEFAULT_EVENING_BRIEFING_HOUR,
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    Settings,
    _parse_bool,
    _parse_pattern_list,
    get_settings,
)
from domus.db import (
    Todo,
    UserProfile,
    CompletionStat,
    delete_todo_by_id,
    get_user_profile,
    init_db,
    list_completion_stats,
    list_open_todos,
    list_user_profiles,
    set_todo_done,
)
from domus.food_db import (
    Food,
    add_recipe,
    get_food,
    init_food_tables,
    list_foods,
    list_tags,
    update_recipe,
)
from domus.meals import handle_plan_meal
from domus.router import route_message
from domus.todos import _add_or_merge_todo

__all__ = [
    "Settings",
    "Todo",
    "Food",
    "UserProfile",
    "CompletionStat",
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
    "add_recipe",
    "update_recipe",
    "get_food",
    "list_recipe_tags",
    "list_profiles",
    "get_profile",
    "list_completion_stats",
    "settings_payload",
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
        evening_briefing_hour=int(
            os.getenv("EVENING_BRIEFING_HOUR", str(DEFAULT_EVENING_BRIEFING_HOUR))
        ),
        quiet_hours_enabled=_parse_bool(os.getenv("QUIET_HOURS_ENABLED", "true"), default=True),
        quiet_hours_start=int(os.getenv("QUIET_HOURS_START", str(DEFAULT_QUIET_HOURS_START))),
        quiet_hours_end=int(os.getenv("QUIET_HOURS_END", str(DEFAULT_QUIET_HOURS_END))),
        redaction_enabled=_parse_bool(os.getenv("REDACTION_ENABLED", "false"), default=False),
        redaction_patterns=tuple(_parse_pattern_list(os.getenv("REDACTION_PATTERNS", ""))),
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


def list_recipe_tags(db_path: Path) -> list[str]:
    """Distinct recipe tags for filtering."""
    return list_tags(db_path)


def plan_recipe(db_path: Path, name: str, *, created_by: str = "You") -> str:
    """Plan a recipe by name, adding any missing ingredients to the list."""
    return handle_plan_meal(name, db_path, created_by, meal_name=name)


def list_profiles(db_path: Path) -> list[UserProfile]:
    return list_user_profiles(db_path)


def get_profile(db_path: Path, user_id: int) -> UserProfile | None:
    return get_user_profile(db_path, user_id)


def settings_payload(settings: Settings) -> dict:
    return {
        "briefing_hour": settings.briefing_hour,
        "evening_briefing_hour": settings.evening_briefing_hour,
        "quiet_hours_enabled": settings.quiet_hours_enabled,
        "quiet_hours_start": settings.quiet_hours_start,
        "quiet_hours_end": settings.quiet_hours_end,
        "redaction_enabled": settings.redaction_enabled,
        "redaction_patterns": list(settings.redaction_patterns),
    }


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
