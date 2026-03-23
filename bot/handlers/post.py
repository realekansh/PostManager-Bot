from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import Database
from bot.models.draft import Draft
from bot.services.messenger import send_post_message
from bot.services.parser import button_summary, buttons_json_from_text, keyboard_from_json


logger = logging.getLogger(__name__)
MENU_TEXT = "Post Draft"


def build_post_menu(draft: Draft, settings: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Write Post", callback_data="post:content"),
                InlineKeyboardButton("Add Button", callback_data="post:buttons"),
            ],
            [
                InlineKeyboardButton("Set Channel", callback_data="post:channel"),
                InlineKeyboardButton("Set Schedule", callback_data="post:schedule"),
            ],
            [
                InlineKeyboardButton("Preview", callback_data="post:preview"),
                InlineKeyboardButton("Pending", callback_data="post:pending"),
            ],
            [
                InlineKeyboardButton("Cancel", callback_data="post:cancel"),
                InlineKeyboardButton("Publish", callback_data="post:publish"),
            ],
        ]
    )


def build_post_menu_text(draft: Draft, settings: Settings) -> str:
    scheduled = format_schedule_for_user(draft.scheduled_time, settings)
    return (
        f"<b>{MENU_TEXT}</b>\n\n"
        f"<b>Write Post:</b> {'Ready' if draft.has_content else 'Not set'}\n"
        f"<b>Add Button:</b> {html.escape(button_summary(draft.buttons))}\n"
        f"<b>Set Channel:</b> {html.escape(draft.channel_id or 'Not set')}\n"
        f"<b>Set Schedule:</b> {html.escape(scheduled)}\n"
        f"<b>State:</b> {html.escape(draft.state)}"
    )


async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return

    db: Database = context.application.bot_data["db"]
    settings: Settings = context.application.bot_data["settings"]
    draft = await db.get_or_create_draft(update.effective_user.id)

    await update.effective_message.reply_text(
        build_post_menu_text(draft, settings),
        reply_markup=build_post_menu(draft, settings),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return

    db: Database = context.application.bot_data["db"]
    settings: Settings = context.application.bot_data["settings"]
    await send_pending_overview(
        update.effective_message.reply_text,
        db=db,
        settings=settings,
        user_id=update.effective_user.id,
    )


async def pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return

    await query.answer()
    db: Database = context.application.bot_data["db"]
    settings: Settings = context.application.bot_data["settings"]
    await send_pending_overview(
        query.message.reply_text,
        db=db,
        settings=settings,
        user_id=query.from_user.id,
    )


async def send_pending_overview(send_func, *, db: Database, settings: Settings, user_id: int) -> None:
    posts = await db.get_unsent_posts_for_user(user_id)

    if not posts:
        await send_func(
            "<b>Pending Queue</b>\n\nNo unsent posts right now.",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    lines = ["<b>Pending Queue</b>", ""]
    for index, post in enumerate(posts, start=1):
        status_label = "Failed" if post["status"] == "failed" else "Pending"
        scheduled_text = format_schedule_for_user(post["scheduled_time"], settings)
        preview = html.escape(compact_preview(post["content"]))

        lines.append(f"<b>{index}. {status_label}</b>")
        lines.append(f"<b>Channel:</b> {html.escape(post['channel_id'] or 'Unknown')}")
        lines.append(f"<b>Schedule:</b> {html.escape(scheduled_text)}")
        lines.append(f"<b>Preview:</b> {preview}")
        if post["failure_reason"]:
            lines.append(f"<b>Reason:</b> {html.escape(post['failure_reason'])}")
        lines.append("")

    await send_func(
        "\n".join(lines).strip(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def prompt_for_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    prompt_action: str,
    prompt_text: str,
) -> None:
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return

    await query.answer()

    db: Database = context.application.bot_data["db"]
    await db.get_or_create_draft(query.from_user.id)

    prompt_message = await query.message.reply_text(
        prompt_text,
        reply_markup=ForceReply(selective=True),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
    draft = await db.update_draft_fields(
        query.from_user.id,
        state=prompt_action,
        prompt_action=prompt_action,
        prompt_chat_id=prompt_message.chat_id,
        prompt_message_id=prompt_message.message_id,
    )

    await refresh_menu(query, draft, context)


async def handle_reply_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user or not update.effective_chat:
        return

    db: Database = context.application.bot_data["db"]
    settings: Settings = context.application.bot_data["settings"]
    draft = await db.get_draft(update.effective_user.id)
    if draft is None or not draft.prompt_action:
        return

    if draft.prompt_chat_id is not None and update.effective_chat.id != draft.prompt_chat_id:
        return

    if update.effective_message.text is None:
        return

    text = update.effective_message.text.strip()
    if not text:
        await update.effective_message.reply_text(
            "<b>Empty Reply</b>\n\nPlease send a non-empty message.",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    try:
        if draft.prompt_action == "writing_content":
            draft = await db.update_draft_fields(
                update.effective_user.id,
                content=update.effective_message.text,
                state="ready",
                prompt_action=None,
                prompt_chat_id=None,
                prompt_message_id=None,
            )
            await update.effective_message.reply_text(
                "<b>Content Saved</b>\n\nYour draft text is ready.",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        elif draft.prompt_action == "adding_buttons":
            draft = await db.update_draft_fields(
                update.effective_user.id,
                buttons=buttons_json_from_text(text),
                state="ready",
                prompt_action=None,
                prompt_chat_id=None,
                prompt_message_id=None,
            )
            await update.effective_message.reply_text(
                "<b>Buttons Saved</b>\n\nYour button layout has been updated.",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        elif draft.prompt_action == "setting_schedule":
            scheduled_iso = parse_schedule_input(text, settings)
            draft = await db.update_draft_fields(
                update.effective_user.id,
                scheduled_time=scheduled_iso,
                state="ready",
                prompt_action=None,
                prompt_chat_id=None,
                prompt_message_id=None,
            )
            await update.effective_message.reply_text(
                f"<b>Schedule Saved</b>\n\nPlanned for {html.escape(format_schedule_for_user(scheduled_iso, settings))}.",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        elif draft.prompt_action == "setting_channel":
            draft = await db.update_draft_fields(
                update.effective_user.id,
                channel_id=text,
                state="ready",
                prompt_action=None,
                prompt_chat_id=None,
                prompt_message_id=None,
            )
            await update.effective_message.reply_text(
                f"<b>Channel Saved</b>\n\nTarget set to {html.escape(text)}.",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        else:
            return
    except ValueError as exc:
        await update.effective_message.reply_text(
            f"<b>Input Error</b>\n\n{html.escape(str(exc))}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return
    except RuntimeError as exc:
        await update.effective_message.reply_text(
            f"<b>System Error</b>\n\n{html.escape(str(exc))}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    await update.effective_message.reply_text(
        build_post_menu_text(draft, settings),
        reply_markup=build_post_menu(draft, settings),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def preview_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return

    db: Database = context.application.bot_data["db"]
    draft = await db.get_or_create_draft(query.from_user.id)

    if not draft.has_content:
        await query.answer("Add content before previewing.", show_alert=True)
        return

    await query.answer()

    try:
        await send_post_message(
            query.message.reply_text,
            draft.content or "",
            keyboard_from_json(draft.buttons),
        )
    except BadRequest as exc:
        await query.message.reply_text(
            f"<b>Preview Error</b>\n\n{html.escape(str(exc))}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return


async def publish_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return

    db: Database = context.application.bot_data["db"]
    settings: Settings = context.application.bot_data["settings"]
    draft = await db.get_or_create_draft(query.from_user.id)

    missing: list[str] = []
    if not draft.has_content:
        missing.append("content")
    if not draft.has_channel:
        missing.append("channel")
    if missing:
        await query.answer(f"Missing: {', '.join(missing)}.", show_alert=True)
        return

    await query.answer()

    now_utc = datetime.now(timezone.utc)
    scheduled_dt = datetime.fromisoformat(draft.scheduled_time) if draft.scheduled_time else None

    if scheduled_dt and scheduled_dt > now_utc:
        post_id = await db.create_post(
            user_id=query.from_user.id,
            owner_chat_id=query.message.chat_id,
            channel_id=draft.channel_id or "",
            content=draft.content or "",
            buttons=draft.buttons,
            scheduled_time=draft.scheduled_time,
            status="pending",
        )
        logger.info(
            "Queued post %s for %s at %s",
            post_id,
            draft.channel_id,
            format_schedule_for_user(draft.scheduled_time, settings),
        )
        await db.delete_draft(query.from_user.id)
        await query.message.reply_text(
            (
                "<b>Post Scheduled</b>\n\n"
                f"<b>Channel:</b> {html.escape(draft.channel_id or '')}\n"
                f"<b>Time:</b> {html.escape(format_schedule_for_user(draft.scheduled_time, settings))}"
            ),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    try:
        await send_post_message(
            context.application.bot.send_message,
            draft.content or "",
            keyboard_from_json(draft.buttons),
            chat_id=draft.channel_id,
        )
    except (BadRequest, Forbidden, TelegramError) as exc:
        post_id = await db.create_post(
            user_id=query.from_user.id,
            owner_chat_id=query.message.chat_id,
            channel_id=draft.channel_id or "",
            content=draft.content or "",
            buttons=draft.buttons,
            scheduled_time=draft.scheduled_time,
            status="failed",
            failure_reason=str(exc),
        )
        logger.warning("Immediate publish failed for post %s: %s", post_id, exc)
        await query.message.reply_text(
            f"<b>Publish Failed</b>\n\n{html.escape(str(exc))}\n\nUse /pending to review unsent posts.",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    post_id = await db.create_post(
        user_id=query.from_user.id,
        owner_chat_id=query.message.chat_id,
        channel_id=draft.channel_id or "",
        content=draft.content or "",
        buttons=draft.buttons,
        scheduled_time=draft.scheduled_time,
        status="sent",
    )
    logger.info("Published post %s to %s", post_id, draft.channel_id)
    await db.delete_draft(query.from_user.id)
    await query.message.reply_text(
        f"<b>Post Published</b>\n\nSent to {html.escape(draft.channel_id or '')}.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def cancel_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return

    await query.answer()
    db: Database = context.application.bot_data["db"]
    await db.delete_draft(query.from_user.id)
    await query.message.reply_text(
        "<b>Draft Cancelled</b>\n\nUse /post to start again.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def refresh_menu_from_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return

    await query.answer()
    db: Database = context.application.bot_data["db"]
    draft = await db.get_or_create_draft(query.from_user.id)
    await refresh_menu(query, draft, context)


async def refresh_menu(query, draft: Draft, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not query.message:
        return
    await query.message.edit_text(
        build_post_menu_text(draft, settings),
        reply_markup=build_post_menu(draft, settings),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


def parse_schedule_input(value: str, settings: Settings) -> str:
    normalized = " ".join(value.strip().split())
    formats = [
        "%I:%M%p %d-%m-%Y",
        "%I:%M %p %d-%m-%Y",
    ]

    parsed_local = None
    for fmt in formats:
        try:
            parsed_local = datetime.strptime(normalized, fmt)
            break
        except ValueError:
            continue

    if parsed_local is None:
        raise ValueError("Use schedule format HH:MM AM/PM DD-MM-YYYY, for example 06:30 PM 23-03-2026.")

    localized = parsed_local.replace(tzinfo=settings.timezone)
    now_local = datetime.now(settings.timezone)
    if localized <= now_local:
        raise ValueError("Schedule must be in the future.")

    return localized.astimezone(timezone.utc).isoformat()


def format_schedule_for_user(value: str | None, settings: Settings) -> str:
    if not value:
        return "Not set"
    dt = datetime.fromisoformat(value).astimezone(settings.timezone)
    return dt.strftime("%I:%M %p %d-%m-%Y")


def compact_preview(content: str | None) -> str:
    if not content:
        return "(empty)"
    collapsed = " ".join(content.split())
    if len(collapsed) <= 70:
        return collapsed
    return f"{collapsed[:67]}..."
