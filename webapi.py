"""
Основной backend MiniDeN (FastAPI).
Приложение: webapi:app
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl
from uuid import uuid4

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
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
from services import home as home_service
from services import faq_service
from services import orders as orders_service
from services import products as products_service
from services import promocodes as promocodes_service
from services import reviews as reviews_service
from services import stats as stats_service
from services import user_admin as user_admin_service
from services import user_stats as user_stats_service
from services import users as users_service
from services.telegram_webapp_auth import authenticate_telegram_webapp_user
from utils.texts import format_order_for_admin
from schemas.home import HomeBannerIn, HomePostIn, HomeSectionIn


app = FastAPI(title="MiniDeN Web API", version="1.0.0")

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def json_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: WPS430
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


ALLOWED_TYPES = {"basket", "course"}

SETTINGS = get_settings()
BOT_TOKEN = SETTINGS.bot_token
AUTH_SESSION_TTL_SECONDS = 600
COOKIE_MAX_AGE = 30 * 24 * 60 * 60
MEDIA_ROOT = Path("/opt/miniden/media")
REQUIRED_DIRS = [
    MEDIA_ROOT,
    MEDIA_ROOT / "users",
    MEDIA_ROOT / "products",
    MEDIA_ROOT / "courses",
    MEDIA_ROOT / "home",
    MEDIA_ROOT / "reviews",
    MEDIA_ROOT / "tmp",
    MEDIA_ROOT / "tmp/products",
    MEDIA_ROOT / "tmp/courses",
]


def ensure_media_dirs() -> None:
    for d in REQUIRED_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def _save_uploaded_image(file: UploadFile, base_folder: str) -> str:
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Неверный формат изображения")

    ensure_media_dirs()

    ext = (file.filename or "jpg").split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"

    filename = f"{uuid4().hex}.{ext}"
    full_path = MEDIA_ROOT / base_folder / filename

    with full_path.open("wb") as f:
        f.write(file.file.read())

    relative = full_path.relative_to(MEDIA_ROOT).as_posix()
    return f"/media/{relative}"


def _delete_media_file(url: str | None) -> None:
    if not url or not url.startswith("/media/"):
        return

    relative = url.split("/media/", 1)[1]
    target_path = MEDIA_ROOT / relative
    try:
        if target_path.is_file():
            target_path.unlink()
    except OSError:
        # тихо игнорируем ошибки удаления, чтобы не ломать основной поток
        pass


class AdminImageKind(str, Enum):
    product = "product"
    course = "course"
    home = "home"


@app.on_event("startup")
def startup_event() -> None:
    ensure_media_dirs()
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


@app.get("/api/home")
def api_home():
    return home_service.get_active_home_data()


@app.get("/api/faq")
def api_faq(category: str | None = None):
    items = faq_service.get_faq_list(category)
    return [_faq_to_dict(item) for item in items]


@app.get("/api/faq/{faq_id}")
def api_faq_detail(faq_id: int):
    item = faq_service.get_faq_item(faq_id)
    if not item:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return _faq_to_dict(item)


def _validate_type(product_type: str) -> str:
    if product_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="type must be 'basket' or 'course'")
    return product_type


def _faq_to_dict(item) -> dict:
    return {
        "id": int(item.id),
        "category": item.category,
        "question": item.question,
        "answer": item.answer,
        "sort_order": int(item.sort_order or 0),
    }


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


class TelegramAuthPayload(BaseModel):
    init_data: str | None = None
    auth_query: str | None = None


class TelegramWebAppAuthPayload(BaseModel):
    init_data: str | None = None


class ProfileUpdatePayload(BaseModel):
    full_name: str | None = None
    phone: str | None = None


class FaqCreatePayload(BaseModel):
    category: str
    question: str
    answer: str
    sort_order: int | None = 0


class FaqUpdatePayload(BaseModel):
    category: str | None = None
    question: str | None = None
    answer: str | None = None
    sort_order: int | None = None


class AvatarUpdatePayload(BaseModel):
    avatar_url: str


class ContactPayload(BaseModel):
    telegram_id: int
    phone: str | None = None


class FavoriteTogglePayload(BaseModel):
    telegram_id: int
    product_id: int
    type: str


class ReviewCreatePayload(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    text: str
    photos: list[str] | None = None
    order_id: int | None = None


class ReviewStatusUpdatePayload(BaseModel):
    status: str
    is_deleted: bool | None = None


def _ensure_admin(user_id: int | None) -> int:
    if user_id is None or not users_service.is_admin(int(user_id)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return int(user_id)


def _validate_telegram_webapp_init_data(
    init_data: str, bot_token: str | None = None
) -> dict[str, Any]:
    if not init_data:
        raise HTTPException(status_code=400, detail="init_data_missing")

    try:
        parsed_pairs = list(parse_qsl(init_data, keep_blank_values=True))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid init_data format")

    received_hash = None
    filtered_pairs: list[tuple[str, str]] = []
    for key, value in parsed_pairs:
        if key == "hash":
            received_hash = value
        else:
            filtered_pairs.append((key, value))

    if not received_hash:
        raise HTTPException(status_code=401, detail="invalid_signature")

    resolved_bot_token = bot_token or BOT_TOKEN
    secret_key = hashlib.sha256(resolved_bot_token.encode()).digest()
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(filtered_pairs, key=lambda item: item[0]))
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, str(received_hash)):
        logger.warning("Telegram WebApp auth failed: invalid signature")
        raise HTTPException(status_code=401, detail="invalid_signature")

    data_dict = {k: v for k, v in filtered_pairs}

    auth_date_raw = data_dict.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError:
            raise HTTPException(status_code=401, detail="invalid_signature")

        if time.time() - auth_date > 24 * 60 * 60:
            raise HTTPException(status_code=401, detail="invalid_signature")

    user_json = data_dict.get("user")
    if not user_json:
        raise HTTPException(status_code=401, detail="invalid_signature")

    try:
        return json.loads(user_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid user payload")


def _parse_telegram_auth_data(auth_payload: str, bot_token: str | None = None) -> dict:
    if not auth_payload:
        raise HTTPException(status_code=400, detail="auth payload is empty")

    normalized_payload = auth_payload[1:] if auth_payload.startswith("?") else auth_payload

    try:
        parsed_pairs = list(parse_qsl(normalized_payload, keep_blank_values=True))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid auth payload format")

    received_hash = None
    filtered_pairs: list[tuple[str, str]] = []
    for key, value in parsed_pairs:
        if key == "hash":
            received_hash = value
        else:
            filtered_pairs.append((key, value))

    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash")

    resolved_bot_token = bot_token or BOT_TOKEN
    secret_key = hashlib.sha256(resolved_bot_token.encode()).digest()
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(filtered_pairs, key=lambda item: item[0]))
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, str(received_hash)):
        raise HTTPException(status_code=401, detail="Invalid auth signature")

    data_dict = {k: v for k, v in filtered_pairs}

    auth_date_raw = data_dict.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid auth_date")

        if time.time() - auth_date > 24 * 60 * 60:
            raise HTTPException(status_code=401, detail="auth_date is too old")

    return data_dict


def _full_name(user) -> str:
    parts = [user.first_name, user.last_name]
    return " ".join(part for part in parts if part).strip()


def _extract_user_from_auth_data(data: dict[str, Any]) -> dict[str, Any]:
    if "user" in data:
        try:
            return json.loads(data["user"])
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid user payload")
    return data


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
        orders = orders_service.get_orders_by_user(
            telegram_id, include_archived=False
        ) or []
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
        "avatar_url": user.avatar_url,
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


def get_admin_user(request: Request) -> User:
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user or not getattr(user, "is_admin", False):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user


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
                "category_id": product_info.get("category_id"),
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


@app.post("/api/auth/telegram_webapp")
def api_auth_telegram_webapp(payload: TelegramWebAppAuthPayload, response: Response):
    """Авторизация WebApp через init_data внутри Telegram."""

    init_data = (payload.init_data or "").strip()
    if not init_data:
        response.status_code = 400
        return {"status": "error", "error": "init_data_missing"}

    try:
        user_data = _validate_telegram_webapp_init_data(init_data, BOT_TOKEN)
    except HTTPException as exc:
        response.status_code = exc.status_code
        error_code = exc.detail if isinstance(exc.detail, str) else "invalid_signature"
        if error_code == "init_data is empty":
            error_code = "init_data_missing"
        if error_code not in {"init_data_missing", "invalid_signature"}:
            error_code = "invalid_signature"
        return {"status": "error", "error": error_code}

    telegram_id = user_data.get("id")
    if telegram_id is None:
        response.status_code = 400
        return {"status": "error", "error": "invalid_user"}

    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    full_name = " ".join(part for part in [first_name, last_name] if part).strip() or None

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
            response.status_code = 400
            return {"status": "error", "error": "invalid_user"}
        except Exception:
            response.status_code = 500
            return {"status": "error", "error": "authorization_failed"}

        response.set_cookie(
            key="tg_user_id",
            value=str(user.telegram_id),
            httponly=True,
            max_age=COOKIE_MAX_AGE,
            samesite="lax",
        )

        logger.info(
            "Telegram WebApp auth succeeded: telegram_id=%s, user_id=%s",
            user.telegram_id,
            user.id,
        )

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
            },
        }


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


def _wrap_home_banner_error(action: str, func):
    try:
        return func()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: WPS430
        logger.exception("Home banner %s failed", action)
        raise HTTPException(status_code=500, detail="Ошибка сервера") from exc


@app.get("/api/auth/session")
async def api_auth_session(request: Request, response: Response, include_notes: bool = False):
    """
    Авторизация из браузера или Telegram WebApp по cookie tg_user_id.

    Если cookie отсутствует, пробует авторизовать пользователя по initData
    из запроса Telegram WebApp. Если сессия не найдена — возвращает
    `{"authenticated": false}` без ошибки 401.
    """
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            user = await authenticate_telegram_webapp_user(
                request,
                session,
                _validate_telegram_webapp_init_data,
                response=response,
                cookie_max_age=COOKIE_MAX_AGE,
            )

        if not user:
            return {"authenticated": False}

        try:
            profile = _build_user_profile(session, user, include_notes=include_notes)
        except HTTPException as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return {"authenticated": True, "user": profile}


class AdminProductsCreatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    short_description: str | None = ""
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    image: str | None = None
    image_url: str | None = None
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
    short_description: str | None = ""
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    is_active: bool | None = None
    image: str | None = None
    image_url: str | None = None
    wb_url: str | None = None
    ozon_url: str | None = None
    yandex_url: str | None = None
    avito_url: str | None = None
    masterclass_url: str | None = None


class AdminProductCategoryPayload(BaseModel):
    user_id: int
    name: str
    slug: str | None = None
    sort_order: int = 0
    is_active: bool | None = True
    type: str = "basket"


class AdminProductCategoryUpdatePayload(BaseModel):
    user_id: int
    name: str | None = None
    slug: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    type: str | None = None


class AdminTogglePayload(BaseModel):
    user_id: int
    type: str


class AdminOrderStatusPayload(BaseModel):
    user_id: int
    status: str


class AdminPromocodeCreatePayload(BaseModel):
    user_id: int
    code: str
    discount_type: str
    discount_value: float
    scope: str = "all"
    target_id: int | None = None
    max_uses: int | None = None
    date_start: str | None = None
    date_end: str | None = None
    expires_at: str | None = None
    active: bool | None = None
    one_per_user: bool | None = None


class AdminPromocodeUpdatePayload(BaseModel):
    user_id: int
    code: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    max_uses: int | None = None
    active: bool | None = None
    scope: str | None = None
    target_id: int | None = None
    date_start: str | None = None
    date_end: str | None = None
    expires_at: str | None = None
    one_per_user: bool | None = None


class PromocodeCartItemPayload(BaseModel):
    product_id: int
    qty: int = 1
    type: str = "basket"
    price: int | None = None
    category_id: int | None = None


class PromocodeValidatePayload(BaseModel):
    telegram_id: int
    code: str
    items: list[PromocodeCartItemPayload] | None = None


class CartPromocodeApplyPayload(BaseModel):
    user_id: int
    code: str


@app.post("/api/auth/telegram")
def api_auth_telegram(payload: TelegramAuthPayload, response: Response):
    """
    Единый endpoint авторизации через Telegram WebApp или Login Widget.

    Поддерживает:
      * init_data — строка initData из Telegram WebApp;
      * auth_query — query-string из Telegram Login Widget или deeplink-а.
    """

    if (payload.init_data is None and payload.auth_query is None) or (
        payload.init_data is not None and payload.auth_query is not None
    ):
        raise HTTPException(status_code=400, detail="Provide exactly one of init_data or auth_query")

    raw_auth_payload = payload.init_data or payload.auth_query or ""

    try:
        validated_data = _parse_telegram_auth_data(raw_auth_payload, BOT_TOKEN)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid telegram auth data")

    user_data = _extract_user_from_auth_data(validated_data)

    telegram_id = user_data.get("id")
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="Missing user id")

    try:
        telegram_id_int = int(telegram_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid user id")

    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    full_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    phone = user_data.get("phone") or user_data.get("phone_number")

    with get_session() as session:
        try:
            user = users_service.get_or_create_user_from_telegram(
                session,
                telegram_id=telegram_id_int,
                username=user_data.get("username"),
                full_name=full_name,
                phone=phone,
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user data")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to authorize user")

        response.set_cookie(
            key="tg_user_id",
            value=str(user.telegram_id),
            httponly=True,
            max_age=COOKIE_MAX_AGE,
            samesite="lax",
        )

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
            },
        }


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


@app.post("/api/profile/avatar-url")
def update_avatar_url(payload: AvatarUpdatePayload, request: Request):
    """
    Обновление avatar_url для текущего пользователя.
    Фактический файл аватара должен быть уже размещён владельцем проекта на сервере
    по указанному пути (например, /media/users/<telegram_id>/avatar.jpg).
    """
    ensure_media_dirs()
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        avatar_url = payload.avatar_url.strip()
        user.avatar_url = avatar_url or None

        session.add(user)
        session.commit()
        session.refresh(user)

        profile = _build_user_profile(session, user)
        return {"ok": True, "avatar_url": user.avatar_url, "profile": profile}


@app.post("/api/profile/avatar")
def upload_avatar(request: Request, file: UploadFile = File(...)) -> dict:
    """Загрузка файла аватара текущего пользователя."""

    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Неверный формат изображения")

    ensure_media_dirs()

    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user_dir = MEDIA_ROOT / "users" / str(user.telegram_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        ext = (file.filename or "jpg").split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        filename = f"avatar.{ext}"
        full_path = user_dir / filename

        with full_path.open("wb") as f:
            f.write(file.file.read())

        relative = full_path.relative_to(MEDIA_ROOT).as_posix()
        user.avatar_url = f"/media/{relative}"

        session.add(user)
        session.commit()
        session.refresh(user)

        profile = _build_user_profile(session, user)
        return {"ok": True, "avatar_url": user.avatar_url, "profile": profile}


@app.post("/api/orders/{order_id}/archive")
def archive_order(order_id: int, request: Request):
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

    archived = orders_service.archive_order_for_user(order_id, int(user.telegram_id))
    if not archived:
        order = orders_service.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=403, detail="Forbidden")

    return {"ok": True}


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
    return products_service.list_products(product_type, category_slug=category_slug, is_active=True)


@app.get("/api/products/{product_id}")
def api_product_detail(product_id: int):
    """Возвращает данные одного товара или мастер-класса по ID."""
    product = products_service.get_product_by_id(product_id)
    if not product or not product.get("is_active"):
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/api/masterclasses/{masterclass_id}")
def api_masterclass_detail(masterclass_id: int):
    """Возвращает данные мастер-класса по ID."""
    masterclass = products_service.get_course_by_id(masterclass_id)
    if not masterclass or not masterclass.get("is_active"):
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return masterclass


@app.post("/api/masterclasses/{masterclass_id}/reviews")
def create_masterclass_review(
    masterclass_id: int, payload: ReviewCreatePayload, request: Request
):
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

    masterclass = products_service.get_course_by_id(masterclass_id)
    if not masterclass or not masterclass.get("is_active", True):
        raise HTTPException(status_code=404, detail="Masterclass not found")

    try:
        review_id = reviews_service.create_masterclass_review(
            masterclass_id,
            user,
            payload.rating,
            payload.text,
            payload.photos,
            payload.order_id,
        )
    except ValueError as exc:  # pragma: no cover - defensive
        detail = "Invalid payload"
        if str(exc) == "masterclass_not_found":
            detail = "Masterclass not found"
        elif str(exc) == "rating must be between 1 and 5":
            detail = str(exc)
        raise HTTPException(status_code=400, detail=detail)

    return {"success": True, "review_id": review_id, "status": "pending"}


@app.get("/api/masterclasses/{masterclass_id}/reviews")
def get_masterclass_reviews(
    masterclass_id: int, page: int = 1, limit: int = 20, with_meta: bool = False
):
    masterclass = products_service.get_course_by_id(masterclass_id)
    if not masterclass:
        raise HTTPException(status_code=404, detail="Masterclass not found")

    reviews = reviews_service.get_reviews_for_masterclass(masterclass_id, page=page, limit=limit)
    if with_meta:
        return {"items": reviews, "page": page, "limit": limit}
    return reviews


@app.post("/api/products/{product_id}/reviews")
def create_product_review(product_id: int, payload: ReviewCreatePayload, request: Request):
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

    product = products_service.get_product_by_id(product_id)
    if not product or not product.get("is_active", True):
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        review_id = reviews_service.create_review(
            product_id,
            user,
            payload.rating,
            payload.text,
            payload.photos,
            payload.order_id,
        )
    except ValueError as exc:  # pragma: no cover - defensive
        detail = "Invalid payload"
        if str(exc) == "product_not_found":
            detail = "Product not found"
        elif str(exc) == "rating must be between 1 and 5":
            detail = str(exc)
        raise HTTPException(status_code=400, detail=detail)

    return {"success": True, "review_id": review_id, "status": "pending"}


@app.get("/api/products/{product_id}/reviews")
def get_product_reviews(
    product_id: int, page: int = 1, limit: int = 20, with_meta: bool = False
):
    product = products_service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    reviews = reviews_service.get_reviews_for_product(product_id, page=page, limit=limit)
    if with_meta:
        return {"items": reviews, "page": page, "limit": limit}
    return reviews


@app.get("/api/products/{product_id}/rating")
def get_product_rating(product_id: int):
    product = products_service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return reviews_service.get_rating_summary(product_id)


@app.post("/api/reviews/{review_id}/photos")
def upload_review_photo(review_id: int, request: Request, file: list[UploadFile] = File(...)):
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

    review = reviews_service.get_review_by_id(review_id)
    if not review or review.is_deleted:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.user_id != user.telegram_id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    ensure_media_dirs()
    try:
        photos = reviews_service.add_review_photo(review_id, file, MEDIA_ROOT)
    except ValueError as exc:  # pragma: no cover - defensive
        detail = str(exc)
        if detail == "review_not_found":
            raise HTTPException(status_code=404, detail="Review not found")
        raise HTTPException(status_code=400, detail=detail)

    return {"ok": True, "photos": photos}


@app.get("/api/cart")
def api_cart(user_id: int):
    """Вернуть содержимое корзины пользователя и сумму заказа."""
    return _build_cart_response(user_id)


@app.post("/api/cart/apply-promocode")
def api_cart_apply_promocode(payload: CartPromocodeApplyPayload):
    if payload.user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")

    cart_data = _build_cart_response(payload.user_id)
    items = cart_data.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    result = promocodes_service.validate_promocode(payload.code, payload.user_id, items)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid promocode")

    return {
        "code": result.get("code"),
        "discount_amount": result.get("discount_amount", 0),
        "final_total": result.get("final_total", cart_data.get("total", 0)),
        "scope": result.get("scope"),
        "target_id": result.get("target_id"),
        "eligible_items": result.get("eligible_items", []),
        "cart_total": cart_data.get("total", 0),
        "used_count": result.get("used_count"),
        "max_uses": result.get("max_uses"),
        "one_per_user": result.get("one_per_user"),
    }


@app.post("/api/checkout")
def api_checkout(payload: CheckoutPayload):
    """Оформить заказ из текущей корзины WebApp."""
    if payload.user_id is None or not users_service.get_user_by_telegram_id(int(payload.user_id)):
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    cart_data = _build_cart_response(payload.user_id)
    normalized_items = cart_data.get("items") or []
    removed_items = cart_data.get("removed_items") or []
    total = int(cart_data.get("total") or 0)

    if not normalized_items:
        cart_service.clear_cart(payload.user_id)
        raise HTTPException(status_code=400, detail="No valid items in cart")

    user_name = payload.user_name or "webapp"

    promo_result = None
    if payload.promocode:
        promo_result = promocodes_service.validate_promocode(
            payload.promocode, payload.user_id, normalized_items
        )
        if not promo_result:
            raise HTTPException(status_code=400, detail="Invalid promocode")

    discount_amount = int(promo_result.get("discount_amount", 0)) if promo_result else 0
    final_total = int(promo_result.get("final_total", total)) if promo_result else total

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
    cart_items: list[dict[str, Any]] = []
    if payload.items:
        for item in payload.items:
            product_type = _validate_type(item.type)
            qty = max(int(item.qty or 0), 0)
            if qty <= 0:
                continue
            product = _product_by_type(product_type, int(item.product_id))
            if not product:
                continue
            cart_items.append(
                {
                    "product_id": int(item.product_id),
                    "type": product_type,
                    "qty": qty,
                    "price": int(product.get("price") or item.price or 0),
                    "category_id": product.get("category_id"),
                }
            )
    else:
        cart_data = _build_cart_response(payload.telegram_id)
        cart_items = cart_data.get("items") or []

    result = promocodes_service.validate_promocode(payload.code, payload.telegram_id, cart_items)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid promocode")

    cart_total = sum(int(item.get("price", 0)) * int(item.get("qty", 0)) for item in cart_items)

    return {
        "code": result["code"],
        "discount_type": result["discount_type"],
        "discount_value": result["discount_value"],
        "discount_amount": result["discount_amount"],
        "final_total": result["final_total"],
        "scope": result.get("scope"),
        "target_id": result.get("target_id"),
        "eligible_items": result.get("eligible_items", []),
        "total": cart_total,
    }


@app.get("/")
def healthcheck():
    return {"ok": True}


# ----------------------------
# Admin uploads
# ----------------------------


@app.post("/api/admin/upload-image")
def admin_upload_image(
    kind: AdminImageKind = Form(...),
    file: UploadFile = File(...),
    admin_user=Depends(get_admin_user),
):
    """
    Загрузка изображения для товара/курса из админки.
    Сохраняет файл в файловой системе и возвращает URL, который потом пишется в image_url.
    """
    base_folder_by_kind = {
        AdminImageKind.product: "products",
        AdminImageKind.course: "courses",
        AdminImageKind.home: "home",
    }
    base_folder = base_folder_by_kind.get(kind, "products")
    url = _save_uploaded_image(file, base_folder)

    return {"ok": True, "url": url}


@app.get("/api/admin/products/{product_id}/images")
def admin_product_images(product_id: int, user_id: int):
    _ensure_admin(user_id)
    try:
        images = products_service.list_product_images(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"items": images}


@app.post("/api/admin/products/{product_id}/images")
def admin_upload_product_images(
    product_id: int,
    files: list[UploadFile] = File(...),
    admin_user=Depends(get_admin_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов для загрузки")

    urls = [_save_uploaded_image(file, "products") for file in files]
    try:
        images = products_service.add_product_images(product_id, urls)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"items": images}


@app.delete("/api/admin/products/images/{image_id}")
def admin_delete_product_image(image_id: int, user_id: int):
    _ensure_admin(user_id)
    image_url = products_service.delete_product_image(image_id)
    if not image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    _delete_media_file(image_url)
    return {"ok": True}


@app.get("/api/admin/masterclasses/{masterclass_id}/images")
def admin_masterclass_images(masterclass_id: int, user_id: int):
    _ensure_admin(user_id)
    try:
        images = products_service.list_masterclass_images(masterclass_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return {"items": images}


@app.post("/api/admin/masterclasses/{masterclass_id}/images")
def admin_upload_masterclass_images(
    masterclass_id: int,
    files: list[UploadFile] = File(...),
    admin_user=Depends(get_admin_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов для загрузки")

    urls = [_save_uploaded_image(file, "courses") for file in files]
    try:
        images = products_service.add_masterclass_images(masterclass_id, urls)
    except ValueError:
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return {"items": images}


@app.delete("/api/admin/masterclasses/images/{image_id}")
def admin_delete_masterclass_image(image_id: int, user_id: int):
    _ensure_admin(user_id)
    image_url = products_service.delete_masterclass_image(image_id)
    if not image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    _delete_media_file(image_url)
    return {"ok": True}


@app.get("/api/admin/reviews")
def admin_reviews(
    status: str | None = None,
    product_id: int | None = None,
    user_id: int | None = None,
    page: int = 1,
    limit: int = 50,
    admin_user=Depends(get_admin_user),
):
    reviews = reviews_service.admin_list_reviews(
        status=status, product_id=product_id, user_id=user_id, page=page, limit=limit
    )
    return {"items": reviews, "page": page, "limit": limit}


@app.post("/api/admin/reviews/{review_id}/status")
def admin_update_review_status(
    review_id: int, payload: ReviewStatusUpdatePayload, admin_user=Depends(get_admin_user)
):
    try:
        review = reviews_service.admin_update_review_status(
            review_id, new_status=payload.status, is_deleted=payload.is_deleted
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return {"ok": True, "status": review.status, "is_deleted": review.is_deleted}


@app.get("/api/admin/faq")
def admin_faq_list(user_id: int, category: str | None = None):
    _ensure_admin(user_id)
    items = faq_service.get_faq_list(category)
    return {"items": [_faq_to_dict(item) for item in items]}


@app.post("/api/admin/faq")
def admin_create_faq(payload: FaqCreatePayload, user_id: int):
    _ensure_admin(user_id)
    item = faq_service.create_faq_item(payload.dict())
    return _faq_to_dict(item)


@app.put("/api/admin/faq/{faq_id}")
def admin_update_faq(faq_id: int, payload: FaqUpdatePayload, user_id: int):
    _ensure_admin(user_id)
    data = {key: value for key, value in payload.dict().items() if value is not None}
    item = faq_service.update_faq_item(faq_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return _faq_to_dict(item)


@app.delete("/api/admin/faq/{faq_id}")
def admin_delete_faq(faq_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = faq_service.delete_faq_item(faq_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"ok": True}


@app.get("/api/admin/home/banners")
def admin_home_banners(user_id: int):
    _ensure_admin(user_id)
    items = _wrap_home_banner_error("list", home_service.list_banners)
    return {"items": [item.dict() for item in items]}


@app.post("/api/admin/home/banners")
def admin_create_home_banner(payload: HomeBannerIn, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error("create", lambda: home_service.create_banner(payload))
    return banner.dict()


@app.get("/api/admin/home/banners/{banner_id}")
def admin_get_home_banner(banner_id: int, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error("get", lambda: home_service.get_banner(banner_id))
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    return banner.dict()


@app.put("/api/admin/home/banners/{banner_id}")
def admin_update_home_banner(banner_id: int, payload: HomeBannerIn, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error(
        "update", lambda: home_service.update_banner(banner_id, payload)
    )
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    return banner.dict()


@app.delete("/api/admin/home/banners/{banner_id}")
def admin_delete_home_banner(banner_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = _wrap_home_banner_error("delete", lambda: home_service.delete_banner(banner_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Banner not found")
    return {"ok": True}


@app.get("/api/admin/home/sections")
def admin_home_sections(user_id: int):
    _ensure_admin(user_id)
    items = home_service.list_sections()
    return {"items": [item.dict() for item in items]}


@app.post("/api/admin/home/sections")
def admin_create_home_section(payload: HomeSectionIn, user_id: int):
    _ensure_admin(user_id)
    section = home_service.create_section(payload)
    return section.dict()


@app.get("/api/admin/home/sections/{section_id}")
def admin_get_home_section(section_id: int, user_id: int):
    _ensure_admin(user_id)
    section = home_service.get_section(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section.dict()


@app.put("/api/admin/home/sections/{section_id}")
def admin_update_home_section(section_id: int, payload: HomeSectionIn, user_id: int):
    _ensure_admin(user_id)
    section = home_service.update_section(section_id, payload)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section.dict()


@app.delete("/api/admin/home/sections/{section_id}")
def admin_delete_home_section(section_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = home_service.delete_section(section_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Section not found")
    return {"ok": True}


@app.get("/api/admin/home/posts")
def admin_home_posts(user_id: int):
    _ensure_admin(user_id)
    items = home_service.list_posts()
    return {"items": [item.dict() for item in items]}


@app.post("/api/admin/home/posts")
def admin_create_home_post(payload: HomePostIn, user_id: int):
    _ensure_admin(user_id)
    post = home_service.create_post(payload)
    return post.dict()


@app.get("/api/admin/home/posts/{post_id}")
def admin_get_home_post(post_id: int, user_id: int):
    _ensure_admin(user_id)
    post = home_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.dict()


@app.put("/api/admin/home/posts/{post_id}")
def admin_update_home_post(post_id: int, payload: HomePostIn, user_id: int):
    _ensure_admin(user_id)
    post = home_service.update_post(post_id, payload)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.dict()


@app.delete("/api/admin/home/posts/{post_id}")
def admin_delete_home_post(post_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = home_service.delete_post(post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
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
        payload.short_description or None,
        payload.description or "",
        payload.detail_url,
        payload.category_id,
        image=payload.image,
        image_url=payload.image_url,
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
        payload.short_description or None,
        payload.description or "",
        payload.detail_url,
        payload.category_id,
        payload.is_active,
        image=payload.image,
        image_url=payload.image_url,
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
    product_type = _validate_type(payload.type)
    changed = products_service.toggle_product_active(product_id, product_type)
    if not changed:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.get("/api/admin/product-categories")
def admin_product_categories(user_id: int, type: str = "basket"):
    _ensure_admin(user_id)
    product_type = _validate_type(type)
    items = products_service.list_product_categories_admin(product_type)
    return {"items": items}


@app.post("/api/admin/product-categories")
def admin_create_product_category(payload: AdminProductCategoryPayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    new_id = products_service.create_product_category(
        payload.name,
        slug=payload.slug,
        sort_order=payload.sort_order,
        is_active=payload.is_active if payload.is_active is not None else True,
        product_type=product_type,
    )
    return {"id": new_id}


@app.put("/api/admin/product-categories/{category_id}")
def admin_update_product_category(category_id: int, payload: AdminProductCategoryUpdatePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type) if payload.type else None
    updated = products_service.update_product_category(
        category_id,
        name=payload.name,
        slug=payload.slug,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        product_type=product_type,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")
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
    try:
        update_data = payload.dict()
        update_data.pop("user_id", None)
        updated = promocodes_service.update_promocode(promocode_id, update_data)
    except ValueError as exc:  # noqa: WPS440
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return updated


@app.delete("/api/admin/promocodes/{promocode_id}")
def admin_delete_promocode(promocode_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = promocodes_service.delete_promocode(promocode_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return {"ok": True}

