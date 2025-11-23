from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services import cart as cart_service
from services import products as products_service


app = FastAPI(title="MiniDeN Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ALLOWED_TYPES = {"basket", "course"}


def _validate_type(product_type: str) -> str:
    if product_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="type must be 'basket' or 'course'")
    return product_type


class CartItemPayload(BaseModel):
    user_id: int
    product_id: int
    qty: int | None = 1
    type: str = "basket"
    type: str = "basket"


class CartClearPayload(BaseModel):
    user_id: int


@app.get("/api/categories")
def api_categories(type: str):
    _validate_type(type)
    return []


@app.get("/api/products")
def api_products(type: str, category_slug: str | None = None):
    product_type = _validate_type(type)
    return products_service.list_products(product_type)


@app.get("/api/cart")
def api_cart(user_id: int):
    items, _ = cart_service.get_cart_items(user_id)

    result_items: list[dict] = []
    total = 0

    for item in items:
        price = 0
        qty = int(item.get("qty") or 0)
        product_type = item.get("type") or "basket"
        try:
            product_id_int = int(item.get("product_id"))
        except (TypeError, ValueError):
            product_id_int = None

        product_info = None
        if product_id_int is not None:
            product_info = (
                products_service.get_basket_by_id(product_id_int)
                if product_type == "basket"
                else products_service.get_course_by_id(product_id_int)
            )

        result_items.append(
            {
                "product_id": product_id_int,
                "name": product_info.get("name") if product_info else None,
                "price": int(product_info.get("price") or price) if product_info else price,
                "qty": qty,
                "type": product_type,
            }
        )
        total += (int(product_info.get("price") or price) if product_info else price) * qty

    return {"items": result_items, "total": total}


@app.post("/api/cart/add")
def api_cart_add(payload: CartItemPayload):
    qty = payload.qty or 1
    if qty <= 0:
        raise HTTPException(status_code=400, detail="qty must be positive")

    product = (
        products_service.get_basket_by_id(int(payload.product_id))
        if payload.type == "basket"
        else products_service.get_course_by_id(int(payload.product_id))
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    cart_service.add_to_cart(
        user_id=payload.user_id,
        product_id=str(payload.product_id),
        name=product["name"],
        price=int(product.get("price") or 0),
        qty=qty,
        product_type=payload.type,
    )

    return {"ok": True}


@app.post("/api/cart/update")
def api_cart_update(payload: CartItemPayload):
    qty = payload.qty or 0

    product_id_str = str(payload.product_id)

    if qty <= 0:
        cart_service.remove_from_cart(payload.user_id, product_id_str, payload.type)
        return {"ok": True}

    product = (
        products_service.get_basket_by_id(int(payload.product_id))
        if payload.type == "basket"
        else products_service.get_course_by_id(int(payload.product_id))
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    current_items, _ = cart_service.get_cart_items(payload.user_id)
    existing = next(
        (
            i
            for i in current_items
            if i.get("product_id") == product_id_str and i.get("type") == payload.type
        ),
        None,
    )

    if existing:
        delta = qty - int(existing.get("qty") or 0)
        if delta != 0:
            cart_service.change_qty(payload.user_id, product_id_str, delta, payload.type)
    else:
        cart_service.add_to_cart(
            user_id=payload.user_id,
            product_id=product_id_str,
            name=product["name"],
            price=int(product.get("price") or 0),
            qty=qty,
            product_type=payload.type,
        )

    return {"ok": True}


@app.post("/api/cart/clear")
def api_cart_clear(payload: CartClearPayload):
    cart_service.clear_cart(payload.user_id)
    return {"ok": True}


@app.get("/")
def healthcheck():
    return {"ok": True}

