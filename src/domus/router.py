from pathlib import Path

from domus.config import Settings
from domus.intents import parse_intent
from domus.todos import handle_intent


async def route_message(text: str, created_by: str, settings: Settings) -> str:
    intent = await parse_intent(text, settings)
    return handle_intent(intent, settings.database_path, created_by)
