from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bot.models.draft import Draft


POST_OPTIONAL_COLUMNS = {
    "user_id": "INTEGER",
    "owner_chat_id": "INTEGER",
    "failure_reason": "TEXT",
    "sent_at": "TEXT",
}


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    channel_id TEXT,
                    content TEXT,
                    buttons TEXT,
                    scheduled_time TEXT,
                    state TEXT NOT NULL DEFAULT 'ready',
                    prompt_action TEXT,
                    prompt_chat_id INTEGER,
                    prompt_message_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    owner_chat_id INTEGER,
                    channel_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    buttons TEXT,
                    scheduled_time TEXT,
                    status TEXT NOT NULL,
                    failure_reason TEXT,
                    sent_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._ensure_post_columns(connection)

    def _ensure_post_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(posts)").fetchall()
        }
        for column_name, column_type in POST_OPTIONAL_COLUMNS.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE posts ADD COLUMN {column_name} {column_type}"
                )

    async def get_or_create_draft(self, user_id: int) -> Draft:
        return await asyncio.to_thread(self._get_or_create_draft_sync, user_id)

    def _get_or_create_draft_sync(self, user_id: int) -> Draft:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM drafts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                now = utc_now_iso()
                cursor = connection.execute(
                    """
                    INSERT INTO drafts (
                        user_id, channel_id, content, buttons, scheduled_time, state,
                        prompt_action, prompt_chat_id, prompt_message_id, created_at, updated_at
                    ) VALUES (?, NULL, NULL, NULL, NULL, 'ready', NULL, NULL, NULL, ?, ?)
                    """,
                    (user_id, now, now),
                )
                row = connection.execute(
                    "SELECT * FROM drafts WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
            return row_to_draft(row)

    async def get_draft(self, user_id: int) -> Draft | None:
        return await asyncio.to_thread(self._get_draft_sync, user_id)

    def _get_draft_sync(self, user_id: int) -> Draft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM drafts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return row_to_draft(row) if row else None

    async def update_draft_fields(self, user_id: int, **fields: Any) -> Draft:
        return await asyncio.to_thread(self._update_draft_fields_sync, user_id, fields)

    def _update_draft_fields_sync(self, user_id: int, fields: dict[str, Any]) -> Draft:
        if not fields:
            raise ValueError("No draft fields provided for update.")

        assignments = [f"{key} = ?" for key in fields]
        values = list(fields.values())
        values.extend([utc_now_iso(), user_id])

        with self._connect() as connection:
            connection.execute(
                f"UPDATE drafts SET {', '.join(assignments)}, updated_at = ? WHERE user_id = ?",
                values,
            )
            row = connection.execute(
                "SELECT * FROM drafts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Draft not found after update.")
            return row_to_draft(row)

    async def delete_draft(self, user_id: int) -> None:
        await asyncio.to_thread(self._delete_draft_sync, user_id)

    def _delete_draft_sync(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM drafts WHERE user_id = ?", (user_id,))

    async def create_post(
        self,
        *,
        user_id: int | None,
        owner_chat_id: int | None,
        channel_id: str,
        content: str,
        buttons: str | None,
        scheduled_time: str | None,
        status: str,
        failure_reason: str | None = None,
    ) -> int:
        return await asyncio.to_thread(
            self._create_post_sync,
            user_id,
            owner_chat_id,
            channel_id,
            content,
            buttons,
            scheduled_time,
            status,
            failure_reason,
        )

    def _create_post_sync(
        self,
        user_id: int | None,
        owner_chat_id: int | None,
        channel_id: str,
        content: str,
        buttons: str | None,
        scheduled_time: str | None,
        status: str,
        failure_reason: str | None,
    ) -> int:
        now = utc_now_iso()
        sent_at = now if status == "sent" else None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO posts (
                    user_id, owner_chat_id, channel_id, content, buttons, scheduled_time,
                    status, failure_reason, sent_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    owner_chat_id,
                    channel_id,
                    content,
                    buttons,
                    scheduled_time,
                    status,
                    failure_reason,
                    sent_at,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    async def get_due_posts(self, now_utc: datetime) -> list[sqlite3.Row]:
        return await asyncio.to_thread(self._get_due_posts_sync, now_utc.isoformat())

    def _get_due_posts_sync(self, now_utc_iso: str) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT * FROM posts
                    WHERE status = 'pending' AND scheduled_time IS NOT NULL AND scheduled_time <= ?
                    ORDER BY scheduled_time ASC, id ASC
                    """,
                    (now_utc_iso,),
                ).fetchall()
            )

    async def get_unsent_posts_for_user(self, user_id: int) -> list[sqlite3.Row]:
        return await asyncio.to_thread(self._get_unsent_posts_for_user_sync, user_id)

    def _get_unsent_posts_for_user_sync(self, user_id: int) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT * FROM posts
                    WHERE user_id = ? AND status IN ('pending', 'failed')
                    ORDER BY
                        CASE status WHEN 'failed' THEN 0 ELSE 1 END,
                        COALESCE(scheduled_time, created_at) ASC,
                        id ASC
                    """,
                    (user_id,),
                ).fetchall()
            )

    async def mark_post_sent(self, post_id: int) -> None:
        await asyncio.to_thread(self._mark_post_sent_sync, post_id)

    def _mark_post_sent_sync(self, post_id: int) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE posts
                SET status = 'sent', failure_reason = NULL, sent_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, post_id),
            )

    async def mark_post_failed(self, post_id: int, failure_reason: str | None) -> None:
        await asyncio.to_thread(self._mark_post_failed_sync, post_id, failure_reason)

    def _mark_post_failed_sync(self, post_id: int, failure_reason: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE posts
                SET status = 'failed', failure_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (failure_reason, utc_now_iso(), post_id),
            )


def row_to_draft(row: sqlite3.Row) -> Draft:
    return Draft(
        id=row["id"],
        user_id=row["user_id"],
        channel_id=row["channel_id"],
        content=row["content"],
        buttons=row["buttons"],
        scheduled_time=row["scheduled_time"],
        state=row["state"],
        prompt_action=row["prompt_action"],
        prompt_chat_id=row["prompt_chat_id"],
        prompt_message_id=row["prompt_message_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
