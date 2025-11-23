from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from database import get_session
from models import Order, OrderItem
from services import products as products_service
from services import stats as stats_service
from services import users as users_service

STATUS_NEW = "new"
STATUS_IN_PROGRESS = "in_progress"
STATUS_PAID = "paid"
STATUS_SENT = "sent"
STATUS_ARCHIVED = "archived"

STATUS_TITLES = {
    STATUS_NEW: "Новый",
    STATUS_IN_PROGRESS: "В работе",
    STATUS_PAID: "Оплачен",
    STATUS_SENT: "Отправлен",
    STATUS_ARCHIVED: "Архив",
}


def _ensure_user(telegram_id: int, user_name: str | None = None) -> None:
    user = users_service.get_user_by_telegram_id(telegram_id)
    if user:
        return

    payload: dict[str, Any] = {"id": telegram_id}
    if user_name:
        payload["first_name"] = user_name
    users_service.get_or_create_user_from_telegram(payload)


def _normalize_order_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    normalized: list[dict[str, Any]] = []
    total_amount = 0

    for item in items:
        try:
            product_id = int(item.get("product_id") or 0)
        except (TypeError, ValueError):
            continue

        try:
            qty = int(item.get("qty") or 1)
        except (TypeError, ValueError):
            qty = 1

        if qty <= 0:
            continue

        product_data = products_service.get_product_by_id(product_id) or {}

        price_raw = item.get("price")
        try:
            price = int(price_raw) if price_raw is not None else int(product_data.get("price") or 0)
        except (TypeError, ValueError):
            price = int(product_data.get("price") or 0)

        product_type = (
            item.get("type")
            or product_data.get("type")
            or ("basket" if product_data else "basket")
        )

        normalized.append(
            {
                "product_id": product_id,
                "qty": qty,
                "price": price,
                "type": product_type,
                "product": product_data or None,
            }
        )

        total_amount += price * qty

    return normalized, total_amount


def add_order(
    user_id: int,
    user_name: str,
    items: list[dict[str, Any]],
    total: int,
    customer_name: str,
    contact: str,
    comment: str,
    order_text: str,
    promocode_code: str | None = None,
    discount_amount: int | None = None,
    status: str | None = STATUS_NEW,
) -> int:
    _ensure_user(user_id, user_name=user_name)

    normalized_items, computed_total = _normalize_order_items(items)
    order_total = computed_total if normalized_items else int(total)

    with get_session() as session:
        order = Order(
            user_id=user_id,
            total_amount=order_total,
            created_at=datetime.utcnow(),
            customer_name=customer_name,
            contact=contact,
            comment=comment,
            promocode_code=promocode_code,
            discount_amount=discount_amount,
            status=status or STATUS_NEW,
            order_text=order_text,
        )
        session.add(order)
        session.flush()

        for item in normalized_items:
            session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=int(item["product_id"]),
                    qty=int(item["qty"]),
                    price=int(item["price"]),
                    type=item.get("type") or "basket",
                )
            )

        stats_service.recalc_user_stats(user_id)

        return int(order.id)


def _serialize_order_summary(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "total": int(order.total_amount or 0),
        "status": order.status or STATUS_NEW,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def get_orders_by_user(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.scalars(
            select(Order).where(Order.user_id == user_id).order_by(Order.id.desc()).limit(limit)
        ).all()
        return [_serialize_order_summary(row) for row in rows]


def list_orders(limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    with get_session() as session:
        query = select(Order).order_by(Order.id.desc()).limit(limit)
        if status:
            query = query.where(Order.status == status)
        rows = session.scalars(query).all()
        return [_serialize_order_summary(row) for row in rows]


def get_orders_for_admin(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return list_orders(limit=limit, status=None if status == "all" else status)


def get_order_by_id(order_id: int) -> Optional[dict[str, Any]]:
    with get_session() as session:
        order = session.get(Order, order_id)
        if not order:
            return None
        items = session.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
        serialized_items: list[dict[str, Any]] = []
        for item in items:
            product = products_service.get_product_by_id(item.product_id)
            serialized_items.append(
                {
                    "product_id": item.product_id,
                    "qty": item.qty,
                    "price": int(item.price or 0),
                    "product": product,
                    "type": item.type,
                }
            )
        return {
            "id": order.id,
            "user_id": order.user_id,
            "total": int(order.total_amount or 0),
            "status": order.status or STATUS_NEW,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "customer_name": order.customer_name,
            "contact": order.contact,
            "comment": order.comment,
            "promocode_code": order.promocode_code,
            "discount_amount": int(order.discount_amount or 0)
            if order.discount_amount is not None
            else None,
            "order_text": order.order_text,
            "items": serialized_items,
        }


def set_order_status(order_id: int, status: str) -> bool:
    with get_session() as session:
        order = session.get(Order, order_id)
        if not order:
            return False
        order.status = status
        session.flush()
        stats_service.recalc_user_stats(int(order.user_id))
        return True


def get_courses_from_order(order_id: int) -> list[dict[str, Any]]:
    with get_session() as session:
        items = session.scalars(
            select(OrderItem).where(OrderItem.order_id == order_id, OrderItem.type == "course")
        ).all()
    result: list[dict[str, Any]] = []
    for item in items:
        product = products_service.get_course_by_id(item.product_id)
        if product:
            result.append(product)
    return result


def get_user_courses_with_access(user_id: int) -> list[dict[str, Any]]:
    with get_session() as session:
        items = session.execute(
            select(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.user_id == user_id, OrderItem.type == "course")
        ).scalars().all()

    seen: set[int] = set()
    courses: list[dict[str, Any]] = []
    for item in items:
        if item.product_id in seen:
            continue
        product = products_service.get_course_by_id(item.product_id)
        if not product:
            continue
        seen.add(item.product_id)
        courses.append(product)
    return courses


def grant_course_access(user_id: int, course_id: int, *, admin_id: int | None = None) -> bool:
    existing = [c for c in get_user_courses_with_access(user_id) if c.get("id") == course_id]
    if existing:
        return True

    with get_session() as session:
        order = Order(
            user_id=user_id,
            total_amount=0,
            created_at=datetime.utcnow(),
            status=STATUS_PAID,
            comment="Access granted manually",
        )
        session.add(order)
        session.flush()

        session.add(
            OrderItem(
                order_id=order.id,
                product_id=course_id,
                qty=1,
                price=0,
                type="course",
            )
        )

        stats_service.recalc_user_stats(user_id)
    return True


def revoke_course_access(user_id: int, course_id: int) -> bool:
    changed = False
    with get_session() as session:
        items = session.scalars(
            select(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.user_id == user_id, OrderItem.type == "course", OrderItem.product_id == course_id)
        ).all()
        for item in items:
            session.delete(item)
            changed = True
        if changed:
            stats_service.recalc_user_stats(user_id)
    return changed


def get_course_users(course_id: int) -> list[int]:
    with get_session() as session:
        rows = session.execute(
            select(Order.user_id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(OrderItem.product_id == course_id, OrderItem.type == "course")
        ).all()
    return [int(row[0]) for row in rows if row[0] is not None]


def grant_courses_from_order(order_id: int, admin_id: int | None = None) -> int:
    courses = get_courses_from_order(order_id)
    if not courses:
        return 0
    order = get_order_by_id(order_id)
    if not order:
        return 0
    user_id = int(order.get("user_id") or 0)
    granted = 0
    for course in courses:
        if grant_course_access(user_id, int(course.get("id"))):
            granted += 1
    return granted
