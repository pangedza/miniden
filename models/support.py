from datetime import datetime

from pydantic import BaseModel


class SupportMessage(BaseModel):
    id: int
    text: str
    sender: str
    created_at: datetime | None = None


class SupportSession(BaseModel):
    session_id: int
    session_key: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_message: str | None = None
    last_sender: str | None = None


class SupportMessageList(BaseModel):
    items: list[SupportMessage]


class SupportSessionList(BaseModel):
    items: list[SupportSession]


class WebChatMessagesResponse(BaseModel):
    ok: bool
    status: str
    messages: list[SupportMessage]
