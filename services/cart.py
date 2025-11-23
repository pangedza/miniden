from __future__ import annotations

from typing import Any, Tuple

from sqlalchemy import delete, select

from database import get_session, init_db
from models import CartItem, User


def _ensure_user(user_id: int, username: str | None = None, first_name: str | None = None) -> None:
    init_db()
    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            session.add(User(id=user_id, username=username, first_name=first_name))
        else:
            if username is not None:
                user.username = username
            if first_name is not None:
                user.first_name = first_name


def get_cart_items(user_id: int) -> Tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    init_db()
    with get_session() as session:
        items = session.scalars(select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)).all()
        result: list[dict[str, Any]] = []
        for item in items:
            result.append(
                {
                    "product_id": str(item.product_id),
                    "name": None,
                    "price": 0,
                    "qty": item.qty,
                    "type": item.type,
                }
            )
        return result, []


def add_to_cart(user_id: int, product_id: str, name: str, price: int, qty: int = 1, product_type: str = "basket") -> None:
    _ensure_user(user_id)
    with get_session() as session:
        existing = session.scalar(
            select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == int(product_id), CartItem.type == product_type)
        )
        if existing:
            existing.qty = existing.qty + qty
        else:
            session.add(
                CartItem(user_id=user_id, product_id=int(product_id), qty=qty, type=product_type)
            )


def change_qty(user_id: int, product_id: str, delta: int, product_type: str = "basket") -> None:
    with get_session() as session:
        item = session.scalar(
            select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == int(product_id), CartItem.type == product_type)
        )
        if not item:
            return
        new_qty = item.qty + delta
        if new_qty <= 0:
            session.delete(item)
        else:
            item.qty = new_qty


def remove_from_cart(user_id: int, product_id: str, product_type: str = "basket") -> None:
    with get_session() as session:
        item = session.scalar(
            select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == int(product_id), CartItem.type == product_type)
        )
        if item:
            session.delete(item)


def clear_cart(user_id: int) -> None:
    with get_session() as session:
        session.execute(delete(CartItem).where(CartItem.user_id == user_id))


def get_cart_total(user_id: int) -> int:
    items, _ = get_cart_items(user_id)
    total = 0
    for item in items:
        total += int(item["price"]) * int(item["qty"])
    return total
