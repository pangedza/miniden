from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Callable, Optional
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request, Response

from models import User
from services import users as users_service

logger = logging.getLogger(__name__)


def get_telegram_init_data_from_request(request: Request) -> str | None:
    """Извлекает initData из query-параметров и HTTP-заголовков запроса."""

    query_params = request.query_params
    init_data = query_params.get("tgWebAppData") or query_params.get("init_data")
    if init_data:
        return init_data

    header_names = (
        "Telegram-Init-Data",
        "X-Telegram-Init-Data",
        "X-Telegram-Web-View-Data",
        "X-Telegram-Web-App-Data",
    )
    for header in header_names:
        header_value = request.headers.get(header)
        if header_value:
            return header_value

    return None


def validate_telegram_webapp_init_data(
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

    if not bot_token:
        raise HTTPException(status_code=401, detail="invalid_signature")

    secret_key = hashlib.sha256(bot_token.encode()).digest()
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


async def authenticate_telegram_webapp_user(
    request: Request,
    db_session,
    validate_init_data: Callable[[str], dict],
    response: Optional[Response] = None,
    cookie_max_age: int | None = None,
) -> Optional[User]:
    """
    Пытается авторизовать пользователя по Telegram initData из запроса.

    Возвращает объект User или None, если авторизация не удалась.
    """

    init_data = get_telegram_init_data_from_request(request)
    if not init_data:
        return None

    try:
        user_data = validate_init_data(init_data)
    except HTTPException:
        return None
    except Exception:
        return None

    telegram_id = user_data.get("id")
    if telegram_id is None:
        return None

    first_name = (user_data.get("first_name") or "").strip()
    last_name = (user_data.get("last_name") or "").strip()
    full_name_parts = [part for part in [first_name, last_name] if part]
    full_name = " ".join(full_name_parts) or None

    try:
        user = users_service.get_or_create_user_from_telegram(
            db_session,
            telegram_id=int(telegram_id),
            username=user_data.get("username"),
            full_name=full_name,
            phone=user_data.get("phone"),
        )
    except Exception:
        logger.exception("Failed to authorize Telegram WebApp user")
        return None

    if response and cookie_max_age:
        response.set_cookie(
            key="tg_user_id",
            value=str(user.telegram_id),
            httponly=True,
            max_age=cookie_max_age,
            samesite="lax",
        )

    return user
