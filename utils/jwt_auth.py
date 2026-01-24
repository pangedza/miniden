from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="jwt_secret_missing",
        )
    return secret


def _sign(signing_input: str, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256)
    return _b64url_encode(signature.digest())


def create_access_token(
    *,
    user_id: int,
    telegram_id: int | None = None,
    ttl_seconds: int = ACCESS_TOKEN_TTL_SECONDS,
) -> str:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    secret = _get_jwt_secret()
    now = int(time.time())
    payload: dict[str, Any] = {
        "user_id": int(user_id),
        "iat": now,
        "exp": now + int(ttl_seconds),
    }
    if telegram_id is not None:
        payload["telegram_id"] = int(telegram_id)

    header_segment = _b64url_encode(json.dumps({"alg": ALGORITHM, "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}"
    signature_segment = _sign(signing_input, secret)
    return f"{signing_input}.{signature_segment}"


def decode_access_token(token: str) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_missing")

    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_invalid")

    header_segment, payload_segment, signature_segment = parts
    secret = _get_jwt_secret()
    expected_signature = _sign(f"{header_segment}.{payload_segment}", secret)
    if not hmac.compare_digest(expected_signature, signature_segment):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_invalid")

    try:
        header = json.loads(_b64url_decode(header_segment))
        payload = json.loads(_b64url_decode(payload_segment))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_invalid")

    if header.get("alg") != ALGORITHM:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_invalid")

    exp_raw = payload.get("exp")
    try:
        exp = int(exp_raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_invalid")

    if exp < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_expired")

    return payload


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_missing")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_invalid")

    return token.strip()


def get_current_user_from_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    payload = decode_access_token(token)

    user_id_raw = payload.get("user_id")
    user: User | None = None
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        user_id = None

    if user_id is not None:
        user = db.get(User, user_id)

    if user is None:
        telegram_id_raw = payload.get("telegram_id")
        try:
            telegram_id = int(telegram_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_invalid")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")

    return user
