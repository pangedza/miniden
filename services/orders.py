from __future__ import annotations

from datetime import datetime
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from database import get_session, init_db
from models import Order, OrderItem
from services import users as users_service
from services import products as products_service

STATUS_NEW = "new"


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
    users_service.get_or_create_user_from_telegram({"id": user_id, "first_name": user_name})
    init_db()

    with get_session() as session:
        order = Order(
            user_id=user_id,
            total_amount=total,
            created_at=datetime.utcnow(),
            customer_name=customer_name,
            contact=contact,
            comment=comment,
            promocode_code=promocode_code,
            discount_amount=discount_amount,
            status=status,
            order_text=order_text,
        )
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
                "status": row.status or STATUS_NEW,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def list_orders(limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with get_session() as session:
        query = select(Order).order_by(Order.id.desc()).limit(limit)
        if status:
            query = query.where(Order.status == status)
        rows = session.scalars(query).all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "total": int(row.total_amount or 0),
                "status": row.status or STATUS_NEW,
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
            "status": order.status or STATUS_NEW,
            "created_at": order.created_at.isoformat(),
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
