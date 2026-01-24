from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import ADMIN_IDS_SET
from database import get_session
from initdb import init_db
from models import User
from utils.phone import normalize_phone


def _extract_phone(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    phone = data.get("phone") or data.get("phone_number")
    if phone:
        try:
            return normalize_phone(str(phone))
        except ValueError:
            return None
    return None


def _split_full_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.split(" ", 1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def _get_or_create_user(
    session: Session,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
) -> User:
    is_admin_flag = telegram_id in ADMIN_IDS_SET

    normalized_phone = None
    if phone:
        try:
            normalized_phone = normalize_phone(phone)
        except ValueError:
            normalized_phone = None

    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        user.username = username or user.username
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        if normalized_phone:
            user.phone = normalized_phone
        user.is_admin = is_admin_flag or user.is_admin
    else:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=normalized_phone,
            is_admin=is_admin_flag,
            created_at=datetime.utcnow(),
        )
        session.add(user)
        session.flush()
    session.refresh(user)
    return user


def _merge_users(session: Session, target: User, source: User) -> User:
    """Merge two user records, keeping the target user id."""

    if source.id == target.id:
        return target

    if target.telegram_id is None and source.telegram_id is not None:
        target.telegram_id = source.telegram_id
    if not target.username and source.username:
        target.username = source.username
    if not target.first_name and source.first_name:
        target.first_name = source.first_name
    if not target.last_name and source.last_name:
        target.last_name = source.last_name
    if not target.phone and source.phone:
        target.phone = source.phone
    target.is_admin = target.is_admin or source.is_admin

    session.delete(source)
    session.flush()
    session.refresh(target)
    return target


def get_or_create_user_by_phone(session: Session, phone: str) -> User:
    """Find or create a user by normalized phone."""

    normalized_phone = normalize_phone(phone)
    user = session.scalar(select(User).where(User.phone == normalized_phone))
    if user:
        return user

    user = User(phone=normalized_phone, created_at=datetime.utcnow())
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        user = session.scalar(select(User).where(User.phone == normalized_phone))
        if not user:
            raise
    session.refresh(user)
    return user


def attach_telegram_id(
    session: Session,
    *,
    user: User,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """Attach a telegram_id to an existing user, merging duplicates if needed."""

    telegram_id = int(telegram_id)
    is_admin_flag = telegram_id in ADMIN_IDS_SET

    other = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if other and other.id != user.id:
        if other.phone and user.phone and other.phone != user.phone:
            raise HTTPException(status_code=409, detail="telegram_id_conflict")
        user = _merge_users(session, target=user, source=other)

    user.telegram_id = telegram_id
    user.username = username or user.username
    user.first_name = first_name or user.first_name
    user.last_name = last_name or user.last_name
    user.is_admin = is_admin_flag or user.is_admin
    session.flush()
    session.refresh(user)
    return user


def get_or_create_user_from_telegram(
    data: dict[str, Any] | Session | None,
    telegram_id: int | None = None,
    username: str | None = None,
    full_name: str | None = None,
    phone: str | None = None,
) -> User:
    # New signature supports passing an existing session for WebApp auth
    if isinstance(data, Session):
        if telegram_id is None:
            raise ValueError("Telegram user id is required")

        first_name, last_name = _split_full_name(full_name)
        return _get_or_create_user(
            data,
            telegram_id=int(telegram_id),
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )

    if not data or "id" not in data:
        raise ValueError("Telegram user data is required")

    telegram_id = int(data["id"])
    username = data.get("username")
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    phone = _extract_phone(data)

    init_db()
    with get_session() as session:
        return _get_or_create_user(
            session,
            telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )


def update_user_contact(telegram_id: int, phone: str | None) -> User:
    init_db()
    with get_session() as session:
        user = session.scalar(select(User).where(User.telegram_id == telegram_id))
        if not user:
            raise ValueError("User not found")
        if phone:
            user.phone = normalize_phone(phone)
        else:
            user.phone = None
        session.refresh(user)
        return user


def get_user_by_telegram_id(telegram_id: int) -> User | None:
    init_db()
    with get_session() as session:
        return session.scalar(select(User).where(User.telegram_id == telegram_id))


def get_user_by_phone(phone: str) -> User | None:
    init_db()
    normalized_phone = normalize_phone(phone)
    with get_session() as session:
        return session.scalar(select(User).where(User.phone == normalized_phone))


def get_user_by_phone_or_telegram(
    session: Session,
    *,
    phone: str | None = None,
    telegram_id: int | None = None,
) -> User | None:
    filters = []
    if phone:
        filters.append(User.phone == normalize_phone(phone))
    if telegram_id is not None:
        filters.append(User.telegram_id == int(telegram_id))
    if not filters:
        return None
    return session.scalar(select(User).where(or_(*filters)))


def is_admin(telegram_id: int) -> bool:
    user = get_user_by_telegram_id(int(telegram_id))
    if not user:
        return False
    return bool(user.is_admin)
