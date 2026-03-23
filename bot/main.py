from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import get_settings
from bot.db import Database
from bot.handlers.callbacks import handle_post_callbacks
from bot.handlers.post import handle_reply_input, pending_command, post_command
from bot.handlers.start import start_command
from bot.services.scheduler import scheduler_loop
from bot.utils.logging import configure_logging


configure_logging()
logger = logging.getLogger(__name__)


async def on_startup(application: Application) -> None:
    db: Database = application.bot_data["db"]
    settings = application.bot_data["settings"]
    await db.initialize()

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        scheduler_loop(
            application=application,
            db=db,
            interval_seconds=settings.scheduler_interval_seconds,
            stop_event=stop_event,
        )
    )
    application.bot_data["scheduler_stop_event"] = stop_event
    application.bot_data["scheduler_task"] = task
    logger.info("Bot is running.")


async def on_shutdown(application: Application) -> None:
    stop_event = application.bot_data.get("scheduler_stop_event")
    task = application.bot_data.get("scheduler_task")
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        await task
    logger.info("Bot stopped.")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception while processing update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(f"Error: {context.error}")


def build_application() -> Application:
    settings = get_settings()
    db = Database(settings.database_path)

    application = (
        Application.builder()
        .token(settings.bot_token)
        .concurrent_updates(True)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )
    application.bot_data["settings"] = settings
    application.bot_data["db"] = db

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("post", post_command))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(CallbackQueryHandler(handle_post_callbacks, pattern=r"^post:"))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_reply_input,
        )
    )
    application.add_error_handler(on_error)

    return application


def main() -> None:
    application = build_application()
    application.run_polling(
        poll_interval=0.0,
        bootstrap_retries=0,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
