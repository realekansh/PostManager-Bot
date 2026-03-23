from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Draft:
    id: int
    user_id: int
    channel_id: str | None
    content: str | None
    buttons: str | None
    scheduled_time: str | None
    state: str
    prompt_action: str | None
    prompt_chat_id: int | None
    prompt_message_id: int | None
    created_at: str
    updated_at: str

    @property
    def has_content(self) -> bool:
        return bool(self.content and self.content.strip())

    @property
    def has_channel(self) -> bool:
        return bool(self.channel_id and self.channel_id.strip())

    @property
    def has_buttons(self) -> bool:
        return bool(self.buttons and self.buttons.strip())

    @property
    def is_scheduled(self) -> bool:
        return bool(self.scheduled_time)
