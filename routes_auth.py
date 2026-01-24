"""Роуты авторизации (Telegram Login/WebApp + phone OTP)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db, get_session
from models import AuthSession, LoginCode, User
from services import cart as cart_service
from services import orders as orders_service
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
from utils.phone import normalize_phone

router = APIRouter()

logger = logging.getLogger(__name__)

AUTH_SESSION_TTL_SECONDS = 600
LOGIN_CODE_TTL_SECONDS = 5 * 60
LOGIN_CODE_MAX_ATTEMPTS = 5
LOGIN_CODE_LENGTH = 6


class TelegramAuthPayload(BaseModel):
    init_data: str | None = None
    auth_query: str | None = None


class TelegramWebAppAuthPayload(BaseModel):
    init_data: str | None = Field(default=None, alias="initData")

    class Config:
        allow_population_by_field_name = True
        populate_by_name = True


class RequestCodePayload(BaseModel):
    phone: str


class VerifyCodePayload(BaseModel):
    phone: str
    code: str


class BotCreateCodePayload(BaseModel):
    phone: str
    telegram_id: int
    telegram_username: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


def _normalize_init_data(init_data: str | None) -> str:
    normalized = (init_data or "").strip()
    if normalized.startswith("?"):
        normalized = normalized[1:]
    return normalized


def _get_code_salt() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if secret:
        return secret
    if BOT_TOKEN:
        return BOT_TOKEN
    raise HTTPException(status_code=500, detail="code_salt_missing")


def _hash_login_code(*, phone: str, code: str) -> str:
    salt = _get_code_salt()
    payload = f"{phone}:{code}:{salt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _generate_login_code() -> str:
    upper_bound = 10**LOGIN_CODE_LENGTH
    return f"{secrets.randbelow(upper_bound):0{LOGIN_CODE_LENGTH}d}"


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "is_admin": bool(user.is_admin),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _invalidate_previous_codes(session: Session, phone: str) -> None:
    session.query(LoginCode).where(
        LoginCode.phone == phone,
        LoginCode.used_at.is_(None),
    ).update({LoginCode.used_at: datetime.utcnow()}, synchronize_session=False)


def _latest_code_for_phone(session: Session, phone: str) -> LoginCode | None:
    stmt = (
        select(LoginCode)
        .where(LoginCode.phone == phone)
        .order_by(LoginCode.created_at.desc(), LoginCode.id.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def _validate_code_record(code_record: LoginCode) -> None:
    now = datetime.utcnow()
    if code_record.used_at is not None:
        raise HTTPException(status_code=400, detail="code_used")
    if code_record.expires_at <= now:
        raise HTTPException(status_code=400, detail="code_expired")
    if code_record.attempts >= LOGIN_CODE_MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail="code_attempts_exceeded")


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


@router.post("/api/auth/request-code")
def api_auth_request_code(payload: RequestCodePayload, db: Session = Depends(get_db)):
    try:
        normalized_phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user = users_service.get_or_create_user_by_phone(db, normalized_phone)

    code = _generate_login_code()
    code_hash = _hash_login_code(phone=normalized_phone, code=code)
    expires_at = datetime.utcnow() + timedelta(seconds=LOGIN_CODE_TTL_SECONDS)

    _invalidate_previous_codes(db, normalized_phone)

    login_code = LoginCode(
        phone=normalized_phone,
        code_hash=code_hash,
        telegram_id=user.telegram_id,
        expires_at=expires_at,
        created_at=datetime.utcnow(),
        attempts=0,
    )
    db.add(login_code)
    db.flush()

    logger.info("Login code generated for phone=%s code=%s", normalized_phone, code)

    return {"ok": True}


@router.post("/api/bot/auth/create-code")
def api_bot_auth_create_code(payload: BotCreateCodePayload, db: Session = Depends(get_db)):
    try:
        normalized_phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user = users_service.get_or_create_user_by_phone(db, normalized_phone)
    payload_telegram_id = int(payload.telegram_id)
    if user.telegram_id is None:
        user = users_service.attach_telegram_id(
            db,
            user=user,
            telegram_id=payload_telegram_id,
            username=payload.telegram_username,
        )
    elif user.telegram_id != payload_telegram_id:
        raise HTTPException(status_code=409, detail="telegram_id_conflict")

    code = _generate_login_code()
    code_hash = _hash_login_code(phone=normalized_phone, code=code)
    expires_at = datetime.utcnow() + timedelta(seconds=LOGIN_CODE_TTL_SECONDS)

    _invalidate_previous_codes(db, normalized_phone)

    login_code = LoginCode(
        phone=normalized_phone,
        code_hash=code_hash,
        telegram_id=user.telegram_id,
        expires_at=expires_at,
        created_at=datetime.utcnow(),
        attempts=0,
    )
    db.add(login_code)
    db.flush()

    logger.info(
        "Bot login code generated for phone=%s telegram_id=%s",
        normalized_phone,
        user.telegram_id,
    )

    return {"code": code, "expires_in_seconds": LOGIN_CODE_TTL_SECONDS}


@router.post("/api/auth/verify-code", response_model=AuthResponse)
def api_auth_verify_code(payload: VerifyCodePayload, db: Session = Depends(get_db)):
    try:
        normalized_phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    code_record = _latest_code_for_phone(db, normalized_phone)
    if not code_record:
        raise HTTPException(status_code=400, detail="code_not_found")

    _validate_code_record(code_record)

    expected_hash = _hash_login_code(phone=normalized_phone, code=payload.code.strip())
    if not hmac.compare_digest(expected_hash, code_record.code_hash):
        code_record.attempts = int(code_record.attempts or 0) + 1
        if code_record.attempts >= LOGIN_CODE_MAX_ATTEMPTS:
            code_record.used_at = datetime.utcnow()
        db.flush()
        raise HTTPException(status_code=400, detail="code_invalid")

    user = db.scalar(select(User).where(User.phone == normalized_phone))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    code_record.used_at = datetime.utcnow()
    if user.telegram_id and code_record.telegram_id is None:
        code_record.telegram_id = user.telegram_id
    db.flush()

    access_token = create_access_token(user_id=user.id, telegram_id=user.telegram_id)

    return AuthResponse(access_token=access_token, user=_serialize_user(user))


@router.get("/api/me/orders")
def api_me_orders(current_user: User = Depends(get_current_user_from_token)):
    if current_user.telegram_id is None:
        return {"items": []}
    orders = orders_service.get_orders_by_user(int(current_user.telegram_id))
    return {"items": orders}


@router.get("/api/me/cart")
def api_me_cart(current_user: User = Depends(get_current_user_from_token)):
    if current_user.telegram_id is None:
        return {"items": [], "removed": []}
    items, removed = cart_service.get_cart_items(int(current_user.telegram_id))
    return {"items": items, "removed": removed}


@router.get("/api/me/addresses")
def api_me_addresses(current_user: User = Depends(get_current_user_from_token)):
    return {"items": []}


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
        "phone": current_user.phone,
        "is_admin": bool(current_user.is_admin),
    }


@router.get("/api/auth/session")
def get_auth_session():
    token = str(uuid4())
    expires_at = datetime.utcnow() + timedelta(seconds=AUTH_SESSION_TTL_SECONDS)
    with get_session() as session:
        session.add(AuthSession(token=token))
    return {"token": token, "expires_at": expires_at.isoformat()}


@router.get("/api/auth/telegram")
def auth_telegram(request: Request, response: Response):
    user = authenticate_telegram_webapp_user(request)
    response.set_cookie(
        key="tg_user_id",
        value=str(user.telegram_id),
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
    )
    return {"status": "ok", "user": {"id": user.id, "telegram_id": user.telegram_id}}


@router.get("/api/auth/status")
def auth_status(request: Request):
    user = _get_current_user_from_cookie(request)
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, "user": {"id": user.id, "telegram_id": user.telegram_id}}


@router.get("/api/auth/telegram/login")
def auth_telegram_login(auth_payload: str = Query(..., alias="auth_payload")):
    parsed = _parse_telegram_auth_data(auth_payload)
    user_data = _extract_user_from_auth_data(parsed)
    user = _upsert_user_from_webapp_data(user_data)
    redirect = RedirectResponse(url="/lk.html")
    redirect.set_cookie(
        key="tg_user_id",
        value=str(user.telegram_id),
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
    )
    return redirect
