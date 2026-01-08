from __future__ import annotations

from typing import Any, Tuple

from sqlalchemy import delete, select

from database import get_session, init_db
from models import CartItem
from services import menu_catalog
from services import products as products_service
from services import users as users_service


def _normalize_product(item: CartItem) -> tuple[dict[str, Any] | None, bool]:
    product_type = item.type
    product = None

    if product_type in menu_catalog.MENU_ITEM_TYPES:
        product = menu_catalog.get_item_by_id(
            int(item.product_id),
            include_inactive=True,
            item_type=product_type,
        )
        if not product and product_type == "course":
            product = products_service.get_course_by_id(item.product_id)
    elif product_type == "basket":
        product = products_service.get_basket_by_id(item.product_id)
    else:
        product = products_service.get_course_by_id(item.product_id)

    if not product:
        return None, True

    name = product.get("name") if isinstance(product, dict) else None
    if not name and isinstance(product, dict):
        name = product.get("title")

    return (
        {
            "product_id": int(item.product_id),
            "name": name,
            "price": int(product.get("price", 0) or 0),
            "qty": int(item.qty),
            "type": product_type,
            "category_id": product.get("category_id"),
            "category_name": product.get("category_title") or product.get("category_name"),
        },
        False,
    )


def get_cart_items(user_id: int) -> Tuple[list[dict[str, Any]], list[int]]:
    init_db()
    with get_session() as session:
        items = session.scalars(select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)).all()

    result: list[dict[str, Any]] = []
    removed: list[int] = []

    for item in items:
        normalized, was_removed = _normalize_product(item)
        if was_removed:
            remove_from_cart(user_id, int(item.product_id), item.type)
            removed.append(int(item.product_id))
            continue
        if normalized:
            result.append(normalized)

    return result, removed


def add_to_cart(user_id: int, product_id: int, product_type: str, qty: int = 1) -> None:
    qty = max(int(qty), 1)
    users_service.get_or_create_user_from_telegram({"id": user_id})
    with get_session() as session:
        existing = session.scalar(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == int(product_id),
                CartItem.type == product_type,
            )
        )
        if existing:
            existing.qty = existing.qty + qty
        else:
            session.add(CartItem(user_id=user_id, product_id=int(product_id), qty=qty, type=product_type))


def change_qty(user_id: int, product_id: int, delta: int, product_type: str = "basket") -> None:
    init_db()
    with get_session() as session:
        item = session.scalar(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == int(product_id),
                CartItem.type == product_type,
            )
        )
        if not item:
            return
        new_qty = item.qty + delta
        if new_qty <= 0:
            session.delete(item)
        else:
            item.qty = new_qty


def remove_from_cart(user_id: int, product_id: int, product_type: str = "basket") -> None:
    init_db()
    with get_session() as session:
        item = session.scalar(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == int(product_id),
                CartItem.type == product_type,
            )
        )
        if item:
            session.delete(item)


def clear_cart(user_id: int) -> None:
    init_db()
    with get_session() as session:
        session.execute(delete(CartItem).where(CartItem.user_id == user_id))


def get_cart_total(user_id: int) -> int:
    items, _ = get_cart_items(user_id)
    total = 0
    for item in items:
        total += int(item.get("price", 0)) * int(item.get("qty", 0))
    return total
