from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import select

from database import get_session
from models import WebChatMessage, WebChatSession


def _refresh_session(db_session, chat_session: WebChatSession) -> WebChatSession:
    db_session.flush()
    db_session.refresh(chat_session)
    return chat_session


def _add_message(chat_session: WebChatSession, sender: str, text: str) -> WebChatMessage:
    with get_session() as db:
        session_obj = db.get(WebChatSession, chat_session.id)
        if not session_obj:
            raise ValueError("session_not_found")

        session_obj.updated_at = datetime.utcnow()
        message = WebChatMessage(
            session_id=session_obj.id,
            sender=sender,
            text=text,
            created_at=datetime.utcnow(),
        )
        db.add(message)
        _refresh_session(db, session_obj)
        db.flush()
        db.refresh(message)
        return message


def _populate_session_key(session: WebChatSession, session_key: str) -> None:
    if session.session_key and session.session_key == session_key:
        return

    session.session_key = session_key
    if not session.session_id:
        session.session_id = session_key


def _apply_metadata(
    session: WebChatSession,
    user_identifier: Optional[str] = None,
    user_agent: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> None:
    updated = False
    if user_identifier and session.user_identifier != user_identifier:
        session.user_identifier = user_identifier
        updated = True
    if user_agent and session.user_agent != user_agent:
        session.user_agent = user_agent
        updated = True
    if client_ip and session.client_ip != client_ip:
        session.client_ip = client_ip
        updated = True
    if updated:
        session.updated_at = datetime.utcnow()


def get_or_create_session(
    session_key: str,
    *,
    user_identifier: Optional[str] = None,
    user_agent: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> WebChatSession:
    with get_session() as db:
        existing = db.scalars(
            select(WebChatSession).where(
                (WebChatSession.session_key == session_key)
                | (WebChatSession.session_id == session_key)
            )
        ).first()
        if existing:
            _populate_session_key(existing, session_key)
            _apply_metadata(existing, user_identifier, user_agent, client_ip)
            db.flush()
            db.refresh(existing)
            return existing

        new_session = WebChatSession(
            session_id=session_key,
            session_key=session_key,
            user_identifier=user_identifier,
            user_agent=user_agent,
            client_ip=client_ip,
            status="open",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(new_session)
        return _refresh_session(db, new_session)


def add_user_message(session: WebChatSession, text: str) -> WebChatMessage:
    return _add_message(session, "user", text)


def add_manager_message(session: WebChatSession, text: str) -> WebChatMessage:
    return _add_message(session, "manager", text)


def add_system_message(session: WebChatSession, text: str) -> WebChatMessage:
    return _add_message(session, "system", text)


def get_session_by_key(session_key: str) -> WebChatSession | None:
    with get_session() as db:
        return db.scalars(
            select(WebChatSession).where(
                (WebChatSession.session_key == session_key)
                | (WebChatSession.session_id == session_key)
            )
        ).first()


def get_session_by_id(session_id: int | str) -> WebChatSession | None:
    try:
        numeric_id = int(session_id)
    except (TypeError, ValueError):
        return None

    with get_session() as db:
        return db.get(WebChatSession, numeric_id)


def get_messages(session: WebChatSession, limit: int = 50) -> list[WebChatMessage]:
    with get_session() as db:
        query = select(WebChatMessage).where(WebChatMessage.session_id == session.id)
        query = query.order_by(WebChatMessage.created_at.asc(), WebChatMessage.id.asc())
        if limit:
            query = query.limit(limit)

        records: Iterable[WebChatMessage] = db.scalars(query).all()

    return list(records)


def mark_waiting_manager(session: WebChatSession) -> None:
    with get_session() as db:
        chat_session = db.get(WebChatSession, session.id)
        if not chat_session:
            return
        chat_session.status = "waiting_manager"
        chat_session.updated_at = datetime.utcnow()


def mark_closed(session: WebChatSession) -> None:
    with get_session() as db:
        chat_session = db.get(WebChatSession, session.id)
        if not chat_session:
            return
        chat_session.status = "closed"
        chat_session.updated_at = datetime.utcnow()


def mark_open(session: WebChatSession) -> None:
    with get_session() as db:
        chat_session = db.get(WebChatSession, session.id)
        if not chat_session:
            return
        chat_session.status = "open"
        chat_session.updated_at = datetime.utcnow()


def set_thread_message_id(session: WebChatSession, message_id: int | None) -> None:
    with get_session() as db:
        chat_session = db.get(WebChatSession, session.id)
        if not chat_session:
            return
        chat_session.telegram_thread_message_id = message_id
        chat_session.updated_at = datetime.utcnow()
