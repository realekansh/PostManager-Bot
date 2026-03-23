from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


BUTTON_PATTERN = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<url>[^)\s]+)\)")


def parse_button_lines(raw_text: str) -> list[list[dict[str, str]]]:
    rows: list[list[dict[str, str]]] = []

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        matches = list(BUTTON_PATTERN.finditer(stripped))
        if not matches:
            raise ValueError(f"Invalid button format in line: {line}")

        consumed = "".join(match.group(0) for match in matches)
        if consumed.replace(" ", "") != stripped.replace(" ", ""):
            raise ValueError(f"Unsupported button text in line: {line}")

        row: list[dict[str, str]] = []
        for match in matches:
            label = match.group("label").strip()
            url = match.group("url").strip()
            validate_button_url(url)
            row.append({"text": label, "url": url})
        rows.append(row)

    if not rows:
        raise ValueError("Please provide at least one button.")

    return rows


def validate_button_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")


def keyboard_from_rows(rows: list[list[dict[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=button["text"], url=button["url"]) for button in row]
            for row in rows
        ]
    )


def keyboard_from_json(raw_json: str | None) -> InlineKeyboardMarkup | None:
    if not raw_json:
        return None
    rows = json.loads(raw_json)
    return keyboard_from_rows(rows)


def buttons_json_from_text(raw_text: str) -> str:
    return json.dumps(parse_button_lines(raw_text))


def button_summary(raw_json: str | None) -> str:
    if not raw_json:
        return "Not set"
    rows: list[list[dict[str, Any]]] = json.loads(raw_json)
    count = sum(len(row) for row in rows)
    return f"{count} button(s) across {len(rows)} row(s)"
