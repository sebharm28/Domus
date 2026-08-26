import logging

from telegram.ext import Application

from domus.db import list_notification_chats

logger = logging.getLogger(__name__)

AWAKE_MESSAGE = "Hi, I am awake and ready."
SLEEP_MESSAGE = "Goodbye, I am going to sleep now."


async def notify_subscribed_chats(application: Application, message: str) -> None:
    settings = application.bot_data["settings"]
    chat_ids = list_notification_chats(settings.database_path)
    if not chat_ids:
        logger.info("No subscribed chats to notify")
        return

    for chat_id in chat_ids:
        try:
            await application.bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            logger.exception("Failed to send lifecycle message to chat %s", chat_id)

    logger.info("Sent lifecycle message to %d chat(s)", len(chat_ids))
