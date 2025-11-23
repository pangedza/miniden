from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func, select

from database import get_session, init_db
from models import Order, OrderItem
from services import products as products_service


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
    if product_type:
        loader = (
            products_service.get_basket_by_id
            if product_type == "basket"
            else products_service.get_course_by_id
        )
        product = loader(product_id)
    else:
        product = products_service.get_product_by_id(product_id)
    name = (product or {}).get("name") or f"Товар #{product_id}"
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
                func.sum(OrderItem.qty).label("total_qty"),
                func.sum(OrderItem.qty * OrderItem.price).label("total_amount"),
            )
            .where(OrderItem.type == "basket")
            .group_by(OrderItem.product_id)
            .order_by(func.sum(OrderItem.qty * OrderItem.price).desc())
            .limit(limit)
        ).all()
    return [_serialize_top_item(row, "basket") for row in rows]


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
