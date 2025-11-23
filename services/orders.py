from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from database import get_session
from models import Order, OrderItem
from services import products as products_service
from services import users as users_service

STATUS_NEW = "new"


def _ensure_user(telegram_id: int, user_data: dict[str, Any] | None = None) -> None:
    user = users_service.get_user_by_telegram_id(telegram_id)
    if user:
        return

    payload: dict[str, Any] = {"id": telegram_id}
    if user_data:
        payload.update(user_data)
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
    user_data: dict[str, Any] | None = None,
) -> int:
    _ensure_user(user_id, user_data=user_data or {"first_name": user_name})

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
