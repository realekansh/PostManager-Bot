# Telegram Post Management Bot

Async Telegram channel post manager built with `python-telegram-bot v20`, SQLite, and an in-process scheduler.

## Features

- Draft posts with content, buttons, channel target, and optional schedule
- Input state is remembered until the next message is sent
- Preview before publishing
- SQLite-backed scheduled posts that survive restarts
- Delivery tracking for sent, pending, and failed posts
- `/pending` command to review unsent posts
- Background scheduler loop that checks due posts every 5 seconds
- Rich post formatting support for bold, italic, underline, strikethrough, spoilers, inline code, fenced code blocks, block quotes, and text links

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables in `.env`:

   - `BOT_TOKEN`
   - `DATABASE_PATH` (optional, defaults to `bot.db`)
   - `DEFAULT_TIMEZONE` (optional, defaults to `UTC`)
   - `SCHEDULER_INTERVAL_SECONDS` (optional, defaults to `5`)

3. Start the bot:

   ```bash
   python -m bot.main
   ```

## Commands

- `/start` shows the intro
- `/post` opens the draft workspace
- `/pending` shows unsent pending or failed posts

## Scheduling

- Schedule input format: `HH:MM AM/PM DD-MM-YYYY`
- The bot interprets schedules in `DEFAULT_TIMEZONE`
- Due posts are sent by the in-process scheduler and marked `sent` or `failed`
- Failed scheduled posts are kept for review and can be inspected with `/pending`

## Formatting

Supported content patterns:

- `*bold*`
- `_italic_`
- `__underline__`
- `~strikethrough~`
- `||spoiler||`
- `` `inline code` ``
- fenced code blocks with triple backticks
- quote blocks with `>` at the start of each line
- text links like `[Docs](https://example.com)`

## Development

Install test dependencies if you want to run the formatter tests:

```bash
pip install -r requirements-dev.txt
pytest tests/test_markdown.py
```
