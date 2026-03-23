from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    await update.effective_message.reply_text(
        "<b>Hello there! I'm HyperTech Post Manager Bot.</b>\n\n"
        "You can draft, preview, publish, and schedule Telegram channel posts using me.\n"
        "Use /post to open your workspace.",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
