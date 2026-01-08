from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from database import get_session
from models import Order, OrderItem
from services import menu_catalog
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

        raw_type = item.get("type")
        product_data = (
            menu_catalog.get_item_by_id(
                product_id, include_inactive=True, item_type=raw_type
            )
            if raw_type in menu_catalog.MENU_ITEM_TYPES
            else None
        )
        if not product_data and raw_type == "course":
            product_data = products_service.get_course_by_id(product_id)
        if not product_data and raw_type == "basket":
            product_data = products_service.get_basket_by_id(product_id)
        if not product_data:
            product_data = products_service.get_product_by_id(product_id) or {}

        price_raw = item.get("price")
        try:
            price = int(price_raw) if price_raw is not None else int(product_data.get("price") or 0)
        except (TypeError, ValueError):
            price = int(product_data.get("price") or 0)

        product_type = item.get("type") or product_data.get("type") or "product"
        if product_type not in menu_catalog.MENU_ITEM_TYPES and product_type not in {"basket", "course"}:
            product_type = "product"

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
        **_extract_client_info(order),
    }


def _course_item_available(status: str | None, price: int) -> bool:
    if status == STATUS_PAID:
        return True
    return price <= 0


def _serialize_order_item(item: OrderItem, order_status: str | None = None) -> dict[str, Any]:
    product = None
    if item.type in menu_catalog.MENU_ITEM_TYPES:
        product = menu_catalog.get_item_by_id(
            int(item.product_id),
            include_inactive=True,
            item_type=item.type,
        )
    if not product and item.type == "course":
        product = products_service.get_course_by_id(item.product_id, include_inactive=True)
    if not product and item.type == "basket":
        product = products_service.get_basket_by_id(item.product_id, include_inactive=True)
    if not product:
        product = products_service.get_product_by_id(item.product_id, include_inactive=True)
    price = int(item.price or 0)
    status = order_status or STATUS_NEW
    name = (product or {}).get("name") if isinstance(product, dict) else None
    if not name and isinstance(product, dict):
        name = product.get("title")
    return {
        "product_id": item.product_id,
        "qty": item.qty,
        "price": price,
        "type": item.type,
        "product": product,
        "name": name,
        "detail_url": (product or {}).get("detail_url") if isinstance(product, dict) else None,
        "masterclass_url": (product or {}).get("masterclass_url") if isinstance(product, dict) else None,
        "can_access": item.type == "course" and _course_item_available(status, price),
    }


def _extract_client_info(order: Order) -> dict[str, Any]:
    user = order.user
    telegram_id = None
    telegram_username = None
    client_phone = None

    if user:
        telegram_id = int(user.telegram_id) if user.telegram_id is not None else None
        telegram_username = user.username
        client_phone = user.phone

    if telegram_id is None and order.user_id is not None:
        telegram_id = int(order.user_id)

    contact_phone = order.contact or client_phone
    client_name = order.customer_name or (user.first_name if user else None)

    return {
        "client_name": client_name,
        "client_phone": contact_phone,
        "telegram_id": telegram_id,
        "telegram_username": telegram_username,
    }


def get_orders_by_user(
    user_id: int, *, limit: int = 20, include_archived: bool = False
) -> list[dict[str, Any]]:
    with get_session() as session:
        query = select(Order).where(Order.user_id == user_id)
        if not include_archived:
            query = query.where(Order.status != STATUS_ARCHIVED)

        rows = session.scalars(query.order_by(Order.id.desc()).limit(limit)).all()
        serialized: list[dict[str, Any]] = []
        for row in rows:
            items = session.scalars(select(OrderItem).where(OrderItem.order_id == row.id)).all()
            serialized.append(
                {
                    **_serialize_order_summary(row),
                    "customer_name": row.customer_name,
                    "contact": row.contact,
                    "comment": row.comment,
                    "promocode_code": row.promocode_code,
                    "discount_amount": int(row.discount_amount or 0)
                    if row.discount_amount is not None
                    else None,
                    "order_text": row.order_text,
                    "items": [_serialize_order_item(item, row.status) for item in items],
                }
            )
        return serialized


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
            serialized_items.append(_serialize_order_item(item, order.status))
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
            **_extract_client_info(order),
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


def archive_order_for_user(order_id: int, user_id: int) -> bool:
    with get_session() as session:
        order = session.get(Order, order_id)
        if not order:
            return False
        if int(order.user_id or 0) != int(user_id):
            return False
        if order.status == STATUS_ARCHIVED:
            return True

        order.status = STATUS_ARCHIVED
        session.flush()
        stats_service.recalc_user_stats(int(order.user_id))
        return True


def update_order_status(order_id: int, status: str) -> bool:
    changed = set_order_status(order_id, status)
    if changed and status == STATUS_PAID:
        grant_courses_from_order(order_id)
    return changed


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
        rows = session.execute(
            select(OrderItem, Order)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.user_id == user_id, OrderItem.type == "course")
        ).all()

    courses: dict[int, dict[str, Any]] = {}
    for item, order in rows:
        product = products_service.get_course_by_id(item.product_id, include_inactive=True)
        if not product:
            continue
        price = int(item.price or 0)
        if not _course_item_available(order.status, price):
            continue

        course_id = int(product.get("id"))
        entry = {
            "id": course_id,
            "name": product.get("name"),
            "masterclass_url": product.get("masterclass_url") or product.get("detail_url"),
            "is_paid": price > 0,
            "from_order_id": order.id,
            "price": price,
        }

        existing = courses.get(course_id)
        if existing:
            if existing.get("is_paid"):
                continue
            if entry.get("is_paid"):
                courses[course_id] = entry
        else:
            courses[course_id] = entry

    return list(courses.values())


def grant_course_access(
    user_id: int,
    course_id: int,
    *,
    admin_id: int | None = None,
    granted_by: int | None = None,
    source_order_id: int | None = None,
    comment: str | None = None,
) -> bool:
    existing = [c for c in get_user_courses_with_access(user_id) if c.get("id") == course_id]
    if existing:
        return True

    with get_session() as session:
        order = Order(
            user_id=user_id,
            total_amount=0,
            created_at=datetime.utcnow(),
            status=STATUS_PAID,
            comment=comment or "Access granted manually",
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
    order = get_order_by_id(order_id)
    if not order:
        return 0

    granted = 0
    for item in order.get("items", []):
        if item.get("type") != "course":
            continue
        price = int(item.get("price") or 0)
        if _course_item_available(order.get("status"), price):
            granted += 1
    return granted
