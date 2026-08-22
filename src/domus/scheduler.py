import logging
from datetime import date, time

from telegram.ext import Application, ContextTypes

from domus.briefing import build_daily_briefing
from domus.config import Settings
from domus.dates import format_due_date
from domus.db import list_due_todos_for_reminder, list_notification_chats, mark_todo_reminded

logger = logging.getLogger(__name__)


async def send_due_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    due_todos = list_due_todos_for_reminder(settings.database_path, date.today())
    if not due_todos:
        return

    chat_ids = list_notification_chats(settings.database_path)
    if not chat_ids:
        logger.warning("Due todos found but no notification chats are subscribed")
        return

    for todo in due_todos:
        due_label = format_due_date(todo.due_date)
        message = (
            f"Reminder: \"{todo.text}\" is due ({due_label}). "
            f"Category: {todo.category}."
        )
        for chat_id in chat_ids:
            try:
                await context.bot.send_message(chat_id=chat_id, text=message)
            except Exception:
                logger.exception("Failed to send reminder for todo %s to chat %s", todo.id, chat_id)
        mark_todo_reminded(settings.database_path, todo.id)
        logger.info("Sent reminder for todo %s to %d chat(s)", todo.id, len(chat_ids))


async def send_morning_briefing(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    chat_ids = list_notification_chats(settings.database_path)
    if not chat_ids:
        return

    message = build_daily_briefing(settings.database_path)
    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            logger.exception("Failed to send morning briefing to chat %s", chat_id)
    logger.info("Sent morning briefing to %d chat(s)", len(chat_ids))


def start_reminder_scheduler(application: Application, interval_seconds: int = 60) -> None:
    if application.job_queue is None:
        logger.warning("Job queue unavailable; due-date reminders are disabled")
        return
    application.job_queue.run_repeating(
        send_due_reminders,
        interval=interval_seconds,
        first=10,
        name="due_todo_reminders",
    )
    logger.info("Reminder scheduler started (every %ss)", interval_seconds)


def start_morning_briefing_scheduler(application: Application) -> None:
    if application.job_queue is None:
        logger.warning("Job queue unavailable; morning briefing is disabled")
        return

    settings: Settings = application.bot_data["settings"]
    briefing_time = time(hour=settings.briefing_hour, minute=0)
    application.job_queue.run_daily(
        send_morning_briefing,
        time=briefing_time,
        name="morning_briefing",
    )
    logger.info("Morning briefing scheduled daily at %02d:00", settings.briefing_hour)
