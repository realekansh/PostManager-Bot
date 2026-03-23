from __future__ import annotations

from telegram.constants import ParseMode

from bot.utils.markdown import render_user_content


async def send_post_message(send_func, content: str, reply_markup=None, **kwargs):
    rendered = render_user_content(content)
    return await send_func(
        text=rendered,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
        **kwargs,
    )
