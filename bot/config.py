from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


TIMEZONE_ALIASES = {
    "Asia/Calcutta": "Asia/Kolkata",
}


@dataclass(slots=True)
class Settings:
    bot_token: str
    database_path: str = "bot.db"
    scheduler_interval_seconds: int = 5
    timezone_name: str = "UTC"

    @property
    def timezone(self) -> ZoneInfo:
        normalized_name = TIMEZONE_ALIASES.get(self.timezone_name, self.timezone_name)
        try:
            return ZoneInfo(normalized_name)
        except ZoneInfoNotFoundError as exc:
            raise RuntimeError(
                f"Invalid timezone '{self.timezone_name}'. Use a valid IANA timezone like 'Asia/Kolkata'."
            ) from exc


def get_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN environment variable is required.")

    database_path = os.getenv("DATABASE_PATH", "bot.db").strip() or "bot.db"
    timezone_name = os.getenv("DEFAULT_TIMEZONE", "UTC").strip() or "UTC"
    interval_raw = os.getenv("SCHEDULER_INTERVAL_SECONDS", "5").strip() or "5"

    try:
        interval = max(1, int(interval_raw))
    except ValueError as exc:
        raise RuntimeError("SCHEDULER_INTERVAL_SECONDS must be an integer.") from exc

    return Settings(
        bot_token=bot_token,
        database_path=database_path,
        scheduler_interval_seconds=interval,
        timezone_name=timezone_name,
    )
