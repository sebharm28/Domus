from domus.config import Settings
from domus.intents import parse_intents
from domus.todos import handle_intents


async def route_message(
    text: str,
    created_by: str,
    settings: Settings,
    *,
    private_mode: bool = False,
) -> str:
    intents = await parse_intents(text, settings, private_mode=private_mode)
    reply = handle_intents(intents, settings.database_path, created_by)
    if private_mode and reply.startswith("I didn't understand"):
        return (
            f"{reply}\n\n(Private mode: I only use local rules here, not OpenRouter.)"
        )
    return reply
