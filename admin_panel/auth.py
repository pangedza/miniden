"""Вспомогательные функции для авторизации админов."""

from datetime import datetime, timedelta
from uuid import uuid4

import bcrypt
from sqlalchemy.orm import Session

from models import AdminSession, AdminUser

SESSION_TTL_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_session(db: Session, user: AdminUser, app_name: str) -> AdminSession:
    token = uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    session = AdminSession(user_id=user.id, token=token, expires_at=expires_at, app=app_name)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, token: str) -> None:
    db.query(AdminSession).filter(AdminSession.token == token).delete()
    db.commit()
