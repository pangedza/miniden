from __future__ import annotations

from typing import Any, Tuple

from sqlalchemy import delete, select

from database import get_session, init_db
from models import CartItem
from services import menu_catalog
from services import users as users_service


def _normalize_product(item: CartItem) -> tuple[dict[str, Any] | None, bool]:
    product_type = item.type
    resolved_type = menu_catalog.map_legacy_item_type(product_type) or "product"
    product = menu_catalog.get_item_by_id(
        int(item.product_id),
        include_inactive=True,
        item_type=resolved_type,
    )

    if not product:
        return None, True

    name = product.get("title") if isinstance(product, dict) else None
    if not name and isinstance(product, dict):
        name = product.get("name")

    return (
        {
            "product_id": int(item.product_id),
            "name": name,
            "price": int(product.get("price", 0) or 0),
            "qty": int(item.qty),
            "type": resolved_type,
            "category_id": product.get("category_id"),
            "category_name": product.get("category_title") or product.get("category_name"),
        },
        False,
    )


def _build_cart_filters(user_id: int | None, session_id: str | None) -> list[Any]:
    if user_id is not None:
        return [CartItem.user_id == int(user_id)]
    if not session_id:
        raise ValueError("cart_identity_missing")
    return [CartItem.session_id == session_id]


def get_cart_items(user_id: int | None, session_id: str | None = None) -> Tuple[list[dict[str, Any]], list[int]]:
    init_db()
    with get_session() as session:
        filters = _build_cart_filters(user_id, session_id)
        items = session.scalars(select(CartItem).where(*filters).order_by(CartItem.id)).all()

    result: list[dict[str, Any]] = []
    removed: list[int] = []

    for item in items:
        normalized, was_removed = _normalize_product(item)
        if was_removed:
            remove_from_cart(user_id, int(item.product_id), item.type, session_id=session_id)
            removed.append(int(item.product_id))
            continue
        if normalized:
            result.append(normalized)

    return result, removed


def add_to_cart(
    user_id: int | None,
    product_id: int,
    product_type: str,
    qty: int = 1,
    session_id: str | None = None,
) -> None:
    qty = max(int(qty), 1)
    if user_id is not None:
        users_service.get_or_create_user_from_telegram({"id": user_id})
    normalized_type = menu_catalog.map_legacy_item_type(product_type) or "product"
    if normalized_type not in menu_catalog.MENU_ITEM_TYPES:
        normalized_type = "product"
    with get_session() as session:
        filters = _build_cart_filters(user_id, session_id)
        existing = session.scalar(
            select(CartItem).where(
                *filters,
                CartItem.product_id == int(product_id),
                CartItem.type == normalized_type,
            )
        )
        stock_limit = None
        product = menu_catalog.get_item_by_id(
            int(product_id), include_inactive=False, item_type=normalized_type
        )
        stock_limit = product.get("stock_qty") if product else None
        if product and stock_limit == 0:
            return

        if existing:
            next_qty = existing.qty + qty
            if stock_limit is not None:
                next_qty = min(next_qty, int(stock_limit))
            existing.qty = next_qty
        else:
            next_qty = qty
            if stock_limit is not None:
                next_qty = min(next_qty, int(stock_limit))
            if next_qty <= 0:
                return
            session.add(
                CartItem(
                    user_id=user_id,
                    session_id=session_id if user_id is None else None,
                    product_id=int(product_id),
                    qty=next_qty,
                    type=normalized_type,
                )
            )


def change_qty(
    user_id: int | None,
    product_id: int,
    delta: int,
    product_type: str = "basket",
    session_id: str | None = None,
) -> None:
    init_db()
    normalized_type = menu_catalog.map_legacy_item_type(product_type) or product_type
    with get_session() as session:
        filters = _build_cart_filters(user_id, session_id)
        item = session.scalar(
            select(CartItem).where(
                *filters,
                CartItem.product_id == int(product_id),
                CartItem.type == normalized_type,
            )
        )
        if not item and normalized_type != product_type:
            item = session.scalar(
                select(CartItem).where(
                    *filters,
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


def remove_from_cart(
    user_id: int | None,
    product_id: int,
    product_type: str = "basket",
    session_id: str | None = None,
) -> None:
    init_db()
    normalized_type = menu_catalog.map_legacy_item_type(product_type) or product_type
    with get_session() as session:
        filters = _build_cart_filters(user_id, session_id)
        item = session.scalar(
            select(CartItem).where(
                *filters,
                CartItem.product_id == int(product_id),
                CartItem.type == normalized_type,
            )
        )
        if not item and normalized_type != product_type:
            item = session.scalar(
                select(CartItem).where(
                    *filters,
                    CartItem.product_id == int(product_id),
                    CartItem.type == product_type,
                )
            )
        if item:
            session.delete(item)


def clear_cart(user_id: int | None, session_id: str | None = None) -> None:
    init_db()
    with get_session() as session:
        filters = _build_cart_filters(user_id, session_id)
        session.execute(delete(CartItem).where(*filters))


def get_cart_total(user_id: int | None, session_id: str | None = None) -> int:
    items, _ = get_cart_items(user_id, session_id=session_id)
    total = 0
    for item in items:
        total += int(item.get("price", 0)) * int(item.get("qty", 0))
    return total
