from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from database import get_session
from initdb import init_db
from models import AuthSession


def create_token() -> str:
    token = str(uuid4())
    init_db()
    with get_session() as session:
        session.add(AuthSession(token=token))
    return token


def get_session_by_token(token: str) -> AuthSession | None:
    init_db()
    with get_session() as session:
        return session.scalar(select(AuthSession).where(AuthSession.token == token))


def attach_telegram_id(token: str, telegram_id: int) -> bool:
    init_db()
    with get_session() as session:
        auth_session = session.scalar(select(AuthSession).where(AuthSession.token == token))
        if not auth_session:
            return False
        auth_session.telegram_id = int(telegram_id)
        return True
