from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from database import get_session, init_db
from models import Order
from services import orders as orders_service


def get_user_order_stats(user_id: int) -> dict[str, Any]:
    """Подсчитать статистику по заказам пользователя для CRM."""

    result: dict[str, Any] = {
        "user_id": user_id,
        "total_orders": 0,
        "total_amount": 0,
        "orders_by_status": {
            orders_service.STATUS_NEW: 0,
            orders_service.STATUS_IN_PROGRESS: 0,
            orders_service.STATUS_PAID: 0,
            orders_service.STATUS_SENT: 0,
            orders_service.STATUS_ARCHIVED: 0,
        },
        "last_order_id": None,
        "last_order_created_at": None,
    }

    init_db()
    with get_session() as session:
        count_row = session.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.total_amount), 0),
            ).where(Order.user_id == user_id)
        ).first()
        if count_row:
            result["total_orders"] = int(count_row[0] or 0)
            result["total_amount"] = int(count_row[1] or 0)

        status_rows = session.execute(
            select(Order.status, func.count(Order.id)).where(Order.user_id == user_id).group_by(Order.status)
        ).all()
        for status, cnt in status_rows:
            if status in result["orders_by_status"]:
                result["orders_by_status"][status] = int(cnt or 0)

        last_order = session.scalar(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc(), Order.id.desc()).limit(1)
        )
        if last_order:
            result["last_order_id"] = int(last_order.id)
            if isinstance(last_order.created_at, datetime):
                result["last_order_created_at"] = last_order.created_at.isoformat()

    return result


def get_user_courses_summary(user_id: int) -> dict[str, Any]:
    """Сводка по курсам, к которым у пользователя есть доступ."""

    courses = orders_service.get_user_courses_with_access(user_id)
    return {
        "count": len(courses),
        "courses": courses,
    }
