import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl
from uuid import uuid4

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from config import get_settings
from database import get_session, init_db
from models import AuthSession, User
from services import admin_notes as admin_notes_service
from services import bans as bans_service
from services import cart as cart_service
from services import favorites as favorites_service
from services import orders as orders_service
from services import products as products_service
from services import promocodes as promocodes_service
from services import stats as stats_service
from services import users as users_service


app = FastAPI(title="MiniDeN Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ALLOWED_TYPES = {"basket", "course"}

SETTINGS = get_settings()
BOT_TOKEN = SETTINGS.bot_token


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/env")
def api_env():
    from config import get_settings

    settings = get_settings()
    bot_username = settings.bot_username.lstrip("@") if hasattr(settings, "bot_username") else ""
    return {
        "bot_link": f"https://t.me/{bot_username}",
        "channel_link": settings.required_channel_link,
    }


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


class AuthPayload(BaseModel):
    initData: str | None = None
    user: dict | None = None


class ContactPayload(BaseModel):
    telegram_id: int
    phone: str | None = None


class FavoriteTogglePayload(BaseModel):
    telegram_id: int
    product_id: int
    type: str


def _ensure_admin(user_id: int | None) -> int:
    if user_id is None or not users_service.is_admin(int(user_id)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return int(user_id)


def _parse_webapp_user(init_data: str) -> dict | None:
    if not init_data:
        raise HTTPException(status_code=401, detail="Unauthorized")

    data_pairs = dict(parse_qsl(init_data, strict_parsing=False))
    received_hash = data_pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Unauthorized")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_pairs.items()))
    secret_key = hmac.new(f"WebAppData{BOT_TOKEN}".encode(), digestmod=hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_json = data_pairs.get("user")
    if not user_json:
        return None

    try:
        return json.loads(user_json)
    except json.JSONDecodeError:
        return None


def _full_name(user) -> str:
    parts = [user.first_name, user.last_name]
    return " ".join(part for part in parts if part).strip()


@app.post("/api/auth/create-token")
def api_auth_create_token():
    """
    Сайт запрашивает токен для авторизации.
    Возвращаем новый UUID и создаём пустую сессию в БД.
    """
    token = str(uuid4())
    with get_session() as s:
        s.add(AuthSession(token=token))
    return {"token": token}


@app.get("/api/auth/check")
def api_auth_check(token: str, request: Request, response: Response):
    """
    Сайт опрашивает этот эндпоинт каждые 0.5–1 сек после того,
    как пользователь перешёл в бота по ссылке с этим токеном.
    Если telegram_id уже записан в AuthSession — авторизуем.
    """
    with get_session() as s:
        session = s.query(AuthSession).filter(AuthSession.token == token).first()
        if not session:
            return {"ok": False, "reason": "not_found"}

        if not session.telegram_id:
            # пользователь ещё не нажал старт в боте
            return {"ok": False, "reason": "pending"}

        # telegram_id есть — авторизуем пользователя
        telegram_id = session.telegram_id

        user = s.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            # на всякий случай создаём пользователя, если его ещё нет
            user = User(telegram_id=telegram_id)
            s.add(user)
            s.flush()

        # ставим cookie с tg_user_id, чтобы сайт знал, кто мы
        response.set_cookie(
            key="tg_user_id",
            value=str(telegram_id),
            httponly=True,
            max_age=30 * 24 * 60 * 60,  # 30 дней
            samesite="lax",
        )

        return {"ok": True, "telegram_id": telegram_id}


@app.get("/api/auth/telegram-login")
def api_auth_telegram_login(request: Request):
    """
    Авторизация через Telegram Login Widget (браузер на сайте).
    Telegram делает GET на этот URL с параметрами:
    id, first_name, last_name, username, photo_url, auth_date, hash.
    Алгоритм проверки: https://core.telegram.org/widgets/login
    """
    params = dict(request.query_params)
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=400, detail="Missing hash")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items()) if v is not None and v != ""
    )

    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=400, detail="Invalid login data")

    auth_date = int(params.get("auth_date", "0") or 0)
    if auth_date and time.time() - auth_date > 86400:
        raise HTTPException(status_code=400, detail="Login data is too old")

    user_data = {
        "id": int(params["id"]),
        "first_name": params.get("first_name") or "",
        "last_name": params.get("last_name") or "",
        "username": params.get("username") or "",
        "photo_url": params.get("photo_url") or "",
    }

    try:
        user = users_service.get_or_create_user_from_telegram(user_data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user data")

    response = RedirectResponse(url="/webapp/profile.html", status_code=302)
    response.set_cookie(
        key="tg_user_id",
        value=str(user.telegram_id),
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/api/auth/session")
def api_auth_session(request: Request):
    """
    Авторизация из браузера по ранее установленной cookie tg_user_id.
    Возвращает тот же формат данных, что и /api/auth/telegram.
    """
    user_id = request.cookies.get("tg_user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No session")

    try:
        telegram_id = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session")

    user = users_service.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    full_name = _full_name(user) or user.username or ""

    user_orders = orders_service.get_orders_by_user(telegram_id)
    user_favorites = favorites_service.list_favorites(telegram_id)
    user_stats = stats_service.get_user_stats(telegram_id)
    ban_status = bans_service.is_banned(telegram_id)
    notes = []
    if user.is_admin:
        notes = admin_notes_service.list_notes(telegram_id)

    return {
        "ok": True,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "full_name": full_name,
        "is_admin": bool(user.is_admin),
        "phone": user.phone,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "orders": user_orders,
        "favorites": user_favorites,
        "stats": user_stats,
        "ban": ban_status,
        "notes": notes,
    }


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
    value: int
    min_order_total: int | None = None
    max_uses: int | None = None
    expires_at: str | None = None
    active: bool | None = None


class AdminPromocodeUpdatePayload(BaseModel):
    user_id: int
    discount_type: str | None = None
    value: int | None = None
    min_order_total: int | None = None
    max_uses: int | None = None
    expires_at: str | None = None
    active: bool | None = None


class PromocodeValidatePayload(BaseModel):
    telegram_id: int
    code: str
    total: int


@app.post("/api/auth/telegram")
def api_auth_telegram(payload: AuthPayload):
    if not payload.initData and not payload.user:
        raise HTTPException(status_code=400, detail="initData is required")

    user_data = None
    if payload.initData:
        user_data = _parse_webapp_user(payload.initData)

    if not user_data and payload.user:
        user_data = payload.user

    if not user_data or "id" not in user_data:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user = users_service.get_or_create_user_from_telegram(user_data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user data")

    full_name = _full_name(user) or user.username or ""

    return {
        "ok": True,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "full_name": full_name,
        "is_admin": bool(user.is_admin),
    }


@app.get("/api/categories")
def api_categories(type: str):
    """
    Вернуть список категорий для товаров или курсов.
    Ожидаемый формат элементов:
    {
      "id": int,
      "slug": str,
      "name": str,
    }
    """
    product_type = _validate_type(type)
    return products_service.list_categories(product_type)


@app.get("/api/products")
def api_products(type: str, category_slug: str | None = None):
    """
    Вернуть список товаров/курсов.
    Если category_slug передан — фильтровать по категории.
    """
    product_type = _validate_type(type)
    return products_service.list_products(product_type, category_slug=category_slug)


@app.get("/api/cart")
def api_cart(user_id: int):
    items, removed = cart_service.get_cart_items(user_id)

    normalized_items: list[dict[str, Any]] = []
    total = 0

    for item in items:
        price = int(item.get("price", 0))
        qty = int(item.get("qty", 0))
        total += price * qty

        normalized_items.append(
            {
                "product_id": int(item.get("product_id")),
                "name": item.get("name"),
                "price": price,
                "qty": qty,
                "type": item.get("type"),
                "category_name": item.get("category_name"),
            }
        )

    return {"items": normalized_items, "removed_items": removed, "total": total}


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
        product_id=int(payload.product_id),
        qty=qty,
        product_type=payload.type,
    )

    return {"ok": True}


@app.post("/api/cart/update")
def api_cart_update(payload: CartItemPayload):
    qty = payload.qty or 0

    if qty <= 0:
        cart_service.remove_from_cart(payload.user_id, int(payload.product_id), payload.type)
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
            if int(i.get("product_id")) == int(payload.product_id) and i.get("type") == payload.type
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
            product_type=payload.type,
        )

    return {"ok": True}


@app.post("/api/cart/clear")
def api_cart_clear(payload: CartClearPayload):
    cart_service.clear_cart(payload.user_id)
    return {"ok": True}


@app.get("/api/me")
def api_me(telegram_id: int):
    user = users_service.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_orders = orders_service.get_orders_by_user(telegram_id)
    user_favorites = favorites_service.list_favorites(telegram_id)
    user_stats = stats_service.get_user_stats(telegram_id)
    ban_status = bans_service.is_banned(telegram_id)
    notes = []
    if user.is_admin:
        notes = admin_notes_service.list_notes(telegram_id)

    return {
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "is_admin": bool(user.is_admin),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "orders": user_orders,
        "favorites": user_favorites,
        "stats": user_stats,
        "ban": ban_status,
        "notes": notes,
    }


@app.post("/api/me/contact")
def api_me_contact(payload: ContactPayload):
    try:
        user = users_service.update_user_contact(payload.telegram_id, payload.phone)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")

    return {"ok": True, "phone": user.phone}


@app.get("/api/favorites")
def api_favorites(telegram_id: int):
    user = users_service.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return favorites_service.list_favorites(telegram_id)


@app.post("/api/favorites/toggle")
def api_favorites_toggle(payload: FavoriteTogglePayload):
    product_type = _validate_type(payload.type)
    user = users_service.get_user_by_telegram_id(payload.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    already_fav = favorites_service.is_favorite(
        payload.telegram_id, payload.product_id, product_type
    )
    if already_fav:
        favorites_service.remove_favorite(payload.telegram_id, payload.product_id, product_type)
        is_fav = False
    else:
        favorites_service.add_favorite(payload.telegram_id, payload.product_id, product_type)
        is_fav = True

    return {"ok": True, "is_favorite": is_fav}


@app.post("/api/promocode/validate")
def api_promocode_validate(payload: PromocodeValidatePayload):
    result = promocodes_service.validate_promocode(
        payload.code, payload.telegram_id, payload.total
    )
    if not result:
        raise HTTPException(status_code=400, detail="Invalid promocode")

    return {
        "code": result["code"],
        "discount_type": result["discount_type"],
        "value": result["value"],
        "discount_amount": result["discount_amount"],
        "final_total": result["final_total"],
    }


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
def admin_orders(user_id: int, status: str | None = None, limit: int = 100):
    _ensure_admin(user_id)
    orders = orders_service.list_orders(status=status, limit=limit)
    return {"items": orders}


@app.get("/api/admin/stats")
def admin_stats(user_id: int):
    _ensure_admin(user_id)
    return stats_service.get_admin_dashboard_stats()


@app.get("/api/admin/notes")
def admin_notes(user_id: int, target_id: int):
    _ensure_admin(user_id)
    return {"items": admin_notes_service.list_notes(target_id)}


class AdminNotePayload(BaseModel):
    user_id: int
    target_id: int
    note: str


@app.post("/api/admin/notes")
def admin_add_note(payload: AdminNotePayload):
    _ensure_admin(payload.user_id)
    record = admin_notes_service.add_note(payload.target_id, payload.note, admin_id=payload.user_id)
    return {
        "id": record.id,
        "user_id": record.user_id,
        "admin_id": record.admin_id,
        "note": record.note,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@app.delete("/api/admin/notes/{note_id}")
def admin_delete_note(note_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = admin_notes_service.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


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
    try:
        promo_data = payload.dict()
        promo_data.pop("user_id", None)
        promo = promocodes_service.create_promocode(promo_data)
    except ValueError as exc:  # noqa: WPS440
        raise HTTPException(status_code=400, detail=str(exc))
    return promo


@app.put("/api/admin/promocodes/{promocode_id}")
def admin_update_promocode(promocode_id: int, payload: AdminPromocodeUpdatePayload):
    _ensure_admin(payload.user_id)
    update_data = payload.dict()
    update_data.pop("user_id", None)
    updated = promocodes_service.update_promocode(promocode_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return updated

