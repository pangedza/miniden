from __future__ import annotations

import logging
from typing import Callable, Optional

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
        "X-Telegram-Web-View-Data",
        "X-Telegram-Web-App-Data",
    )
    for header in header_names:
        header_value = request.headers.get(header)
        if header_value:
            return header_value

    return None


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
