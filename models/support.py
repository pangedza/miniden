from datetime import datetime

from pydantic import BaseModel


class SupportMessage(BaseModel):
    id: int
    text: str
    sender: str
    created_at: datetime | None = None
    is_read_by_manager: bool | None = None
    is_read_by_client: bool | None = None


class SupportSession(BaseModel):
    session_id: int
    session_key: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_message_at: datetime | None = None
    last_message: str | None = None
    last_sender: str | None = None
    unread_for_manager: int | None = 0


class SupportSessionDetail(BaseModel):
    session: SupportSession
    messages: list[SupportMessage]


class SupportMessageList(BaseModel):
    items: list[SupportMessage]


class SupportSessionList(BaseModel):
    items: list[SupportSession]


class WebChatMessagesResponse(BaseModel):
    ok: bool
    status: str
    messages: list[SupportMessage]
