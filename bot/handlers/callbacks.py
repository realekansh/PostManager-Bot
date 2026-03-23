from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.post import (
    cancel_draft,
    pending_callback,
    preview_draft,
    prompt_for_input,
    publish_draft,
    refresh_menu_from_query,
)


async def handle_post_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    if data == "post:content":
        await prompt_for_input(
            update,
            context,
            prompt_action="writing_content",
            prompt_text="<b>Write Post</b>\nSend your post content exactly as it should appear.",
        )
        return
    if data == "post:buttons":
        await prompt_for_input(
            update,
            context,
            prompt_action="adding_buttons",
            prompt_text=(
                "<b>Add Button</b>\n"
                "Send button definitions like:\n"
                "[Google](https://google.com) [Docs](https://docs.com)\n"
                "[GitHub](https://github.com)"
            ),
        )
        return
    if data == "post:channel":
        await prompt_for_input(
            update,
            context,
            prompt_action="setting_channel",
            prompt_text=(
                "<b>Set Channel</b>\n"
                "Send the target channel username or ID, for example @my_channel."
            ),
        )
        return
    if data == "post:schedule":
        await prompt_for_input(
            update,
            context,
            prompt_action="setting_schedule",
            prompt_text=(
                "<b>Set Schedule</b>\n"
                "Send the time in HH:MM AM/PM DD-MM-YYYY."
            ),
        )
        return
    if data == "post:preview":
        await preview_draft(update, context)
        return
    if data == "post:pending":
        await pending_callback(update, context)
        return
    if data == "post:publish":
        await publish_draft(update, context)
        return
    if data == "post:cancel":
        await cancel_draft(update, context)
        return

    await refresh_menu_from_query(update, context)
