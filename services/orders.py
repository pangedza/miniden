from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from database import get_session, init_db
from models import Order, OrderItem, User
from services import products as products_service

STATUS_NEW = "new"


def _ensure_user(user_id: int, username: str | None = None, first_name: str | None = None) -> User:
    init_db()
    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            user = User(id=user_id, username=username, first_name=first_name)
            session.add(user)
            session.flush()
        return user


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
) -> int:
    _ensure_user(user_id, user_name)
    init_db()

    with get_session() as session:
        order = Order(user_id=user_id, total_amount=total, created_at=datetime.utcnow())
        session.add(order)
        session.flush()

        for item in items:
            price = item.get("price", 0)
            qty = item.get("qty", 1)
            product_type = item.get("type") or "basket"
            session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=int(item.get("product_id") or 0),
                    qty=int(qty),
                    price=price,
                    type=product_type,
                )
            )

        return int(order.id)


def get_orders_by_user(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with get_session() as session:
        rows = session.scalars(
            select(Order).where(Order.user_id == user_id).order_by(Order.id.desc()).limit(limit)
        ).all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "total": int(row.total_amount or 0),
                "status": STATUS_NEW,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_order_by_id(order_id: int) -> Optional[dict[str, Any]]:
    init_db()
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
            "status": STATUS_NEW,
            "created_at": order.created_at.isoformat(),
            "items": serialized_items,
        }
