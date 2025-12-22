"""Общие зависимости для маршрутов админок."""

from typing import Iterable, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from models.admin_user import AdminRole, AdminUser
from services import auth as auth_service


SESSION_COOKIE_NAME = "admin_session"


def get_db_session() -> Session:
    from database import SessionLocal  # импорт внутри, чтобы избежать циклов

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_admin(request: Request, db: Session) -> Optional[AdminUser]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    session = auth_service.get_session(db, token)
    return session.user if session else None


def require_admin(
    request: Request,
    db: Session,
    roles: Iterable[AdminRole] | None = None,
) -> Optional[AdminUser]:
    user = get_current_admin(request=request, db=db)
    if not user:
        return None

    if roles is None:
        return user

    role_values = {role.value if isinstance(role, AdminRole) else role for role in roles}
    if any(code in role_values for code in user.role_codes()):
        return user

    return None
