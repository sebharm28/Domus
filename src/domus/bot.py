import asyncio
import logging
import re

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from domus.config import get_settings
from domus.conversation_log import ConversationLog
from domus.db import init_db, subscribe_chat
from domus.food_db import init_food_tables
from domus.lifecycle import notify_subscribed_chats
from domus.private_mode import apply_private_mode
from domus.router import route_message
from domus.scheduler import start_morning_briefing_scheduler, start_reminder_scheduler

logger = logging.getLogger(__name__)

WAKE_WORD = "domus"
WAKE_PATTERN = re.compile(rf"\b{WAKE_WORD}\b", re.IGNORECASE)
MESSAGE_TIMEOUT_SECONDS = 45
TELEGRAM_MESSAGE_LIMIT = 4096


def strip_wake_word(text: str) -> str:
    cleaned = WAKE_PATTERN.sub("", text, count=1).strip(" ,:;-")
    return cleaned or text.strip()


def has_wake_word(text: str) -> bool:
    return bool(WAKE_PATTERN.search(text))


async def _safe_reply(message, text: str) -> None:
    if not text.strip():
        text = "I couldn't produce a reply for that message."
    chunks = [text[i : i + TELEGRAM_MESSAGE_LIMIT] for i in range(0, len(text), TELEGRAM_MESSAGE_LIMIT)]
    for chunk in chunks:
        await message.reply_text(chunk)


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
        "• Domus, hello\n"
        "• Domus, add milk to the list\n"
        "• Domus, we need butter and eggs\n"
        "• Domus, what's on the list?\n"
        "• Domus, what's on today?\n"
        "• Domus, let's make curry with rice tonight\n"
        "• Domus, plan meals for this week\n"
        "• Domus, what's missing for dinner?\n"
        "• Domus, remind us every Tuesday to take out the trash\n"
        "• Domus, what should I eat for dinner?\n"
        "• Domus, /private add pay rent by friday\n"
        "• Domus, thank you"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()
    chat = message.chat
    sender = message.from_user.full_name if message.from_user else "unknown"
    telegram_user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    reply_to_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.is_bot
    )

    has_private = bool(re.search(r"/private\b", text, re.IGNORECASE))
    if not has_wake_word(text) and not (reply_to_bot and has_private):
        logger.debug("Ignored message without wake word from %s in chat %s", sender, chat.id)
        return

    if has_wake_word(text):
        request = strip_wake_word(text)
    else:
        request = text.strip()

    request, private_mode = apply_private_mode(request, reply_to_bot=reply_to_bot)
    if private_mode:
        logger.info("Private mode from %s in chat %s", sender, chat.id)

    logger.info(
        "Wake word from %s in chat %s (%d chars): %r",
        sender,
        chat.id,
        len(request),
        request[:120],
    )

    settings = context.application.bot_data["settings"]
    conversation_log: ConversationLog = context.application.bot_data["conversation_log"]
    subscribe_chat(settings.database_path, chat.id, chat.title)
    try:
        await message.chat.send_action(ChatAction.TYPING)
        reply = await asyncio.wait_for(
            route_message(
                request,
                settings,
                chat_id=chat.id,
                telegram_user_id=telegram_user_id,
                display_name=sender,
                username=username,
                private_mode=private_mode,
            ),
            timeout=MESSAGE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("Timed out handling message from %s after %ss", sender, MESSAGE_TIMEOUT_SECONDS)
        reply = "That message took too long to process. Try splitting it into shorter requests."
    except Exception:
        logger.exception("Failed to handle message from %s", sender)
        reply = "Something went wrong on my side. Please try again in a moment."

    try:
        await _safe_reply(message, reply)
        conversation_log.log_exchange(sender, request, reply)
        logger.info("Replied to %s in chat %s", sender, chat.id)
    except Exception:
        logger.exception("Failed to send reply to %s in chat %s", sender, chat.id)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot error while processing update: %s", update, exc_info=context.error)


async def on_init(application: Application) -> None:
    start_reminder_scheduler(application)
    start_morning_briefing_scheduler(application)
    await notify_subscribed_chats(application, "Hi, I am awake and ready.")


async def on_shutdown(application: Application) -> None:
    await notify_subscribed_chats(application, "Goodbye, I am going to sleep now.")
    conversation_log: ConversationLog = application.bot_data.get("conversation_log")
    if conversation_log is not None:
        conversation_log.close()
        logger.info("Conversation log saved to %s", conversation_log.path)


def build_application() -> Application:
    settings = get_settings()
    init_db(settings.database_path)
    init_food_tables(settings.database_path)
    conversation_log = ConversationLog()

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(on_init)
        .post_shutdown(on_shutdown)
        .build()
    )
    application.bot_data["settings"] = settings
    application.bot_data["conversation_log"] = conversation_log
    application.add_error_handler(on_error)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Conversation logging to %s", conversation_log.path)
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
