from __future__ import annotations

from datetime import datetime
from datetime import datetime
from typing import Any

from sqlalchemy import select

from config import ADMIN_IDS_SET
from database import get_session, init_db
from models import User


def _extract_phone(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    phone = data.get("phone") or data.get("phone_number")
    if phone:
        return str(phone)
    return None


def get_or_create_user_from_telegram(data: dict[str, Any] | None) -> User:
    if not data or "id" not in data:
        raise ValueError("Telegram user data is required")

    telegram_id = int(data["id"])
    username = data.get("username")
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    phone = _extract_phone(data)
    is_admin_flag = telegram_id in ADMIN_IDS_SET

    init_db()
    with get_session() as session:
        user = session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user:
            user.username = username or user.username
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.phone = phone or user.phone
            user.is_admin = is_admin_flag or user.is_admin
        else:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                is_admin=is_admin_flag,
                created_at=datetime.utcnow(),
            )
            session.add(user)
            session.flush()
        session.refresh(user)
        return user


def update_user_contact(telegram_id: int, phone: str | None) -> User:
    init_db()
    with get_session() as session:
        user = session.scalar(select(User).where(User.telegram_id == telegram_id))
        if not user:
            raise ValueError("User not found")
        user.phone = phone
        session.refresh(user)
        return user


def get_user_by_telegram_id(telegram_id: int) -> User | None:
    init_db()
    with get_session() as session:
        return session.scalar(select(User).where(User.telegram_id == telegram_id))


def is_admin(telegram_id: int) -> bool:
    user = get_user_by_telegram_id(int(telegram_id))
    if not user:
        return False
    return bool(user.is_admin)
