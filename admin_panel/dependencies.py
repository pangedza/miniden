"""Общие зависимости для маршрутов админок."""

from datetime import datetime
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from models import AdminSession, AdminUser


COOKIE_NAMES = {
    "adminbot": "adminbot_session",
    "adminsite": "adminsite_session",
}


def get_db_session() -> Session:
    from database import SessionLocal  # импорт внутри, чтобы избежать циклов

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_admin(
    request: Request, db: Session, app_name: str
) -> Optional[AdminUser]:
    cookie_name = COOKIE_NAMES.get(app_name)
    if not cookie_name:
        return None

    token = request.cookies.get(cookie_name)
    if not token:
        return None

    session = (
        db.query(AdminSession)
        .filter(AdminSession.token == token, AdminSession.app == app_name)
        .first()
    )
    if not session:
        return None

    if session.expires_at <= datetime.utcnow():
        db.delete(session)
        db.commit()
        return None

    if not session.user or not session.user.is_active:
        return None

    return session.user


def require_admin(request: Request, db: Session, app_name: str) -> Optional[AdminUser]:
    return get_current_admin(request=request, db=db, app_name=app_name)
