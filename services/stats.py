from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func, select

from database import get_session
from initdb import init_db
from models import Favorite, Order, OrderItem, User, UserStats
from services import menu_catalog

# NOTE: Этот модуль используется прежде всего для веб-админки
# (WEBAPP_ADMIN_URL). В Telegram-боте подробные отчёты больше не
# отображаются, чтобы оставить боту роль CRM-инструмента.


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_orders_stats_summary(date_from: str | None = None, date_to: str | None = None) -> dict:
    init_db()
    filters = []
    dt_from = _parse_date(date_from)
    dt_to = _parse_date(date_to)
    if dt_from:
        filters.append(Order.created_at >= dt_from)
    if dt_to:
        filters.append(Order.created_at <= dt_to)

    with get_session() as session:
        count_row = session.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.total_amount), 0),
            ).where(*filters)
        ).first()

        status_rows = session.execute(
            select(Order.status, func.count(Order.id)).where(*filters).group_by(Order.status)
        ).all()

    by_status = {status: int(cnt or 0) for status, cnt in status_rows if status}
    total_orders = int(count_row[0] or 0) if count_row else 0
    total_amount = int(count_row[1] or 0) if count_row else 0

    return {
        "total_orders": total_orders,
        "total_amount": total_amount,
        "by_status": by_status,
    }


def get_orders_stats_by_day(limit_days: int = 7) -> List[dict]:
    if limit_days <= 0:
        return []

    today = datetime.now().date()
    date_from = today - timedelta(days=limit_days - 1)

    with get_session() as session:
        rows = session.execute(
            select(
                func.date(Order.created_at),
                func.count(Order.id),
                func.coalesce(func.sum(Order.total_amount), 0),
            )
            .where(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at).desc())
            .limit(limit_days)
        ).all()

    return [
        {
            "date": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
            "orders_count": int(row[1] or 0),
            "total_amount": int(row[2] or 0),
        }
        for row in rows
    ]


def _serialize_top_item(row, product_type: str | None = None) -> dict:
    product_id = int(row.product_id)
    resolved_type = menu_catalog.map_legacy_item_type(product_type or getattr(row, "type", None)) or "product"
    product = menu_catalog.get_item_by_id(
        product_id,
        include_inactive=True,
        item_type=resolved_type,
    )
    name = (product or {}).get("title") if isinstance(product, dict) else None
    if not name and isinstance(product, dict):
        name = product.get("name")
    name = name or f"Товар #{product_id}"
    return {
        "product_id": product_id,
        "name": name,
        "total_qty": int(row.total_qty or 0),
        "total_amount": int(row.total_amount or 0),
    }


def get_top_products(limit: int = 5) -> list[dict]:
    if limit <= 0:
        return []

    with get_session() as session:
        rows = session.execute(
            select(
                OrderItem.product_id.label("product_id"),
                OrderItem.type.label("type"),
                func.sum(OrderItem.qty).label("total_qty"),
                func.sum(OrderItem.qty * OrderItem.price).label("total_amount"),
            )
            .where(OrderItem.type.in_(["basket", "product"]))
            .group_by(OrderItem.product_id, OrderItem.type)
            .order_by(func.sum(OrderItem.qty * OrderItem.price).desc())
            .limit(limit)
        ).all()
    return [_serialize_top_item(row) for row in rows]


def get_top_courses(limit: int = 5) -> list[dict]:
    if limit <= 0:
        return []

    with get_session() as session:
        rows = session.execute(
            select(
                OrderItem.product_id.label("product_id"),
                func.sum(OrderItem.qty).label("total_qty"),
                func.sum(OrderItem.qty * OrderItem.price).label("total_amount"),
            )
            .where(OrderItem.type == "course")
            .group_by(OrderItem.product_id)
            .order_by(func.sum(OrderItem.qty * OrderItem.price).desc())
            .limit(limit)
        ).all()
    return [_serialize_top_item(row, "course") for row in rows]


def _get_or_create_user_stats(session, user_id: int) -> UserStats:
    stats = session.scalar(select(UserStats).where(UserStats.user_id == user_id))
    if stats:
        return stats
    stats = UserStats(user_id=user_id, orders_count=0, total_spent=0)
    session.add(stats)
    session.flush()
    return stats


def recalc_user_stats(user_id: int) -> dict:
    with get_session() as session:
        orders_count = session.scalar(
            select(func.count(Order.id)).where(Order.user_id == user_id)
        )
        total_spent = session.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.user_id == user_id
            )
        )
        last_order = session.scalar(
            select(Order.created_at)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(1)
        )

        stats = _get_or_create_user_stats(session, user_id)
        stats.orders_count = int(orders_count or 0)
        stats.total_spent = int(total_spent or 0)
        stats.last_order_at = last_order
        session.flush()
        session.refresh(stats)

        return {
            "orders_count": stats.orders_count,
            "total_spent": stats.total_spent,
            "last_order_at": stats.last_order_at.isoformat() if stats.last_order_at else None,
        }


def update_user_stats(user_id: int, order_total: int, last_order_at: datetime | None = None) -> None:
    with get_session() as session:
        stats = _get_or_create_user_stats(session, user_id)
        stats.orders_count = int(stats.orders_count or 0) + 1
        stats.total_spent = int(stats.total_spent or 0) + int(order_total or 0)
        stats.last_order_at = last_order_at or datetime.utcnow()


def get_user_stats(user_id: int) -> dict:
    with get_session() as session:
        stats = _get_or_create_user_stats(session, user_id)
        return {
            "orders_count": int(stats.orders_count or 0),
            "total_spent": int(stats.total_spent or 0),
            "last_order_at": stats.last_order_at.isoformat() if stats.last_order_at else None,
        }


def get_admin_dashboard_stats(limit_new_users: int = 5) -> dict:
    with get_session() as session:
        total_users = session.scalar(select(func.count(User.id))) or 0
        total_orders = session.scalar(select(func.count(Order.id))) or 0
        total_amount = session.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0))
        ) or 0
        favorites_count = session.scalar(select(func.count(Favorite.id))) or 0

        new_users = session.scalars(
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit_new_users)
        ).all()

    top_products = get_top_products(limit=5)
    top_courses = get_top_courses(limit=5)

    return {
        "totals": {
            "users": int(total_users),
            "orders": int(total_orders),
            "amount": int(total_amount),
            "favorites": int(favorites_count),
        },
        "top_products": top_products,
        "top_courses": top_courses,
        "new_users": [
            {
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in new_users
        ],
    }
