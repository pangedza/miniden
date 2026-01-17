from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from database import get_session
from models import AuthSession, User
from services import favorites as favorites_service
from services import orders as orders_service
from services import user_admin as user_admin_service
from services import user_stats as user_stats_service
from services import users as users_service
from services.telegram_webapp_auth import authenticate_telegram_webapp_user

SETTINGS = get_settings()
BOT_TOKEN = SETTINGS.bot_token
AUTH_SESSION_TTL_SECONDS = 600
COOKIE_MAX_AGE = 30 * 24 * 60 * 60

router = APIRouter()


class TelegramAuthPayload(BaseModel):
    init_data: str | None = None
    auth_query: str | None = None


class TelegramWebAppAuthPayload(BaseModel):
    init_data: str | None = None


class VersionedProfileResponse(BaseModel):
    authenticated: bool
    user: dict[str, Any] | None = None


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
    check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(filtered_pairs, key=lambda item: item[0])
    )
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, str(received_hash)):
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
    check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(filtered_pairs, key=lambda item: item[0])
    )
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


def _full_name(user: User) -> str:
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
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    telegram_id = int(user.telegram_id)
    display_full_name = _full_name(user) or None

    try:
        orders = orders_service.get_orders_by_user(telegram_id, include_archived=False) or []
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


@router.post("/api/auth/telegram_webapp")
def api_auth_telegram_webapp(payload: TelegramWebAppAuthPayload, response: Response):
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

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
            },
        }


@router.post("/api/auth/create-token")
def api_auth_create_token():
    token = str(uuid4())
    with get_session() as s:
        s.add(AuthSession(token=token))
    return {"ok": True, "token": token}


@router.get("/api/auth/check")
def api_auth_check(token: str, response: Response, include_notes: bool = False):
    with get_session() as s:
        session = s.query(AuthSession).filter(AuthSession.token == token).first()
        if not session:
            response.status_code = 404
            return {"ok": False, "reason": "not_found"}

        if session.created_at and datetime.utcnow() - session.created_at > timedelta(
            seconds=AUTH_SESSION_TTL_SECONDS
        ):
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

        profile = _build_user_profile(session, user, include_notes=include_notes)

    return {"authenticated": True, "user": profile}


@router.post("/api/auth/telegram")
def api_auth_telegram(payload: TelegramAuthPayload, response: Response):
    if (payload.init_data is None and payload.auth_query is None) or (
        payload.init_data is not None and payload.auth_query is not None
    ):
        raise HTTPException(
            status_code=400, detail="Provide exactly one of init_data or auth_query"
        )

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
    response.delete_cookie("tg_user_id", path="/")
    return {"ok": True}


__all__ = [
    "BOT_TOKEN",
    "COOKIE_MAX_AGE",
    "SETTINGS",
    "_build_user_profile",
    "_get_current_user_from_cookie",
    "_split_full_name",
    "_validate_telegram_webapp_init_data",
    "router",
]
