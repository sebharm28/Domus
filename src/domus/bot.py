import asyncio
import logging
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from domus.config import get_settings
from domus.db import init_db
from domus.router import route_message

logger = logging.getLogger(__name__)

WAKE_WORD = "domus"
WAKE_PATTERN = re.compile(rf"\b{WAKE_WORD}\b", re.IGNORECASE)


def strip_wake_word(text: str) -> str:
    cleaned = WAKE_PATTERN.sub("", text, count=1).strip(" ,:;-")
    return cleaned or text.strip()


def has_wake_word(text: str) -> bool:
    return bool(WAKE_PATTERN.search(text))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Hi, I'm Domus — your household assistant.\n\n"
        "In this group, start a message with \"Domus\" and I'll help with "
        "your shared shopping list, reminders, and meal planning."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Say something like:\n"
        "• Domus, add milk to the list\n"
        "• Domus, what's on the list?\n"
        "• Domus, check off milk\n"
        "• Domus, remove milk"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()
    chat = message.chat
    sender = message.from_user.full_name if message.from_user else "unknown"

    if not has_wake_word(text):
        logger.debug("Ignored message without wake word from %s in chat %s", sender, chat.id)
        return

    request = strip_wake_word(text)
    logger.info("Wake word from %s in chat %s: %r", sender, chat.id, request)

    settings = context.application.bot_data["settings"]
    try:
        reply = await route_message(request, sender, settings)
    except Exception:
        logger.exception("Failed to handle message from %s", sender)
        reply = "Something went wrong on my side. Please try again in a moment."

    await message.reply_text(reply)


def build_application() -> Application:
    settings = get_settings()
    init_db(settings.database_path)

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Python 3.14+ no longer creates a default event loop automatically.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    logger.info("Starting Domus bot (polling mode)")
    application = build_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
