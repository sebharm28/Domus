from domus.config import Settings
from domus import db
from domus.intents import parse_intents
from domus.todos import handle_intents


async def route_message(
    text: str,
    settings: Settings,
    *,
    chat_id: int,
    telegram_user_id: int,
    display_name: str,
    username: str | None = None,
    private_mode: bool = False,
) -> str:
    db.upsert_user_profile(
        settings.database_path,
        telegram_user_id,
        display_name,
        username=username,
    )
    intents = await parse_intents(text, settings, private_mode=private_mode)
    reply = handle_intents(
        intents,
        settings.database_path,
        display_name,
        chat_id=chat_id,
        telegram_user_id=telegram_user_id,
    )
    if private_mode and reply.startswith("I didn't understand"):
        return (
            f"{reply}\n\n(Private mode: I only use local rules here, not OpenRouter.)"
        )
    return reply
