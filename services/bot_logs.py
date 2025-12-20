from __future__ import annotations

from datetime import datetime, time
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from models import BotLog


def _parse_int(value: str | int | None) -> Optional[int]:
    try:
        return int(value) if value is not None and value != "" else None
    except Exception:
        return None


def _normalize_date(value: str | None, is_end: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if is_end:
            return datetime.combine(parsed.date(), time.max)
        return datetime.combine(parsed.date(), time.min)
    except Exception:
        return None


def fetch_logs(
    db: Session,
    *,
    page: int = 1,
    per_page: int = 50,
    user_id: str | int | None = None,
    username: str | None = None,
    event_type: str | None = None,
    node_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[BotLog], int]:
    page = max(page, 1)
    per_page = max(per_page, 1)

    query = db.query(BotLog)

    normalized_user_id = _parse_int(user_id)
    if normalized_user_id:
        query = query.filter(BotLog.user_id == normalized_user_id)

    normalized_username = (username or "").strip()
    if normalized_username:
        query = query.filter(BotLog.username.ilike(f"%{normalized_username}%"))

    normalized_event = (event_type or "").strip().upper()
    if normalized_event:
        query = query.filter(BotLog.event_type == normalized_event)

    normalized_node_code = (node_code or "").strip()
    if normalized_node_code:
        query = query.filter(BotLog.node_code.ilike(f"%{normalized_node_code}%"))

    start_date = _normalize_date(date_from)
    if start_date:
        query = query.filter(BotLog.created_at >= start_date)

    end_date = _normalize_date(date_to, is_end=True)
    if end_date:
        query = query.filter(BotLog.created_at <= end_date)

    total = query.count()
    rows = (
        query.order_by(BotLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return rows, total


def fetch_user_history(
    db: Session,
    *,
    user_id: int,
    limit: int = 300,
    event_types: Iterable[str] | None = None,
) -> list[BotLog]:
    query = db.query(BotLog).filter(BotLog.user_id == user_id)

    if event_types:
        normalized = [event.upper() for event in event_types]
        query = query.filter(BotLog.event_type.in_(normalized))

    return query.order_by(BotLog.created_at.asc()).limit(limit).all()
