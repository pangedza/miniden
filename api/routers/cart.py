"""
LEGACY ROUTER — старый API.
Не используется. Оставлен только как архив.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import cart as cart_service
from services import menu_catalog

router = APIRouter(prefix="/cart", tags=["cart"])


class CartItemPayload(BaseModel):
    user_id: int
    product_id: int
    qty: int | None = 1
    type: str = "basket"


class CartClearPayload(BaseModel):
    user_id: int


class CartRemovePayload(BaseModel):
    user_id: int
    product_id: int
    type: str = "basket"


class CartUpdatePayload(BaseModel):
    user_id: int
    product_id: int
    qty: int
    type: str = "basket"


def _build_cart_response(user_id: int) -> dict[str, Any]:
    items, removed_items = cart_service.get_cart_items(user_id)

    result_items: list[dict[str, Any]] = []
    total = 0

    for item in items:
        price = 0
        qty = int(item.get("qty") or 0)
        product_type = item.get("type") or "product"
        try:
            product_id_int = int(item.get("product_id"))
        except (TypeError, ValueError):
            product_id_int = None

        product_info = None
        if product_id_int is not None:
            resolved_type = menu_catalog.map_legacy_item_type(product_type) or "product"
            product_info = menu_catalog.get_item_by_id(
                product_id_int,
                include_inactive=True,
                item_type=resolved_type,
            )

        if product_info is not None:
            price = int(product_info.get("price") or price)

        result_items.append(
            {
                "product_id": product_id_int,
                "name": (product_info or {}).get("title") if product_info else None,
                "price": price,
                "qty": qty,
                "type": menu_catalog.map_legacy_item_type(product_type) or product_type,
            }
        )
        total += price * qty

    return {"items": result_items, "total": total, "removed_items": removed_items}


@router.get("")
@router.get("/{user_id}")
def api_cart(user_id: int):
    return _build_cart_response(user_id)


@router.post("/add")
def api_cart_add(payload: CartItemPayload):
    qty = payload.qty or 1
    if qty <= 0:
        raise HTTPException(status_code=400, detail="qty must be positive")

    resolved_type = menu_catalog.map_legacy_item_type(payload.type) or "product"
    product = menu_catalog.get_item_by_id(
        int(payload.product_id), include_inactive=False, item_type=resolved_type
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    cart_service.add_to_cart(
        user_id=payload.user_id,
        product_id=int(payload.product_id),
        qty=qty,
        product_type=resolved_type,
    )

    return {"ok": True}


@router.post("/update")
def api_cart_update(payload: CartUpdatePayload):
    qty = payload.qty or 0

    if qty <= 0:
        cart_service.remove_from_cart(payload.user_id, int(payload.product_id), payload.type)
        return {"ok": True}

    resolved_type = menu_catalog.map_legacy_item_type(payload.type) or "product"
    product = menu_catalog.get_item_by_id(
        int(payload.product_id), include_inactive=False, item_type=resolved_type
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    current_items, _ = cart_service.get_cart_items(payload.user_id)
    existing = next(
        (
            i
            for i in current_items
            if int(i.get("product_id")) == int(payload.product_id)
            and i.get("type") == resolved_type
        ),
        None,
    )

    if existing:
        delta = qty - int(existing.get("qty") or 0)
        if delta != 0:
            cart_service.change_qty(payload.user_id, int(payload.product_id), delta, payload.type)
    else:
        cart_service.add_to_cart(
            user_id=payload.user_id,
            product_id=int(payload.product_id),
            qty=qty,
            product_type=resolved_type,
        )

    return {"ok": True}


@router.post("/remove")
def api_cart_remove(payload: CartRemovePayload):
    cart_service.remove_from_cart(payload.user_id, int(payload.product_id), payload.type)
    return {"ok": True}


@router.post("/clear")
def api_cart_clear(payload: CartClearPayload):
    cart_service.clear_cart(payload.user_id)
    return {"ok": True}
