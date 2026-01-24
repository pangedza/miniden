"""Публичные роуты FastAPI (каталог, корзина, webapp)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode
import urllib.request
from uuid import uuid4

from fastapi import (
    APIRouter,
    Body,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import get_settings
from database import get_session
from media_paths import (
    MEDIA_ROOT,
    ensure_media_dirs,
)
from models import BotEventTrigger, BotButtonPreset, CheckoutOrder, User
from models.support import WebChatMessagesResponse
from services import automations as automations_service
from services import branding as branding_service
from services import cart as cart_service
from services import favorites as favorites_service
from services import faq_service
from services import home as home_service
from services import menu_catalog
from services import orders as orders_service
from services import products as products_service
from services import promocodes as promocodes_service
from services import reviews as reviews_service
from services import user_admin as user_admin_service
from services import user_stats as user_stats_service
from services import users as users_service
from services import webchat_service
from services.telegram_webapp_auth import (
    get_telegram_init_data_from_request,
    validate_telegram_webapp_init_data,
)
from utils import site_chat_storage
from utils.jwt_auth import decode_access_token
from utils.texts import format_order_for_admin

router = APIRouter()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"
STATIC_DIR_PUBLIC = BASE_DIR / "static"

SETTINGS = get_settings()
BOT_TOKEN = SETTINGS.bot_token
COOKIE_MAX_AGE = 30 * 24 * 60 * 60
CART_SESSION_COOKIE = "cart_session_id"
ALLOWED_TYPES = set(menu_catalog.MENU_ITEM_TYPES) | {"basket"}
ALLOWED_CATEGORY_TYPES = {"basket", "course", "mixed"}


class VersionInfo(BaseModel):
    commit: str
    build_time: str
    service_name: str


def _detect_git_commit() -> str:
    env_commit = os.getenv("BUILD_COMMIT")
    if env_commit:
        return env_commit

    repo_dir = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "unknown"
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to detect git commit")
        return "unknown"


BUILD_COMMIT = _detect_git_commit()
BUILD_TIME = os.getenv("BUILD_TIME") or datetime.utcnow().isoformat() + "Z"
SERVICE_NAME = os.getenv("SERVICE_NAME", "miniden-webapi")


class WebChatStartPayload(BaseModel):
    session_key: str | None = None
    page: str | None = None
    referrer: str | None = None
    user_identifier: str | None = None

    class Config:
        extra = "ignore"


class WebChatMessagePayload(BaseModel):
    session_key: str | None = None
    text: str | None = None
    user_identifier: str | None = None

    class Config:
        extra = "ignore"


class WebChatManagerReplyPayload(BaseModel):
    session_id: int | None = None
    session_key: str | None = None
    text: str | None = None
    message: str | None = None
    reply: str | None = None


class CartItemPayload(BaseModel):
    user_id: int | None = None
    product_id: int
    qty: int | None = 1
    type: str = "basket"


class CartClearPayload(BaseModel):
    user_id: int | None = None


class CheckoutPayload(BaseModel):
    user_id: int
    user_name: str | None = Field(None, description="Имя пользователя из Telegram")
    customer_name: str = Field(..., description="Имя клиента", max_length=100)
    contact: str = Field(..., description="Способ связи", max_length=100)
    comment: str | None = Field(None, max_length=500)
    promocode: str | None = None


class WebappCheckoutItem(BaseModel):
    item_id: int
    title: str
    qty: int
    price: int
    type: str
    category_slug: str | None = None


class WebappCheckoutTotals(BaseModel):
    qty_total: int
    sum_total: int
    currency: str = "₽"


class WebappCheckoutContext(BaseModel):
    page_url: str | None = None
    order_link: str | None = None
    user_agent: str | None = None
    created_at: str | None = None


class WebappCheckoutPayload(BaseModel):
    tg_user_id: int
    items: list[WebappCheckoutItem]
    totals: WebappCheckoutTotals
    client_context: WebappCheckoutContext | None = None


class WebappOrderItem(BaseModel):
    id: int
    title: str
    qty: int
    price: int


class WebappOrderCart(BaseModel):
    items: list[WebappOrderItem]
    total: int
    currency: str = "₽"


class WebappOrderPayload(BaseModel):
    tg_user_id: int
    cart: WebappOrderCart
    init_data: str | None = None


class ProfileUpdatePayload(BaseModel):
    full_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=100)


class AvatarUpdatePayload(BaseModel):
    avatar_url: str


class ContactPayload(BaseModel):
    telegram_id: int
    phone: str | None = Field(None, max_length=100)


class FavoriteTogglePayload(BaseModel):
    telegram_id: int
    product_id: int
    type: str


class ReviewCreatePayload(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    text: str
    photos: list[str] | None = None
    order_id: int | None = None


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
    user_id: int | None = None
    code: str


def _serve_webapp_index() -> FileResponse:
    return FileResponse(WEBAPP_DIR / "index.html", media_type="text/html")


def _send_message_to_admins(
    text: str, reply_markup: dict[str, Any] | None = None
) -> list[int]:
    admin_ids = list(getattr(SETTINGS, "admin_ids", set()) or [])
    primary_admin = getattr(SETTINGS, "admin_chat_id", None)
    if primary_admin and primary_admin not in admin_ids:
        admin_ids.append(primary_admin)

    if not BOT_TOKEN or not admin_ids:
        return []

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    message_ids: list[int] = []

    for chat_id in admin_ids:
        payload_data: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload_data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        payload = urlencode(payload_data).encode()
        try:
            with urllib.request.urlopen(api_url, data=payload, timeout=10) as response:
                data = json.load(response)
        except Exception:
            logger.exception("Failed to notify admin via Telegram")
            continue

        if data.get("ok"):
            try:
                message_id = int(data["result"]["message_id"])
                message_ids.append(message_id)
            except Exception:
                continue
    return message_ids


def _send_bot_message(chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> bool:
    if not BOT_TOKEN:
        return False

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

    try:
        data = urlencode(payload).encode()
        with urllib.request.urlopen(api_url, data=data, timeout=10) as response:
            result = json.load(response)
    except Exception:
        logger.exception("Failed to send bot message to user %s", chat_id)
        return False

    return bool(result.get("ok"))


def _format_checkout_items(items: list[dict[str, Any]], currency: str) -> str:
    lines = []
    for index, item in enumerate(items, start=1):
        title = item.get("title") or "Позиция"
        qty = int(item.get("qty") or 0)
        price = int(item.get("price") or 0)
        line_total = price * qty
        lines.append(f"{index}) {title} x{qty} — {line_total} {currency}")
    return "\n".join(lines) if lines else "—"


def _build_event_keyboard(buttons: list[dict[str, Any]], *, webapp_url: str) -> dict[str, Any] | None:
    if not buttons:
        return None

    rows: dict[int, list[dict[str, str]]] = {}
    for button in buttons:
        title = str(button.get("title") or "").strip()
        if not title:
            continue
        button_type = (button.get("type") or "").strip().lower()
        value = str(button.get("value") or "").strip()
        value = value.replace("{webapp_url}", webapp_url)
        if not value:
            continue
        row_index = int(button.get("row") or 0)
        payload: dict[str, str]
        if button_type == "url":
            payload = {"text": title, "url": value}
        else:
            payload = {"text": title, "callback_data": value}
        rows.setdefault(row_index, []).append(payload)

    if not rows:
        return None

    inline_keyboard = [rows[row] for row in sorted(rows.keys()) if rows[row]]
    if not inline_keyboard:
        return None
    return {"inline_keyboard": inline_keyboard}


def _resolve_webapp_url(request: Request) -> str:
    settings = get_settings()
    if settings.webapp_index_url:
        return settings.webapp_index_url
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/"


def _automation_conditions_match(conditions: list[dict[str, Any]] | None) -> bool:
    if not conditions:
        return True
    for condition in conditions:
        cond_type = str(condition.get("type") or "").lower()
        if cond_type == "source":
            value = str(condition.get("value") or "").lower()
            if value not in {"webapp", "web_app"}:
                return False
    return True


def _build_webapp_automation_context(
    *,
    tg_user_id: int,
    items: list[dict[str, Any]],
    totals: dict[str, Any],
    order_id: int,
    saved_order_id: int | None = None,
) -> dict[str, Any]:
    user = users_service.get_user_by_telegram_id(tg_user_id)
    user_name = (
        user.first_name if user and user.first_name else user.username if user else None
    ) or "Пользователь"
    phone = user.phone if user and user.phone else ""
    total_amount = int(totals.get("sum_total") or 0)
    currency = totals.get("currency") or "₽"
    items_text = automations_service.build_items_text(
        items, currency, ["title", "qty", "price", "sum"]
    )
    return {
        "order_id": order_id,
        "saved_order_id": saved_order_id,
        "total": total_amount,
        "items": items_text,
        "user_name": user_name,
        "user_id": tg_user_id,
        "phone": phone,
        "comment": "",
    }


def _apply_webapp_automation_rules(
    *,
    request: Request,
    tg_user_id: int,
    items: list[dict[str, Any]],
    totals: dict[str, Any],
    order_id: int,
    saved_order_id: int | None = None,
) -> dict[str, bool]:
    currency = totals.get("currency") or "₽"
    webapp_url = _resolve_webapp_url(request)
    context = _build_webapp_automation_context(
        tg_user_id=tg_user_id,
        items=items,
        totals=totals,
        order_id=order_id,
        saved_order_id=saved_order_id,
    )

    with get_session() as session:
        rules = automations_service.list_active_rules(
            session, trigger_type=automations_service.TRIGGER_WEBAPP_ORDER
        )
        presets = automations_service.list_active_presets(session)

    if not rules:
        return {"any": False, "user_sent": False, "admin_sent": False}

    presets_map = {int(preset.id): preset for preset in presets}
    any_executed = False
    user_sent = False
    admin_sent = False

    for rule in rules:
        if not _automation_conditions_match(rule.conditions_json or []):
            continue
        attached_presets: dict[str, BotButtonPreset | None] = {"user": None, "admin": None}
        for action in rule.actions_json or []:
            action_type = str(action.get("type") or "").upper()
            if action_type == automations_service.ACTION_SAVE_ORDER:
                if context.get("saved_order_id"):
                    any_executed = True
                    continue
                user = users_service.get_user_by_telegram_id(tg_user_id)
                user_name = (
                    user.first_name if user and user.first_name else user.username if user else None
                ) or "webapp"
                customer_name = (user.first_name if user else None) or user_name
                contact = user.phone if user and user.phone else ""
                order_items = [
                    {
                        "product_id": int(item.get("item_id") or item.get("product_id") or 0),
                        "name": item.get("title"),
                        "price": int(item.get("price") or 0),
                        "qty": int(item.get("qty") or 0),
                        "type": item.get("type") or "basket",
                    }
                    for item in items
                ]
                order_text = format_order_for_admin(
                    user_id=tg_user_id,
                    user_name=user_name,
                    items=order_items,
                    total=int(totals.get("sum_total") or 0),
                    customer_name=customer_name,
                    contact=contact,
                    comment="",
                )
                saved_order_id = orders_service.add_order(
                    user_id=tg_user_id,
                    user_name=user_name,
                    items=order_items,
                    total=int(totals.get("sum_total") or 0),
                    customer_name=customer_name,
                    contact=contact,
                    comment="",
                    order_text=order_text,
                )
                context["order_id"] = saved_order_id
                context["saved_order_id"] = saved_order_id
                any_executed = True
                continue

            if action_type == automations_service.ACTION_ATTACH_BUTTONS:
                target = str(action.get("target") or "").lower()
                try:
                    preset_id = int(action.get("preset_id") or 0)
                except (TypeError, ValueError):
                    preset_id = 0
                preset = presets_map.get(preset_id)
                if preset and target in attached_presets:
                    attached_presets[target] = preset
                    any_executed = True
                continue

            if action_type in {
                automations_service.ACTION_SEND_USER_MESSAGE,
                automations_service.ACTION_SEND_ADMIN_MESSAGE,
            }:
                text = automations_service.render_message(
                    action.get("template"),
                    context=context,
                    items=items,
                    currency=currency,
                )
                if not text:
                    continue
                target_scope = "user" if action_type == automations_service.ACTION_SEND_USER_MESSAGE else "admin"
                preset = attached_presets.get(target_scope)
                reply_markup = automations_service.build_keyboard_from_buttons(
                    preset.buttons_json if preset else None,
                    webapp_url=webapp_url,
                    context=context,
                )
                if target_scope == "user":
                    _send_bot_message(tg_user_id, text, reply_markup=reply_markup)
                    user_sent = True
                else:
                    _send_message_to_admins(text, reply_markup=reply_markup)
                    admin_sent = True
                any_executed = True
                continue

    return {"any": any_executed, "user_sent": user_sent, "admin_sent": admin_sent}


def _dispatch_webapp_checkout_created(
    *,
    request: Request,
    tg_user_id: int,
    items: list[dict[str, Any]],
    totals: dict[str, Any],
    order_id: int,
    saved_order_id: int | None = None,
    client_context: dict[str, Any] | None = None,
) -> None:
    automation_result = _apply_webapp_automation_rules(
        request=request,
        tg_user_id=tg_user_id,
        items=items,
        totals=totals,
        order_id=order_id,
        saved_order_id=saved_order_id,
    )

    webapp_url = _resolve_webapp_url(request)
    with get_session() as session:
        trigger = (
            session.query(BotEventTrigger)
            .filter(BotEventTrigger.event_code == "webapp_checkout_created")
            .filter(BotEventTrigger.is_enabled.is_(True))
            .first()
        )

    qty_total = int(totals.get("qty_total") or 0)
    sum_total = int(totals.get("sum_total") or 0)
    currency = totals.get("currency") or "₽"
    items_text = _format_checkout_items(items, currency)
    raw_order_link = ""
    if isinstance(client_context, dict):
        raw_order_link = str(
            client_context.get("order_link") or client_context.get("page_url") or ""
        ).strip()
    order_link = f"Ссылка на заказ: {raw_order_link}" if raw_order_link else ""

    if not automation_result["user_sent"]:
        if trigger:
            template = trigger.message_template or ""
            text = template.format(
                items=items_text,
                qty_total=qty_total,
                sum_total=sum_total,
                total=sum_total,
                currency=currency,
                order_id=order_id,
                webapp_url=webapp_url,
                order_link=order_link,
            )
            keyboard = _build_event_keyboard(trigger.buttons_json or [], webapp_url=webapp_url)
        else:
            text = (
                "🛒 Новый заказ из витрины\n"
                f"Вы выбрали:\n{items_text}\n"
                f"Итого: {qty_total} шт, {sum_total} {currency}"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Связаться", "callback_data": "trigger:contact_manager"}],
                    [{"text": "Открыть витрину", "url": webapp_url}],
                ]
            }

        _send_bot_message(tg_user_id, text, reply_markup=keyboard)

    if not automation_result["admin_sent"]:
        admin_text = (
            "📦 Новый заказ из WebApp\n"
            f"Заказ #{order_id}\n"
            f"{items_text}\n"
            f"Итого: {sum_total} {currency}"
        )
        _send_message_to_admins(admin_text)


def _notify_admin_about_chat(chat_session, preview_text: str) -> list[int]:
    snippet = (preview_text or "")[:200]
    text = (
        f"Новый чат с сайта #{chat_session.id}\n"
        f"Текст: {snippet}\n"
        "Чтобы ответить — ответьте на это сообщение."
    )
    message_ids = _send_message_to_admins(text)
    for message_id in message_ids:
        try:
            site_chat_storage.remember_admin_message(message_id, int(chat_session.id))
        except Exception:
            logger.exception("Failed to persist mapping for admin notification")
    return message_ids




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


def _get_cart_user_id_from_cookie(request: Request) -> int | None:
    user_id = request.cookies.get("tg_user_id")
    if not user_id:
        return None
    try:
        return int(user_id)
    except ValueError:
        return None


def _get_cart_user_id_from_authorization(request: Request) -> int | None:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        payload = decode_access_token(token.strip())
    except HTTPException:
        return None

    telegram_id_raw = payload.get("telegram_id")
    try:
        return int(telegram_id_raw)
    except (TypeError, ValueError):
        return None


def _ensure_cart_session_id(request: Request, response: Response) -> str:
    session_id = request.cookies.get(CART_SESSION_COOKIE)
    if session_id:
        return session_id
    session_id = uuid4().hex
    response.set_cookie(
        key=CART_SESSION_COOKIE,
        value=session_id,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
    )
    return session_id


def _resolve_cart_identity(
    request: Request,
    response: Response,
    user_id: int | None = None,
) -> tuple[int | None, str | None]:
    auth_user_id = _get_cart_user_id_from_authorization(request)
    if auth_user_id is not None:
        return auth_user_id, None

    if user_id is not None:
        return int(user_id), None

    cookie_user_id = _get_cart_user_id_from_cookie(request)
    if cookie_user_id is not None:
        return cookie_user_id, None

    session_id = _ensure_cart_session_id(request, response)
    return None, session_id


def _product_by_type(product_type: str, product_id: int, *, include_inactive: bool = False):
    resolved_type = menu_catalog.map_legacy_item_type(product_type) or "product"
    return menu_catalog.get_item_by_id(
        product_id, include_inactive=include_inactive, item_type=resolved_type
    )


def _build_cart_response(
    *,
    user_id: int | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    items, removed_ids = cart_service.get_cart_items(user_id, session_id=session_id)

    normalized_items: list[dict[str, Any]] = []
    removed_items: list[dict[str, Any]] = []
    total = 0

    for item in items:
        product_type = item.get("type") or "product"
        if product_type not in ALLOWED_TYPES:
            removed_items.append({"product_id": item.get("product_id"), "type": product_type, "reason": "invalid"})
            cart_service.remove_from_cart(
                user_id,
                int(item.get("product_id") or 0),
                product_type,
                session_id=session_id,
            )
            continue
        try:
            product_id = int(item.get("product_id"))
        except (TypeError, ValueError):
            removed_items.append({"product_id": None, "type": product_type, "reason": "invalid"})
            continue

        product_info = _product_by_type(product_type, product_id)
        if not product_info:
            removed_items.append({"product_id": product_id, "type": product_type, "reason": "inactive"})
            cart_service.remove_from_cart(
                user_id,
                product_id,
                product_type,
                session_id=session_id,
            )
            continue

        qty = max(int(item.get("qty") or 0), 0)
        if qty <= 0:
            cart_service.remove_from_cart(
                user_id,
                product_id,
                product_type,
                session_id=session_id,
            )
            continue

        price = int(product_info.get("price") or 0)
        subtotal = price * qty
        total += subtotal

        normalized_items.append(
            {
                "product_id": product_id,
                "type": menu_catalog.map_legacy_item_type(product_type) or product_type,
                "name": product_info.get("title") or product_info.get("name"),
                "price": price,
                "qty": qty,
                "subtotal": subtotal,
                "category_id": product_info.get("category_id"),
                "category_slug": product_info.get("category_slug"),
            }
        )

    for removed_id in removed_ids:
        product_info = menu_catalog.get_item_by_id(
            removed_id, include_inactive=True, item_type=None
        )
        removed_items.append(
            {
                "product_id": removed_id,
                "type": product_info.get("type") if product_info else "unknown",
                "reason": "inactive" if product_info else "not_found",
            }
        )

    return {"items": normalized_items, "removed_items": removed_items, "total": total}


def _validate_type(product_type: str) -> str:
    if product_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail="type must be 'basket' or 'course'")
    return product_type


def _validate_category_type(product_type: str) -> str:
    if product_type not in ALLOWED_CATEGORY_TYPES:
        raise HTTPException(status_code=422, detail="type must be 'basket', 'course' or 'mixed'")
    return product_type


def _faq_to_dict(item) -> dict:
    return {
        "id": int(item.id),
        "category": item.category,
        "question": item.question,
        "answer": item.answer,
        "sort_order": int(item.sort_order or 0),
    }


@router.get("/api/version", response_model=VersionInfo)
def version() -> VersionInfo:
    return VersionInfo(
        commit=BUILD_COMMIT,
        build_time=BUILD_TIME,
        service_name=SERVICE_NAME,
    )


@router.get("/api/env")
def api_env():
    settings = get_settings()
    bot_username = settings.bot_username.lstrip("@") if hasattr(settings, "bot_username") else ""
    return {
        "bot_link": f"https://t.me/{bot_username}",
        "channel_link": settings.required_channel_link,
    }


@router.get("/api/branding")
def api_get_branding():
    with get_session() as session:
        branding = branding_service.get_or_create_branding(session)
        return branding_service.serialize_branding(branding)


@router.get("/api/home")
def api_home():
    return home_service.get_active_home_data()


@router.get("/api/homepage/blocks")
def api_homepage_blocks():
    try:
        blocks = home_service.list_blocks(include_inactive=False)
    except Exception as exc:  # noqa: WPS430
        logger.exception("Failed to load homepage blocks")
        return {"items": [], "error": str(exc)}
    return {"items": [block.dict() for block in blocks]}


@router.get("/api/health")
def api_health():
    return {"ok": True}


@router.get("/api/faq")
def api_faq(category: str | None = None):
    items = faq_service.get_faq_list(category)
    return [_faq_to_dict(item) for item in items]


@router.get("/api/faq/{faq_id}")
def api_faq_detail(faq_id: int):
    item = faq_service.get_faq_item(faq_id)
    if not item:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return _faq_to_dict(item)


@router.post("/api/webchat/start")
async def api_webchat_start(
    request: Request, payload: WebChatStartPayload = Body(default=WebChatStartPayload())
):
    """
    Старт/инициализация сессии веб-чата.
    Ожидается JSON:
    {
      "session_key": "строка",
      "page": "опционально, строка"
    }
    """
    session_key = payload.session_key
    page = payload.page
    user_identifier = payload.user_identifier
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request and request.client else None

    if not session_key:
        raise HTTPException(status_code=400, detail="session_key is required")

    logger.info(
        "webchat_start: session_key=%s page=%s user_identifier=%s",
        session_key,
        page,
        user_identifier,
    )

    session = webchat_service.get_session_by_key(session_key)
    created = False
    if not session:
        session = webchat_service.get_or_create_session(
            session_key,
            user_identifier=user_identifier,
            user_agent=user_agent,
            client_ip=client_ip,
        )
        created = True
    else:
        webchat_service.get_or_create_session(
            session_key,
            user_identifier=user_identifier,
            user_agent=user_agent,
            client_ip=client_ip,
        )

    if created:
        try:
            webchat_service.add_system_message(session, "Чат начат")
        except Exception:
            logger.exception("Failed to add system message for webchat start")

    return {
        "ok": True,
        "session_id": int(session.id),
        "session_key": session.session_key,
        "status": session.status,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.post("/api/webchat/message")
async def api_webchat_message(
    request: Request, payload: WebChatMessagePayload = Body(default=WebChatMessagePayload())
):
    """
    Приём сообщения пользователя из веб-чата.
    Ожидается JSON:
    {
      "session_key": "строка",
      "text": "строка"
    }
    """
    session_key = payload.session_key
    text = payload.text
    user_identifier = payload.user_identifier
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request and request.client else None

    if not session_key:
        raise HTTPException(status_code=400, detail="session_key is required")
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    logger.info(
        "webchat_message: session_key=%s text_len=%s user_identifier=%s",
        session_key,
        len(text or ""),
        user_identifier,
    )

    session = webchat_service.get_or_create_session(
        session_key,
        user_identifier=user_identifier,
        user_agent=user_agent,
        client_ip=client_ip,
    )

    message = webchat_service.add_user_message(session, text)

    current_session = webchat_service.get_session_by_key(session_key) or session
    if current_session.status == "open":
        webchat_service.mark_waiting_manager(current_session)

    current_session = webchat_service.get_session_by_key(session_key) or current_session
    if (
        current_session.status == "waiting_manager"
        and not current_session.telegram_thread_message_id
    ):
        message_ids = _notify_admin_about_chat(current_session, text)
        if message_ids:
            webchat_service.set_thread_message_id(current_session, message_ids[0])

    return {"ok": True, "message_id": int(message.id), "text": text}


@router.get("/api/webchat/messages", response_model=WebChatMessagesResponse)
def api_webchat_messages(
    session_key: str, limit: Optional[int] = None, after_id: int = 0
):
    session = webchat_service.get_session_by_key(session_key)
    if not session:
        return {"ok": True, "status": "open", "messages": []}

    messages = webchat_service.get_messages(
        session, limit=limit, after_id=after_id, mark_read_for="client"
    )

    payload_messages = []
    for msg in messages:
        payload_messages.append(
            {
                "id": msg.id,
                "sender": msg.sender,
                "text": msg.text,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "is_read_by_manager": msg.is_read_by_manager,
                "is_read_by_client": msg.is_read_by_client,
            }
        )

    return {
        "ok": True,
        "status": session.status,
        "messages": payload_messages,
    }


async def _handle_manager_reply(
    session_id: int | str | None, text: str, session_key: str | None = None
):
    session = None
    if session_id is not None:
        try:
            session = webchat_service.get_session_by_id(int(session_id))
        except Exception:
            session = None
    if not session and session_key:
        session = webchat_service.get_session_by_key(session_key)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.add_manager_message(session, text)

    if session.status == "waiting_manager":
        webchat_service.mark_open(session)

    return {"ok": True}


@router.post("/api/webchat/manager_reply")
async def api_webchat_manager_reply(
    payload: WebChatManagerReplyPayload = Body(default=WebChatManagerReplyPayload()),
    session_id: int | None = Query(default=None),
    text: str | None = Query(default=None),
):
    sid = payload.session_id if payload.session_id is not None else session_id
    session_key = payload.session_key
    reply_text = payload.text or payload.message or payload.reply or text

    if sid is None and not session_key:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not reply_text:
        raise HTTPException(status_code=400, detail="text is required")

    logger.info(
        "manager_reply: session_id=%s session_key=%s text_len=%s",
        sid,
        session_key,
        len(reply_text or ""),
    )
    return await _handle_manager_reply(sid, reply_text, session_key=session_key)


@router.get("/public/site-settings")
def public_site_settings():
    return menu_catalog.get_site_settings()


@router.get("/public/menu")
def public_menu(type: str | None = None):
    try:
        return menu_catalog.build_public_menu(type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/public/menu/tree")
def public_menu_tree(type: str | None = None):
    try:
        return menu_catalog.build_public_menu_tree(type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/public/menu/categories")
def public_menu_categories(type: str | None = None):
    try:
        return {"items": menu_catalog.list_categories(include_inactive=False, category_type=type)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/public/menu/items")
def public_menu_items(category: str | None = None, type: str | None = None):
    try:
        if category:
            if category.isdigit():
                return {
                    "items": menu_catalog.list_items(
                        include_inactive=False,
                        category_id=int(category),
                        category_type=type,
                    )
                }
            category_record = menu_catalog.get_category_by_slug(
                category, include_inactive=False, category_type=type
            )
            if not category_record:
                raise HTTPException(status_code=404, detail="Category not found")
            return {
                "items": menu_catalog.list_items(
                    include_inactive=False,
                    category_id=int(category_record.id),
                    category_type=type,
                )
            }
        return {
            "items": menu_catalog.list_items(include_inactive=False, category_type=type)
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/api/public/site-settings")
def api_public_site_settings():
    return menu_catalog.get_site_settings()


@router.get("/api/public/menu")
def api_public_menu(type: str | None = None):
    try:
        return menu_catalog.build_public_menu(type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/api/public/menu/tree")
def api_public_menu_tree(type: str | None = None):
    try:
        return menu_catalog.build_public_menu_tree(type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/api/public/menu/categories")
def api_public_menu_categories(type: str | None = None):
    try:
        return {"items": menu_catalog.list_categories(include_inactive=False, category_type=type)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/api/public/menu/category/{slug}")
def api_public_menu_category(slug: str, type: str | None = None):
    try:
        category = menu_catalog.get_category_details(
            slug, include_inactive=False, category_type=type
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get("/api/public/menu/items")
def api_public_menu_items(category_slug: str | None = None, type: str | None = None):
    try:
        if category_slug:
            category_record = menu_catalog.get_category_by_slug(
                category_slug, include_inactive=False, category_type=type
            )
            if not category_record:
                raise HTTPException(status_code=404, detail="Category not found")
            return {
                "items": menu_catalog.list_items(
                    include_inactive=False,
                    category_id=int(category_record.id),
                    category_type=type,
                )
            }
        return {"items": menu_catalog.list_items(include_inactive=False, category_type=type)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/api/public/item/{item_id}")
def api_public_item(item_id: int):
    item = menu_catalog.get_item_by_id(item_id, include_inactive=False)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/api/public/blocks")
def api_public_blocks(page: str | None = None):
    return {"items": menu_catalog.list_blocks(include_inactive=False, page=page)}


@router.post("/api/public/checkout/from-webapp")
def api_public_checkout_from_webapp(payload: WebappCheckoutPayload, request: Request):
    init_data = get_telegram_init_data_from_request(request)
    if not init_data:
        raise HTTPException(status_code=401, detail="init_data_missing")

    user_data = validate_telegram_webapp_init_data(init_data, BOT_TOKEN)
    telegram_id = user_data.get("id")
    if telegram_id is None:
        raise HTTPException(status_code=401, detail="invalid_user")

    if int(payload.tg_user_id) != int(telegram_id):
        raise HTTPException(status_code=403, detail="telegram_id_mismatch")

    if payload.tg_user_id <= 0:
        raise HTTPException(status_code=422, detail="tg_user_id is required")
    if not payload.items:
        raise HTTPException(status_code=422, detail="items are required")

    normalized_items: list[dict[str, Any]] = []
    qty_total = 0
    sum_total = 0

    for item in payload.items:
        if item.qty <= 0:
            raise HTTPException(status_code=422, detail="qty must be positive")
        if item.price < 0:
            raise HTTPException(status_code=422, detail="price must be non-negative")
        if not item.title:
            raise HTTPException(status_code=422, detail="title is required")
        item_type = item.type or "basket"
        if item_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=422, detail="unsupported item type")

        qty_total += int(item.qty)
        sum_total += int(item.price) * int(item.qty)
        normalized_items.append(
            {
                "item_id": int(item.item_id),
                "title": item.title,
                "qty": int(item.qty),
                "price": int(item.price),
                "type": item_type,
                "category_slug": item.category_slug,
            }
        )

    if payload.totals.qty_total != qty_total:
        raise HTTPException(status_code=422, detail="qty_total mismatch")
    if payload.totals.sum_total != sum_total:
        raise HTTPException(status_code=422, detail="sum_total mismatch")

    totals_payload = payload.totals.model_dump()
    totals_payload["qty_total"] = qty_total
    totals_payload["sum_total"] = sum_total

    client_context = payload.client_context.model_dump() if payload.client_context else None
    first_name = (user_data.get("first_name") or "").strip()
    last_name = (user_data.get("last_name") or "").strip()
    full_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    username = (user_data.get("username") or "").strip() or None

    with get_session() as session:
        user = users_service.get_or_create_user_from_telegram(
            session,
            telegram_id=int(payload.tg_user_id),
            username=username,
            full_name=full_name,
        )
        contact = user.phone or ""
        user_name = (
            user.first_name if user and user.first_name else username or "Пользователь"
        )
        order = CheckoutOrder(
            tg_user_id=int(payload.tg_user_id),
            status="created",
            items_json=normalized_items,
            totals_json=totals_payload,
            client_context_json=client_context,
        )
        session.add(order)
        session.flush()
        checkout_order_id = int(order.id)
    order_items = [
        {
            "product_id": int(item.get("item_id") or 0),
            "name": item.get("title"),
            "price": int(item.get("price") or 0),
            "qty": int(item.get("qty") or 0),
            "type": item.get("type") or "basket",
        }
        for item in normalized_items
    ]
    order_text = format_order_for_admin(
        user_id=int(payload.tg_user_id),
        user_name=user_name,
        items=order_items,
        total=int(totals_payload.get("sum_total") or 0),
        customer_name=user_name,
        contact=contact,
        comment="",
    )
    saved_order_id = orders_service.add_order(
        user_id=int(payload.tg_user_id),
        user_name=user_name,
        items=order_items,
        total=int(totals_payload.get("sum_total") or 0),
        customer_name=user_name,
        contact=contact,
        comment="",
        order_text=order_text,
    )

    _dispatch_webapp_checkout_created(
        request=request,
        tg_user_id=int(payload.tg_user_id),
        items=normalized_items,
        totals=totals_payload,
        order_id=saved_order_id,
        saved_order_id=saved_order_id,
        client_context=client_context,
    )

    return {
        "ok": True,
        "order_id": saved_order_id,
        "checkout_order_id": checkout_order_id,
        "message": "sent",
    }


@router.post("/api/webapp/order", deprecated=True)
def api_webapp_order(payload: WebappOrderPayload):
    raise HTTPException(
        status_code=410,
        detail="Deprecated endpoint. Use /api/public/checkout/from-webapp",
    )


@router.get("/api/site/menu")
def site_menu():
    return menu_catalog.build_public_menu()


@router.get("/api/site/theme", deprecated=True)
def site_theme():
    raise HTTPException(status_code=410, detail="Theme constructor disabled")


@router.get("/api/site-settings")
def site_settings():
    return menu_catalog.get_site_settings()


@router.get("/api/site/categories")
def site_categories():
    return {"items": menu_catalog.list_categories(include_inactive=False)}


@router.get("/api/site/categories/{slug}")
def site_category(slug: str):
    category = menu_catalog.get_category_details(slug, include_inactive=False)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get("/api/site/products/{slug}")
def site_product(slug: str):
    item = menu_catalog.get_item_by_slug(slug, include_inactive=False)
    if not item or item.get("type") != "product":
        raise HTTPException(status_code=404, detail="Product not found")
    return item


@router.get("/api/site/masterclasses/{slug}")
def site_masterclass(slug: str):
    item = menu_catalog.get_item_by_slug(slug, include_inactive=False)
    if not item or item.get("type") != "course":
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return item


@router.get("/api/site/items")
def site_items(category_id: int | None = None, type: str | None = None):
    return {
        "items": menu_catalog.list_items(
            include_inactive=False, category_id=category_id, item_type=type
        )
    }


@router.get("/api/site/home")
def site_home():
    return {
        "settings": menu_catalog.get_site_settings(),
        "menu": menu_catalog.build_public_menu(),
    }


@router.get("/api/site/pages/{page_key}", deprecated=True)
def site_page(page_key: str):
    raise HTTPException(status_code=410, detail="Page constructor disabled")


# LEGACY CATALOG API (products_baskets/products_courses).
# Используйте /api/public/menu* и /api/admin/menu* для работы с menu_items.
@router.get("/api/categories", deprecated=True)
def api_categories(type: str | None = None, active_only: bool = True):
    """
    Вернуть список категорий для товаров или курсов.
    Если type не указан — вернуть активные категории всех типов.
    """
    product_type = _validate_category_type(type) if type else None
    return products_service.list_categories(product_type, include_inactive=not active_only)


@router.get("/api/categories/{slug}", deprecated=True)
def api_category_detail(slug: str):
    category = products_service.get_category_with_items(slug)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get("/api/products", deprecated=True)
def api_products(type: str, category_slug: str | None = None):
    """
    Вернуть список товаров/курсов.
    Если category_slug передан — фильтровать по категории.
    """
    product_type = _validate_type(type)
    return products_service.list_products(product_type, category_slug=category_slug, is_active=True)


@router.get("/api/products/{product_id}", deprecated=True)
def api_product_detail(product_id: int):
    """Возвращает данные одного товара или мастер-класса по ID."""
    product = products_service.get_product_by_id(product_id)
    if not product or not product.get("is_active"):
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/api/masterclasses/{masterclass_id}", deprecated=True)
def api_masterclass_detail(masterclass_id: int):
    """Возвращает данные мастер-класса по ID."""
    masterclass = products_service.get_course_by_id(masterclass_id)
    if not masterclass or not masterclass.get("is_active"):
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return masterclass


@router.post("/api/masterclasses/{masterclass_id}/reviews")
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
        raise HTTPException(status_code=422, detail=detail)

    return {"success": True, "review_id": review_id, "status": "pending"}


@router.get("/api/masterclasses/{masterclass_id}/reviews")
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


@router.post("/api/products/{product_id}/reviews")
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
        raise HTTPException(status_code=422, detail=detail)

    return {"success": True, "review_id": review_id, "status": "pending"}


@router.get("/api/products/{product_id}/reviews")
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


@router.get("/api/products/{product_id}/rating")
def get_product_rating(product_id: int):
    product = products_service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return reviews_service.get_rating_summary(product_id)


@router.post("/api/reviews/{review_id}/photos")
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
        raise HTTPException(status_code=422, detail=detail)

    return {"ok": True, "photos": photos}


@router.get("/api/cart")
def api_cart(request: Request, response: Response, user_id: int | None = None):
    """Вернуть содержимое корзины пользователя и сумму заказа."""
    resolved_user_id, session_id = _resolve_cart_identity(request, response, user_id=user_id)
    return _build_cart_response(user_id=resolved_user_id, session_id=session_id)


@router.post("/api/cart/apply-promocode")
def api_cart_apply_promocode(
    payload: CartPromocodeApplyPayload,
    request: Request,
    response: Response,
):
    resolved_user_id, session_id = _resolve_cart_identity(
        request,
        response,
        user_id=payload.user_id,
    )

    cart_data = _build_cart_response(user_id=resolved_user_id, session_id=session_id)
    items = cart_data.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    result = promocodes_service.validate_promocode(payload.code, resolved_user_id, items)
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


@router.post("/api/checkout")
def api_checkout(payload: CheckoutPayload, request: Request):
    """Оформить заказ из текущей корзины WebApp."""
    auth_user_id = _get_cart_user_id_from_authorization(request)
    resolved_user_id = auth_user_id or payload.user_id
    if resolved_user_id is None or int(resolved_user_id) <= 0:
        raise HTTPException(status_code=422, detail="user_id is required")
    resolved_user_id = int(resolved_user_id)

    users_service.get_or_create_user_from_telegram(
        {
            "id": resolved_user_id,
            "username": payload.user_name,
            "first_name": payload.customer_name,
        }
    )

    cart_data = _build_cart_response(user_id=resolved_user_id)
    normalized_items = cart_data.get("items") or []
    removed_items = cart_data.get("removed_items") or []
    total = int(cart_data.get("total") or 0)

    if not normalized_items:
        cart_service.clear_cart(resolved_user_id)
        raise HTTPException(status_code=400, detail="No valid items in cart")

    user_name = payload.user_name or "webapp"

    promo_result = None
    if payload.promocode:
        promo_result = promocodes_service.validate_promocode(
            payload.promocode, resolved_user_id, normalized_items
        )
        if not promo_result:
            raise HTTPException(status_code=400, detail="Invalid promocode")

    discount_amount = int(promo_result.get("discount_amount", 0)) if promo_result else 0
    final_total = int(promo_result.get("final_total", total)) if promo_result else total

    order_text = format_order_for_admin(
        user_id=resolved_user_id,
        user_name=user_name,
        items=normalized_items,
        total=final_total,
        customer_name=payload.customer_name,
        contact=payload.contact,
        comment=payload.comment or "",
    )

    order_id = orders_service.add_order(
        user_id=resolved_user_id,
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

    cart_service.clear_cart(resolved_user_id)

    return {
        "ok": True,
        "order_id": order_id,
        "total": final_total,
        "discount_amount": discount_amount,
        "removed_items": removed_items,
    }


@router.post("/api/cart/add")
def api_cart_add(payload: CartItemPayload, request: Request, response: Response):
    qty = payload.qty or 1
    if qty <= 0:
        raise HTTPException(status_code=422, detail="qty must be positive")

    product_type = _validate_type(payload.type)
    product = _product_by_type(product_type, int(payload.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    resolved_user_id, session_id = _resolve_cart_identity(
        request,
        response,
        user_id=payload.user_id,
    )
    cart_service.add_to_cart(
        user_id=resolved_user_id,
        product_id=int(payload.product_id),
        qty=qty,
        product_type=product_type,
        session_id=session_id,
    )

    return _build_cart_response(user_id=resolved_user_id, session_id=session_id)


@router.post("/api/cart/update")
def api_cart_update(payload: CartItemPayload, request: Request, response: Response):
    qty = payload.qty or 0
    product_type = _validate_type(payload.type)

    resolved_user_id, session_id = _resolve_cart_identity(
        request,
        response,
        user_id=payload.user_id,
    )
    if qty <= 0:
        cart_service.remove_from_cart(
            resolved_user_id,
            int(payload.product_id),
            product_type,
            session_id=session_id,
        )
        return _build_cart_response(user_id=resolved_user_id, session_id=session_id)

    product = _product_by_type(product_type, int(payload.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    current_items, _ = cart_service.get_cart_items(resolved_user_id, session_id=session_id)
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
            cart_service.change_qty(
                resolved_user_id,
                int(payload.product_id),
                delta,
                product_type,
                session_id=session_id,
            )
    else:
        cart_service.add_to_cart(
            user_id=resolved_user_id,
            product_id=int(payload.product_id),
            qty=qty,
            product_type=product_type,
            session_id=session_id,
        )

    return _build_cart_response(user_id=resolved_user_id, session_id=session_id)


@router.post("/api/cart/clear")
def api_cart_clear(
    request: Request,
    response: Response,
    payload: CartClearPayload = Body(default=CartClearPayload()),
):
    resolved_user_id, session_id = _resolve_cart_identity(
        request,
        response,
        user_id=payload.user_id,
    )
    cart_service.clear_cart(resolved_user_id, session_id=session_id)
    return _build_cart_response(user_id=resolved_user_id, session_id=session_id)


@router.get("/api/me")
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


@router.post("/api/me/contact")
def api_me_contact(payload: ContactPayload):
    try:
        user = users_service.update_user_contact(payload.telegram_id, payload.phone)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")

    return {"ok": True, "phone": user.phone}


@router.get("/api/favorites")
def api_favorites(telegram_id: int):
    user = users_service.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return favorites_service.list_favorites(telegram_id)


@router.post("/api/favorites/toggle")
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


@router.post("/api/promocode/validate")
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
        cart_data = _build_cart_response(user_id=payload.telegram_id)
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


@router.post("/api/profile/update")
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


@router.post("/api/profile/avatar-url")
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


@router.get("/", include_in_schema=False)
def webapp_home():
    return _serve_webapp_index()


@router.get("/cart", include_in_schema=False)
def webapp_cart():
    return FileResponse(WEBAPP_DIR / "cart.html", media_type="text/html")


@router.get("/categories", include_in_schema=False)
def categories_page():
    return RedirectResponse(url="/webapp/categories.html", status_code=302)


@router.get("/category/{slug}", include_in_schema=False)
def category_page(slug: str):
    return RedirectResponse(url=f"/c/{slug}", status_code=302)


@router.get("/c/{slug}", include_in_schema=False)
def category_slug_page(slug: str):
    return _serve_webapp_index()


@router.get("/i/{slug}", include_in_schema=False)
def item_slug_page(slug: str):
    return _serve_webapp_index()


@router.get("/p/{slug}", include_in_schema=False)
def product_slug_page(slug: str):
    return _serve_webapp_index()


@router.get("/m/{slug}", include_in_schema=False)
def masterclass_slug_page(slug: str):
    return _serve_webapp_index()


@router.get("/item/{slug}", include_in_schema=False)
def item_page(slug: str):
    return _serve_webapp_index()
