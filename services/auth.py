"""Логика аутентификации админов."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from models.admin_user import AdminRole, AdminSession, AdminUser
from services.passwords import verify_password

SESSION_TTL_HOURS = 24


def authenticate_admin(
    db: Session, username: str, password: str
) -> Optional[AdminUser]:
    user: AdminUser | None = (
        db.query(AdminUser).filter(AdminUser.username == username).first()
    )
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: Session, user: AdminUser) -> AdminSession:
    token = uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    session = AdminSession(user_id=user.id, token=token, expires_at=expires_at)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def remove_session(db: Session, token: str) -> None:
    db.query(AdminSession).filter(AdminSession.token == token).delete()
    db.commit()


def get_session(db: Session, token: str) -> Optional[AdminSession]:
    session = db.query(AdminSession).filter(AdminSession.token == token).first()
    if not session:
        return None
    if session.expires_at <= datetime.utcnow():
        db.delete(session)
        db.commit()
        return None
    if not session.user or not session.user.is_active:
        return None
    return session


def invalidate_user_sessions(db: Session, user_id: int) -> None:
    db.query(AdminSession).filter(AdminSession.user_id == user_id).delete()
    db.commit()


__all__ = [
    "authenticate_admin",
    "create_session",
    "get_session",
    "invalidate_user_sessions",
    "remove_session",
    "SESSION_TTL_HOURS",
    "AdminRole",
]
