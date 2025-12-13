from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import or_, select

from database import get_session
from models import WebChatMessage, WebChatSession


def _refresh_session(db_session, chat_session: WebChatSession) -> WebChatSession:
    db_session.flush()
    db_session.refresh(chat_session)
    return chat_session


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
            existing.last_message_at = existing.last_message_at or existing.updated_at
            db.flush()
            db.refresh(existing)
            return existing

        now = datetime.utcnow()
        new_session = WebChatSession(
            session_id=session_key,
            session_key=session_key,
            user_identifier=user_identifier,
            user_agent=user_agent,
            client_ip=client_ip,
            status="open",
            created_at=now,
            updated_at=now,
            last_message_at=now,
            unread_for_manager=0,
        )
        db.add(new_session)
        return _refresh_session(db, new_session)


def _update_read_flags(message: WebChatMessage, sender: str) -> None:
    if sender == "user":
        message.is_read_by_client = True
        message.is_read_by_manager = False
    elif sender == "manager":
        message.is_read_by_manager = True
        message.is_read_by_client = False
    else:
        message.is_read_by_manager = True
        message.is_read_by_client = True


def _add_message(chat_session: WebChatSession, sender: str, text: str) -> WebChatMessage:
    with get_session() as db:
        session_obj = db.get(WebChatSession, chat_session.id)
        if not session_obj:
            raise ValueError("session_not_found")

        now = datetime.utcnow()
        session_obj.updated_at = now
        session_obj.last_message_at = now

        if sender == "user":
            session_obj.unread_for_manager = (session_obj.unread_for_manager or 0) + 1
            if session_obj.status != "closed":
                session_obj.status = "waiting_manager"
        elif sender == "manager":
            session_obj.unread_for_manager = 0
            if session_obj.status != "closed":
                session_obj.status = "open"

        message = WebChatMessage(
            session_id=session_obj.id,
            sender=sender,
            text=text,
            created_at=now,
        )
        _update_read_flags(message, sender)
        db.add(message)
        _refresh_session(db, session_obj)
        db.flush()
        db.refresh(message)
        return message


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


def _mark_messages_read_by_manager(
    db, session_obj: WebChatSession, *, last_read_message_id: int | None = None
) -> None:
    updated = False
    query = select(WebChatMessage).where(
        WebChatMessage.session_id == session_obj.id,
        WebChatMessage.is_read_by_manager.is_(False),
    )
    if last_read_message_id:
        query = query.where(WebChatMessage.id <= last_read_message_id)

    unread_messages = db.scalars(query).all()
    for msg in unread_messages:
        msg.is_read_by_manager = True
        updated = True

    if session_obj.unread_for_manager:
        session_obj.unread_for_manager = 0
        updated = True

    if updated:
        session_obj.updated_at = datetime.utcnow()


def _mark_messages_read_by_client(db, session_obj: WebChatSession) -> None:
    unread_messages = db.scalars(
        select(WebChatMessage).where(
            WebChatMessage.session_id == session_obj.id,
            WebChatMessage.sender != "user",
            WebChatMessage.is_read_by_client.is_(False),
        )
    ).all()
    for msg in unread_messages:
        msg.is_read_by_client = True

    if unread_messages:
        session_obj.updated_at = datetime.utcnow()


def get_messages(
    session: WebChatSession,
    limit: int | None = 50,
    *,
    after_id: int = 0,
    mark_read_for: str | None = None,
    last_read_message_id: int | None = None,
) -> list[WebChatMessage]:
    with get_session() as db:
        session_obj = db.get(WebChatSession, session.id)
        if not session_obj:
            return []

        query = select(WebChatMessage).where(WebChatMessage.session_id == session_obj.id)
        if after_id:
            query = query.where(WebChatMessage.id > after_id)
        query = query.order_by(WebChatMessage.created_at.asc(), WebChatMessage.id.asc())
        if limit:
            query = query.limit(limit)

        records: Iterable[WebChatMessage] = db.scalars(query).all()

        if mark_read_for == "manager":
            _mark_messages_read_by_manager(
                db, session_obj, last_read_message_id=last_read_message_id
            )
        elif mark_read_for == "client":
            _mark_messages_read_by_client(db, session_obj)

        db.flush()

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


def list_sessions(
    *, status: str | None = None, limit: int | None = 100, search: str | None = None, page: int = 1
) -> list[tuple[WebChatSession, WebChatMessage | None]]:
    with get_session() as db:
        query = select(WebChatSession)
        if status and status != "all":
            query = query.where(WebChatSession.status == status)
        if search:
            like = f"%{search}%"
            query = query.where(
                or_(
                    WebChatSession.session_key.ilike(like),
                    WebChatSession.user_identifier.ilike(like),
                    WebChatSession.client_ip.ilike(like),
                )
            )

        page = max(page, 1)
        if limit:
            query = query.limit(limit).offset((page - 1) * limit)

        query = query.order_by(
            WebChatSession.last_message_at.desc().nullslast(),
            WebChatSession.updated_at.desc(),
            WebChatSession.id.desc(),
        )

        sessions: list[WebChatSession] = list(db.scalars(query).all())
        last_messages: dict[int, WebChatMessage | None] = {}

        for session in sessions:
            last_messages[int(session.id)] = db.scalars(
                select(WebChatMessage)
                .where(WebChatMessage.session_id == session.id)
                .order_by(WebChatMessage.created_at.desc(), WebChatMessage.id.desc())
                .limit(1)
            ).first()

    return [(session, last_messages.get(int(session.id))) for session in sessions]


def get_messages_by_session_id(
    session_id: int,
    *,
    limit: int | None = None,
    after_id: int = 0,
    mark_read_for: str | None = None,
    last_read_message_id: int | None = None,
) -> list[WebChatMessage]:
    session = get_session_by_id(session_id)
    if not session:
        return []
    return get_messages(
        session,
        limit=limit or 0,
        after_id=after_id,
        mark_read_for=mark_read_for,
        last_read_message_id=last_read_message_id,
    )


def close_session(session_id: int) -> bool:
    session = get_session_by_id(session_id)
    if not session:
        return False
    mark_closed(session)
    return True


def mark_read_for_manager(session_id: int, *, last_read_message_id: int | None = None) -> bool:
    """Mark messages as read for manager side and reset unread counter."""

    with get_session() as db:
        session_obj = db.get(WebChatSession, session_id)
        if not session_obj:
            return False

        _mark_messages_read_by_manager(
            db, session_obj, last_read_message_id=last_read_message_id
        )
        db.flush()

    return True
