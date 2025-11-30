"""
LEGACY ROUTER — старый API.
Не используется. Оставлен только как архив.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import cart as cart_service
from services import orders as orders_service
from services import users as users_service
from services import products as products_service
from utils.texts import format_order_for_admin

router = APIRouter(prefix="/order", tags=["orders"])


class CheckoutPayload(BaseModel):
    user_id: int
    user_name: str | None = Field(None, description="Имя пользователя из Telegram")
    customer_name: str = Field(..., description="Имя клиента")
    contact: str = Field(..., description="Способ связи")
    comment: str | None = None


class CheckoutResponse(BaseModel):
    order_id: int
    total: int
    items: list[dict[str, Any]]
    removed_items: list[dict[str, Any]]


@router.post("/create", response_model=CheckoutResponse)
def api_checkout(payload: CheckoutPayload):
    items, removed_items = cart_service.get_cart_items(payload.user_id)

    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    normalized_items: list[dict[str, Any]] = []
    total = 0

    for item in items:
        qty = max(int(item.get("qty") or 0), 0)
        if qty <= 0:
            continue

        try:
            product_id_int = int(item.get("product_id"))
        except (TypeError, ValueError):
            removed_items.append({"product_id": item.get("product_id"), "reason": "invalid_id"})
            continue

        product_type = item.get("type") or "basket"
        if product_type == "basket":
            product_info = products_service.get_basket_by_id(product_id_int)
        else:
            product_info = products_service.get_course_by_id(product_id_int)

        if not product_info:
            removed_items.append({"product_id": product_id_int, "reason": "inactive"})
            continue

        price = int(product_info.get("price") or 0)
        subtotal = price * qty
        total += subtotal

        normalized_items.append(
            {
                "product_id": product_id_int,
                "name": product_info.get("name") or item.get("name"),
                "price": price,
                "qty": qty,
                "type": product_type,
            }
        )

    if not normalized_items:
        cart_service.clear_cart(payload.user_id)
        raise HTTPException(status_code=400, detail="No valid items in cart")

    user_name = payload.user_name or "webapp"

    order_text = format_order_for_admin(
        user_id=payload.user_id,
        user_name=user_name,
        items=normalized_items,
        total=total,
        customer_name=payload.customer_name,
        contact=payload.contact,
        comment=payload.comment or "",
    )

    users_service.get_or_create_user_from_telegram(
        {
            "id": payload.user_id,
            "username": payload.user_name,
            "first_name": payload.customer_name,
        }
    )

    order_id = orders_service.add_order(
        user_id=payload.user_id,
        user_name=user_name,
        items=normalized_items,
        total=total,
        customer_name=payload.customer_name,
        contact=payload.contact,
        comment=payload.comment or "",
        order_text=order_text,
    )

    cart_service.clear_cart(payload.user_id)

    return CheckoutResponse(
        order_id=order_id,
        total=total,
        items=normalized_items,
        removed_items=removed_items,
    )
