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
    init_db,
    list_open_todos,
    set_todo_done,
)
from domus.food_db import init_food_tables
from domus.router import route_message

__all__ = [
    "Settings",
    "Todo",
    "get_settings",
    "build_settings",
    "init_storage",
    "handle_user_message",
    "list_open_todos",
    "set_todo_done",
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
