from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone

from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import Application

from bot.db import Database
from bot.services.messenger import send_post_message
from bot.services.parser import keyboard_from_json


logger = logging.getLogger(__name__)


async def scheduler_loop(
    application: Application,
    db: Database,
    interval_seconds: int,
    stop_event: asyncio.Event,
) -> None:
    logger.info("Scheduler started. Checking every %s seconds.", interval_seconds)
    while not stop_event.is_set():
        await process_due_posts(application, db)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
    logger.info("Scheduler stopped.")


async def process_due_posts(application: Application, db: Database) -> None:
    now_utc = datetime.now(timezone.utc)
    due_posts = await db.get_due_posts(now_utc)

    for post in due_posts:
        try:
            await send_post_message(
                application.bot.send_message,
                post["content"],
                keyboard_from_json(post["buttons"]),
                chat_id=post["channel_id"],
            )
        except (BadRequest, Forbidden, TelegramError) as exc:
            logger.warning("Scheduled post %s failed for %s: %s", post["id"], post["channel_id"], exc)
            await db.mark_post_failed(post["id"], str(exc))
            await notify_post_status(application, post, success=False, error_message=str(exc))
            continue

        logger.info("Scheduled post %s sent to %s", post["id"], post["channel_id"])
        await db.mark_post_sent(post["id"])
        await notify_post_status(application, post, success=True)


async def notify_post_status(
    application: Application,
    post,
    *,
    success: bool,
    error_message: str | None = None,
) -> None:
    owner_chat_id = post["owner_chat_id"]
    if owner_chat_id is None:
        return

    channel = html.escape(str(post["channel_id"] or ""))
    reason = html.escape(error_message or "Unknown error")

    if success:
        message = (
            "<b>Scheduled Post Sent</b>\n\n"
            f"<b>Channel:</b> {channel}"
        )
    else:
        message = (
            "<b>Scheduled Post Failed</b>\n\n"
            f"<b>Channel:</b> {channel}\n"
            f"<b>Reason:</b> {reason}\n\n"
            "Use /pending to review unsent posts."
        )

    try:
        await application.bot.send_message(
            chat_id=owner_chat_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except TelegramError as exc:
        logger.warning("Could not notify owner about post %s: %s", post["id"], exc)
