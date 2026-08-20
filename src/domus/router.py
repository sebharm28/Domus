from domus.config import Settings
from domus.intents import parse_intents
from domus.todos import handle_intents


async def route_message(text: str, created_by: str, settings: Settings) -> str:
    intents = await parse_intents(text, settings)
    return handle_intents(intents, settings.database_path, created_by)
