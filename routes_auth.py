"""Роуты авторизации (Telegram Login/WebApp)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from database import get_session
from models import AuthSession, User
from services import users as users_service
from services.telegram_webapp_auth import (
    authenticate_telegram_webapp_user,
    validate_telegram_webapp_init_data,
)
from routes_public import (
    BOT_TOKEN,
    COOKIE_MAX_AGE,
    _build_user_profile,
    _get_current_user_from_cookie,
)
from utils.jwt_auth import create_access_token, get_current_user_from_token

router = APIRouter()

logger = logging.getLogger(__name__)

AUTH_SESSION_TTL_SECONDS = 600


class TelegramAuthPayload(BaseModel):
    init_data: str | None = None
    auth_query: str | None = None


class TelegramWebAppAuthPayload(BaseModel):
    init_data: str | None = Field(default=None, alias="initData")

    class Config:
        allow_population_by_field_name = True
        populate_by_name = True


def _normalize_init_data(init_data: str | None) -> str:
    normalized = (init_data or "").strip()
    if normalized.startswith("?"):
        normalized = normalized[1:]
    return normalized


def _upsert_user_from_webapp_data(user_data: dict[str, Any]) -> User:
    telegram_id = user_data.get("id")
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="invalid_user")

    first_name = (user_data.get("first_name") or "").strip()
    last_name = (user_data.get("last_name") or "").strip()
    full_name = " ".join(part for part in [first_name, last_name] if part) or None

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
            raise HTTPException(status_code=400, detail="invalid_user")
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to upsert telegram user", exc_info=exc)
            raise HTTPException(status_code=500, detail="authorization_failed")

    return user


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


def _extract_user_from_auth_data(data: dict[str, Any]) -> dict[str, Any]:
    if "user" in data:
        try:
            return json.loads(data["user"])
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid user payload")
    return data


@router.post("/api/auth/telegram_webapp")
def api_auth_telegram_webapp(payload: TelegramWebAppAuthPayload, response: Response):
    """Авторизация WebApp через init_data внутри Telegram."""

    init_data = _normalize_init_data(payload.init_data)
    if not init_data:
        response.status_code = 400
        return {"status": "error", "error": "init_data_missing"}

    try:
        user_data = validate_telegram_webapp_init_data(init_data, BOT_TOKEN)
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

    try:
        user = _upsert_user_from_webapp_data(user_data)
    except HTTPException as exc:
        response.status_code = exc.status_code
        error_code = exc.detail if isinstance(exc.detail, str) else "authorization_failed"
        return {"status": "error", "error": error_code}

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


@router.post("/api/auth/telegram-webapp")
def api_auth_telegram_webapp_jwt(payload: TelegramWebAppAuthPayload, response: Response):
    """Авторизация Telegram WebApp с выдачей JWT access_token."""

    init_data = _normalize_init_data(payload.init_data)
    if not init_data:
        raise HTTPException(status_code=400, detail="init_data_missing")

    user_data = validate_telegram_webapp_init_data(init_data, BOT_TOKEN)
    user = _upsert_user_from_webapp_data(user_data)
    access_token = create_access_token(user_id=user.id, telegram_id=user.telegram_id)

    response.set_cookie(
        key="tg_user_id",
        value=str(user.telegram_id),
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
    }


@router.get("/api/auth/me")
def api_auth_me(current_user: User = Depends(get_current_user_from_token)):
    """Минимальная проверка JWT-токена для будущей защиты роутов."""

    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "is_admin": current_user.is_admin,
    }


@router.post("/api/auth/create-token")
def api_auth_create_token():
    """
    Создать новую сессию авторизации для deeplink-а из бота.
    Возвращает {"ok": true, "token": "..."}.
    """
    token = str(uuid4())
    with get_session() as s:
        s.add(AuthSession(token=token))
    return {"ok": True, "token": token}


@router.get("/api/auth/check")
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


@router.get("/api/auth/telegram-login")
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


@router.get("/api/auth/session")
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
                validate_telegram_webapp_init_data,
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


@router.post("/api/auth/telegram")
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


@router.post("/api/auth/logout")
def api_auth_logout(response: Response):
    """
    Logout для обычного сайта: сбрасывает cookie tg_user_id.
    Используется кнопкой "Выйти"/"Сменить пользователя".
    """
    response.delete_cookie("tg_user_id", path="/")
    return {"ok": True}
