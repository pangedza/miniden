from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import ADMIN_IDS_SET
from services import cart as cart_service
from services import orders as orders_service
from services import products as products_service
from services import promocodes as promocodes_service


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


class CartClearPayload(BaseModel):
    user_id: int


def _ensure_admin(user_id: int | None) -> int:
    if user_id is None or int(user_id) not in ADMIN_IDS_SET:
        raise HTTPException(status_code=403, detail="Forbidden")
    return int(user_id)


class AdminProductsCreatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None


class AdminProductsUpdatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    is_active: bool | None = None


class AdminTogglePayload(BaseModel):
    user_id: int


class AdminPromocodeCreatePayload(BaseModel):
    user_id: int
    code: str
    discount_type: str
    discount_value: int
    min_order_total: int | None = 0
    max_uses: int | None = 0
    valid_from: str | None = None
    valid_to: str | None = None
    description: str | None = None
    is_active: bool | None = None


class AdminPromocodeUpdatePayload(BaseModel):
    user_id: int
    discount_type: str | None = None
    discount_value: int | None = None
    min_order_total: int | None = None
    max_uses: int | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    description: str | None = None
    is_active: bool | None = None


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


# ----------------------------
# Admin endpoints
# ----------------------------


@app.get("/api/admin/products")
def admin_products(user_id: int, type: str | None = None, status: str | None = None):
    _ensure_admin(user_id)
    if type:
        _validate_type(type)
    items = products_service.list_products_admin(type, status)
    return {"items": items}


@app.post("/api/admin/products")
def admin_create_product(payload: AdminProductsCreatePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    new_id = products_service.create_product(
        product_type,
        payload.name,
        payload.price,
        payload.description or "",
        payload.detail_url,
        payload.category_id,
    )
    return {"id": new_id}


@app.put("/api/admin/products/{product_id}")
def admin_update_product(product_id: int, payload: AdminProductsUpdatePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    updated = products_service.update_product_full(
        product_id,
        product_type,
        payload.name,
        payload.price,
        payload.description or "",
        payload.detail_url,
        payload.category_id,
        payload.is_active,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.patch("/api/admin/products/{product_id}/toggle_active")
def admin_toggle_product(product_id: int, payload: AdminTogglePayload):
    _ensure_admin(payload.user_id)
    changed = products_service.toggle_product_active(product_id)
    if not changed:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.get("/api/admin/orders")
def admin_orders(user_id: int, status: str | None = None):
    _ensure_admin(user_id)
    orders = orders_service.list_orders(status=status)
    return {"items": orders}


@app.get("/api/admin/orders/{order_id}")
def admin_order_detail(order_id: int, user_id: int):
    _ensure_admin(user_id)
    order = orders_service.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/api/admin/promocodes")
def admin_promocodes(user_id: int):
    _ensure_admin(user_id)
    promos = promocodes_service.list_promocodes()
    return {"items": promos}


@app.post("/api/admin/promocodes")
def admin_create_promocode(payload: AdminPromocodeCreatePayload):
    _ensure_admin(payload.user_id)
    new_id = promocodes_service.create_promocode(
        payload.code,
        payload.discount_type,
        payload.discount_value,
        payload.min_order_total or 0,
        payload.max_uses or 0,
        payload.valid_from,
        payload.valid_to,
        payload.description,
    )
    if payload.is_active is not None and new_id > 0:
        promocodes_service.update_promocode(new_id, is_active=1 if payload.is_active else 0)
    if new_id < 0:
        raise HTTPException(status_code=400, detail="Duplicate code")
    return {"id": new_id}


@app.put("/api/admin/promocodes/{promocode_id}")
def admin_update_promocode(promocode_id: int, payload: AdminPromocodeUpdatePayload):
    _ensure_admin(payload.user_id)
    updated = promocodes_service.update_promocode(
        promocode_id,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_order_total=payload.min_order_total,
        max_uses=payload.max_uses,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        description=payload.description,
        is_active=1 if payload.is_active is True else 0 if payload.is_active is False else None,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return {"ok": True}

