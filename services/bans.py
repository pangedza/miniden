from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import select

from database import get_session
from models import UserBan


def ban_user(user_id: int, reason: str | None = None) -> UserBan:
    with get_session() as session:
        active_ban = session.scalar(
            select(UserBan).where(UserBan.user_id == user_id, UserBan.active.is_(True))
        )
        if active_ban:
            active_ban.reason = reason or active_ban.reason
            active_ban.banned_at = datetime.utcnow()
            session.flush()
            session.refresh(active_ban)
            return active_ban

        record = UserBan(
            user_id=user_id,
            reason=reason,
            banned_at=datetime.utcnow(),
            active=True,
        )
        session.add(record)
        session.flush()
        session.refresh(record)
        return record


def unban_user(user_id: int) -> bool:
    with get_session() as session:
        bans: List[UserBan] = session.scalars(
            select(UserBan).where(UserBan.user_id == user_id, UserBan.active.is_(True))
        ).all()
        if not bans:
            return False
        for ban in bans:
            ban.active = False
        return True


def is_banned(user_id: int) -> dict:
    with get_session() as session:
        ban = session.scalar(
            select(UserBan)
            .where(UserBan.user_id == user_id, UserBan.active.is_(True))
            .order_by(UserBan.banned_at.desc(), UserBan.id.desc())
        )
        if not ban:
            return {
                "is_banned": False,
                "reason": None,
                "ban_reason": None,
                "banned_at": None,
            }
    return {
        "is_banned": True,
        "reason": ban.reason,
        "ban_reason": ban.reason,
        "banned_at": ban.banned_at.isoformat() if ban.banned_at else None,
    }


def list_banned(limit: int = 100) -> list[dict]:
    with get_session() as session:
        rows = session.scalars(
            select(UserBan)
            .where(UserBan.active.is_(True))
            .order_by(UserBan.banned_at.desc(), UserBan.id.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "reason": row.reason,
                "banned_at": row.banned_at.isoformat() if row.banned_at else None,
                "active": bool(row.active),
            }
            for row in rows
        ]
