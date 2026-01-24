from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.jwt_auth import create_access_token, decode_access_token


@pytest.fixture(autouse=True)
def _set_jwt_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")


def test_create_and_decode_access_token_roundtrip_with_telegram_id():
    token = create_access_token(user_id=123, telegram_id=456, ttl_seconds=60)
    payload = decode_access_token(token)

    assert payload["user_id"] == 123
    assert payload["telegram_id"] == 456
    assert payload["exp"] >= payload["iat"]


def test_create_and_decode_access_token_without_telegram_id():
    token = create_access_token(user_id=321, ttl_seconds=60)
    payload = decode_access_token(token)

    assert payload["user_id"] == 321
    assert "telegram_id" not in payload


def test_decode_access_token_rejects_tampered_token():
    token = create_access_token(user_id=1, telegram_id=2, ttl_seconds=60)
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(tampered)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "token_invalid"
