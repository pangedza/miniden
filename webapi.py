"""
Основной backend MiniDeN (FastAPI).
Приложение: webapi:app
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl
from uuid import uuid4

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import get_settings
from database import get_session, init_db
from models import AuthSession, User
from services import admin_notes as admin_notes_service
from services import cart as cart_service
from services import favorites as favorites_service
from services import orders as orders_service
from services import products as products_service
from services import promocodes as promocodes_service
from services import stats as stats_service
from services import user_admin as user_admin_service
from services import user_stats as user_stats_service
from services import users as users_service
from utils.texts import format_order_for_admin


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
AUTH_SESSION_TTL_SECONDS = 600
COOKIE_MAX_AGE = 30 * 24 * 60 * 60


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


class CheckoutPayload(BaseModel):
    user_id: int
    user_name: str | None = Field(None, description="Имя пользователя из Telegram")
    customer_name: str = Field(..., description="Имя клиента")
    contact: str = Field(..., description="Способ связи")
    comment: str | None = None
    promocode: str | None = None


class AuthPayload(BaseModel):
    initData: str | None = None
    user: dict | None = None
    include_notes: bool | None = False


class ProfileUpdatePayload(BaseModel):
    full_name: str | None = None
    phone: str | None = None


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


def _parse_webapp_user(init_data: str, bot_token: str | None = None) -> dict | None:
    if not init_data:
        raise HTTPException(status_code=400, detail="initData is empty")

    data_pairs = dict(parse_qsl(init_data, strict_parsing=False))
    received_hash = data_pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash")

    resolved_bot_token = bot_token or BOT_TOKEN
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_pairs.items()))
    secret_key = hmac.new(f"WebAppData{resolved_bot_token}".encode(), digestmod=hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    auth_date_raw = data_pairs.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid auth_date")

        if time.time() - auth_date > 24 * 60 * 60:
            raise HTTPException(status_code=401, detail="auth_date is too old")

    user_json = data_pairs.get("user")
    if not user_json:
        return None

    try:
        return json.loads(user_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid user payload")


def _full_name(user) -> str:
    parts = [user.first_name, user.last_name]
    return " ".join(part for part in parts if part).strip()


def _split_full_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.split(" ", 1)
    first_name = parts[0].strip() if parts else None
    last_name = parts[1].strip() if len(parts) > 1 else None
    return first_name or None, last_name or None


def _build_user_profile(session: Session, user: User, *, include_notes: bool = False) -> dict:
    """
    Собирает полный профиль пользователя для фронтенда.

    Возвращаемые поля:
      - ok: True
      - telegram_id: int
      - telegram_username: str | None
      - full_name: str | None
      - phone: str | None
      - created_at: str | None (ISO8601)
      - is_admin: bool
      - orders: list[dict]
      - stats: dict
      - favorites: list[dict]
      - ban: dict | None
    Заметки (notes) для CRM можно добавлять только если user.is_admin и include_notes=True.
    """
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    telegram_id = int(user.telegram_id)
    display_full_name = _full_name(user) or None

    try:
        orders = orders_service.get_orders_by_user(telegram_id) or []
    except Exception:
        orders = []

    try:
        favorites = favorites_service.list_favorites(telegram_id) or []
    except Exception:
        favorites = []

    try:
        courses = orders_service.get_user_courses_with_access(telegram_id) or []
    except Exception:
        courses = []

    try:
        stats = user_stats_service.get_user_order_stats(telegram_id) or {}
    except Exception:
        stats = {}

    try:
        ban_status = user_admin_service.get_user_ban_status(telegram_id) or None
    except Exception:
        ban_status = None

    notes = []
    if include_notes and user.is_admin:
        try:
            notes = user_admin_service.get_user_notes(telegram_id, limit=20) or []
        except Exception:
            notes = []

    return {
        "ok": True,
        "telegram_id": telegram_id,
        "telegram_username": user.username,
        "username": user.username,
        "full_name": display_full_name,
        "phone": user.phone,
        "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        "is_admin": bool(user.is_admin),
        "orders": orders,
        "favorites": favorites,
        "courses": courses,
        "stats": stats,
        "ban": ban_status,
        "notes": notes,
    }


def _get_current_user_from_cookie(session: Session, request: Request) -> User | None:
    user_id = request.cookies.get("tg_user_id")
    if not user_id:
        return None

    try:
        telegram_id = int(user_id)
    except ValueError:
        return None

    return session.query(User).filter(User.telegram_id == telegram_id).first()


def _product_by_type(product_type: str, product_id: int, *, include_inactive: bool = False):
    if product_type == "basket":
        return products_service.get_basket_by_id(product_id, include_inactive=include_inactive)
    return products_service.get_course_by_id(product_id, include_inactive=include_inactive)


def _build_cart_response(user_id: int) -> dict[str, Any]:
    items, removed_ids = cart_service.get_cart_items(user_id)

    normalized_items: list[dict[str, Any]] = []
    removed_items: list[dict[str, Any]] = []
    total = 0

    for item in items:
        product_type = item.get("type") or "basket"
        if product_type not in ALLOWED_TYPES:
            removed_items.append({"product_id": item.get("product_id"), "type": product_type, "reason": "invalid"})
            cart_service.remove_from_cart(user_id, int(item.get("product_id") or 0), product_type)
            continue
        try:
            product_id = int(item.get("product_id"))
        except (TypeError, ValueError):
            removed_items.append({"product_id": None, "type": product_type, "reason": "invalid"})
            continue

        product_info = _product_by_type(product_type, product_id)
        if not product_info:
            removed_items.append({"product_id": product_id, "type": product_type, "reason": "inactive"})
            cart_service.remove_from_cart(user_id, product_id, product_type)
            continue

        qty = max(int(item.get("qty") or 0), 0)
        if qty <= 0:
            cart_service.remove_from_cart(user_id, product_id, product_type)
            continue

        price = int(product_info.get("price") or 0)
        subtotal = price * qty
        total += subtotal

        normalized_items.append(
            {
                "product_id": product_id,
                "type": product_type,
                "name": product_info.get("name"),
                "price": price,
                "qty": qty,
                "subtotal": subtotal,
            }
        )

    for removed_id in removed_ids:
        product_info = products_service.get_product_by_id(removed_id, include_inactive=True)
        removed_items.append(
            {
                "product_id": removed_id,
                "type": product_info.get("type") if product_info else "unknown",
                "reason": "inactive" if product_info else "not_found",
            }
        )

    return {"items": normalized_items, "removed_items": removed_items, "total": total}


@app.post("/api/auth/create-token")
def api_auth_create_token():
    """
    Создать новую сессию авторизации для deeplink-а из бота.
    Возвращает {"ok": true, "token": "..."}.
    """
    token = str(uuid4())
    with get_session() as s:
        s.add(AuthSession(token=token))
    return {"ok": True, "token": token}


@app.get("/api/auth/check")
def api_auth_check(token: str, response: Response, include_notes: bool = False):
    """
    Проверить токен AuthSession, выданный по deeplink-у из бота.
    При успешной проверке возвращает профиль пользователя в едином формате.
    """
    with get_session() as s:
        session = s.query(AuthSession).filter(AuthSession.token == token).first()
        if not session:
            response.status_code = 404
            return {"ok": False, "reason": "not_found"}

        if session.created_at and datetime.utcnow() - session.created_at > timedelta(seconds=AUTH_SESSION_TTL_SECONDS):
            response.status_code = 410
            return {"ok": False, "reason": "expired"}

        if not session.telegram_id:
            return {"ok": False, "reason": "pending"}

        telegram_id = int(session.telegram_id)

        user = s.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id)
            s.add(user)
            s.flush()

        profile = _build_user_profile(s, user, include_notes=include_notes)

    if not profile:
        response.status_code = 404
        return {"ok": False, "reason": "not_found"}

    response.set_cookie(
        key="tg_user_id",
        value=str(telegram_id),
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
    )

    return profile


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

    response = RedirectResponse(url="/profile.html", status_code=302)
    response.set_cookie(
        key="tg_user_id",
        value=str(user.telegram_id),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/api/auth/session")
def api_auth_session(request: Request, response: Response, include_notes: bool = False):
    """
    Авторизация из браузера по ранее установленной cookie tg_user_id.
    Возвращает профиль пользователя в едином формате или ok=false при ошибке.
    """
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            response.status_code = 401
            return {"ok": False, "detail": "unauthorized"}

        try:
            profile = _build_user_profile(session, user, include_notes=include_notes)
        except HTTPException as exc:
            response.status_code = exc.status_code
            return {"ok": False, "detail": exc.detail}

    return profile


class AdminProductsCreatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    image: str | None = None
    wb_url: str | None = None
    ozon_url: str | None = None
    yandex_url: str | None = None
    avito_url: str | None = None
    masterclass_url: str | None = None


class AdminProductsUpdatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    is_active: bool | None = None
    image: str | None = None
    wb_url: str | None = None
    ozon_url: str | None = None
    yandex_url: str | None = None
    avito_url: str | None = None
    masterclass_url: str | None = None


class AdminTogglePayload(BaseModel):
    user_id: int


class AdminOrderStatusPayload(BaseModel):
    user_id: int
    status: str


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
    """
    Авторизация WebApp по initData (из Telegram WebApp) или по заранее
    переданным данным user. Возвращает единый JSON-профиль пользователя.
    """
    if not payload.initData and not payload.user:
        raise HTTPException(status_code=400, detail="initData or user is required")

    user_data = None
    if payload.initData:
        try:
            user_data = _parse_webapp_user(payload.initData, BOT_TOKEN)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"ok": False, "detail": "invalid telegram webapp auth"},
            )
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"ok": False, "detail": "invalid telegram webapp auth"},
            )

    if not user_data and payload.user:
        user_data = payload.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Unauthorized: no user data")

    telegram_id = user_data.get("id")
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="Missing user id")

    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    full_name = " ".join([part for part in [first_name, last_name] if part]).strip() or None

    with get_session() as session:
        try:
            user = users_service.get_or_create_user_from_telegram(
                session,
                telegram_id=int(telegram_id),
                username=user_data.get("username"),
                full_name=full_name,
                phone=user_data.get("phone"),
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user data")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to authorize user")

        return _build_user_profile(session, user, include_notes=bool(payload.include_notes))


@app.post("/api/auth/logout")
def api_auth_logout(response: Response):
    """
    Logout для обычного сайта: сбрасывает cookie tg_user_id.
    Используется кнопкой "Выйти"/"Сменить пользователя".
    """
    response.delete_cookie("tg_user_id", path="/")
    return {"ok": True}


@app.post("/api/profile/update")
def api_profile_update(payload: ProfileUpdatePayload, request: Request):
    """
    Обновление имени и телефона текущего пользователя (по cookie tg_user_id).
    Telegram ID и username менять нельзя.
    """
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        if payload.full_name is not None:
            first_name, last_name = _split_full_name(payload.full_name.strip())
            user.first_name = first_name
            user.last_name = last_name
        if payload.phone is not None:
            user.phone = payload.phone.strip()

        session.add(user)
        session.commit()
        session.refresh(user)
        return {"ok": True, "user": _build_user_profile(session, user)}


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
    """Вернуть содержимое корзины пользователя и сумму заказа."""
    return _build_cart_response(user_id)


@app.post("/api/checkout")
def api_checkout(payload: CheckoutPayload):
    """Оформить заказ из текущей корзины WebApp."""
    items, removed_ids = cart_service.get_cart_items(payload.user_id)

    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    normalized_items: list[dict[str, Any]] = []
    removed_items: list[dict[str, Any]] = []
    total = 0

    for item in items:
        qty = max(int(item.get("qty") or 0), 0)
        if qty <= 0:
            continue

        try:
            product_id_int = int(item.get("product_id"))
        except (TypeError, ValueError):
            removed_items.append({"product_id": item.get("product_id"), "type": item.get("type"), "reason": "invalid"})
            cart_service.remove_from_cart(payload.user_id, int(item.get("product_id") or 0), item.get("type") or "basket")
            continue

        product_type = item.get("type") or "basket"
        if product_type not in ALLOWED_TYPES:
            removed_items.append({"product_id": product_id_int, "type": product_type, "reason": "invalid"})
            cart_service.remove_from_cart(payload.user_id, product_id_int, product_type)
            continue
        product_info = _product_by_type(product_type, product_id_int)

        if not product_info:
            removed_items.append({"product_id": product_id_int, "type": product_type, "reason": "inactive"})
            cart_service.remove_from_cart(payload.user_id, product_id_int, product_type)
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

    for removed_id in removed_ids:
        product_info = products_service.get_product_by_id(removed_id, include_inactive=True)
        removed_items.append(
            {
                "product_id": removed_id,
                "type": product_info.get("type") if product_info else "unknown",
                "reason": "inactive" if product_info else "not_found",
            }
        )

    if not normalized_items:
        cart_service.clear_cart(payload.user_id)
        raise HTTPException(status_code=400, detail="No valid items in cart")

    user_name = payload.user_name or "webapp"

    promo_result = None
    if payload.promocode:
        promo_result = promocodes_service.validate_promocode(payload.promocode, payload.user_id, total)
        if not promo_result:
            raise HTTPException(status_code=400, detail="Invalid promocode")

    discount_amount = int(promo_result.get("discount_amount", 0)) if promo_result else 0
    final_total = max(total - discount_amount, 0)

    order_text = format_order_for_admin(
        user_id=payload.user_id,
        user_name=user_name,
        items=normalized_items,
        total=final_total,
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
        total=final_total,
        customer_name=payload.customer_name,
        contact=payload.contact,
        comment=payload.comment or "",
        order_text=order_text,
        promocode_code=promo_result.get("code") if promo_result else None,
        discount_amount=discount_amount if promo_result else None,
    )

    if promo_result:
        promocodes_service.increment_usage(promo_result.get("code"))

    cart_service.clear_cart(payload.user_id)

    return {
        "ok": True,
        "order_id": order_id,
        "total": final_total,
        "discount_amount": discount_amount,
        "removed_items": removed_items,
    }


@app.post("/api/cart/add")
def api_cart_add(payload: CartItemPayload):
    qty = payload.qty or 1
    if qty <= 0:
        raise HTTPException(status_code=400, detail="qty must be positive")

    product_type = _validate_type(payload.type)
    product = _product_by_type(product_type, int(payload.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    cart_service.add_to_cart(
        user_id=payload.user_id,
        product_id=int(payload.product_id),
        qty=qty,
        product_type=product_type,
    )

    return _build_cart_response(payload.user_id)


@app.post("/api/cart/update")
def api_cart_update(payload: CartItemPayload):
    qty = payload.qty or 0
    product_type = _validate_type(payload.type)

    if qty <= 0:
        cart_service.remove_from_cart(payload.user_id, int(payload.product_id), product_type)
        return _build_cart_response(payload.user_id)

    product = _product_by_type(product_type, int(payload.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    current_items, _ = cart_service.get_cart_items(payload.user_id)
    existing = next(
        (
            i
            for i in current_items
            if int(i.get("product_id")) == int(payload.product_id) and i.get("type") == product_type
        ),
        None,
    )

    if existing:
        delta = qty - int(existing.get("qty") or 0)
        if delta != 0:
            cart_service.change_qty(payload.user_id, int(payload.product_id), delta, product_type)
    else:
        cart_service.add_to_cart(
            user_id=payload.user_id,
            product_id=int(payload.product_id),
            qty=qty,
            product_type=product_type,
        )

    return _build_cart_response(payload.user_id)


@app.post("/api/cart/clear")
def api_cart_clear(payload: CartClearPayload):
    cart_service.clear_cart(payload.user_id)
    return _build_cart_response(payload.user_id)


@app.get("/api/me")
def api_me(telegram_id: int):
    """
    Вернуть профиль пользователя (личный кабинет) по его telegram_id.
    Формат ответа совпадает с /api/auth/telegram, чтобы фронту было удобно.
    """
    with get_session() as session:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        profile = _build_user_profile(session, user, include_notes=True)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    return profile


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
        image=payload.image,
        wb_url=payload.wb_url,
        ozon_url=payload.ozon_url,
        yandex_url=payload.yandex_url,
        avito_url=payload.avito_url,
        masterclass_url=payload.masterclass_url,
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
        image=payload.image,
        wb_url=payload.wb_url,
        ozon_url=payload.ozon_url,
        yandex_url=payload.yandex_url,
        avito_url=payload.avito_url,
        masterclass_url=payload.masterclass_url,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.patch("/api/admin/products/{product_id}/toggle_active")
@app.post("/api/admin/products/{product_id}/toggle")
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


@app.post("/api/admin/orders/{order_id}/status")
@app.put("/api/admin/orders/{order_id}/status")
def admin_order_set_status(order_id: int, payload: AdminOrderStatusPayload):
    _ensure_admin(payload.user_id)
    if payload.status not in orders_service.STATUS_TITLES:
        raise HTTPException(status_code=400, detail="Invalid status")
    updated = orders_service.update_order_status(order_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders_service.get_order_by_id(order_id)


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

