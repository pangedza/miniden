from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("BOT_TOKEN", "test-bot-token")
os.environ.setdefault("JWT_SECRET", "test-secret")

from models import LoginCode, User
from routes_auth import (
    BotCreateCodePayload,
    LOGIN_CODE_LENGTH,
    LOGIN_CODE_TTL_SECONDS,
    api_bot_auth_create_code,
)


@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Session:
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("BOT_TOKEN", "test-bot-token")

    db_path = tmp_path / "bot-create-code.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    # Create only the tables needed for this endpoint with SQLite-friendly PKs.
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS login_codes"))
        connection.execute(text("DROP TABLE IF EXISTS users"))
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id BIGINT UNIQUE,
                    username VARCHAR,
                    first_name VARCHAR,
                    last_name VARCHAR,
                    phone VARCHAR UNIQUE,
                    avatar_url TEXT,
                    is_admin BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE login_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone VARCHAR(32) NOT NULL,
                    code_hash VARCHAR(128) NOT NULL,
                    telegram_id BIGINT,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME NOT NULL,
                    used_at DATETIME,
                    attempts INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        connection.execute(text("CREATE INDEX ix_login_codes_phone ON login_codes (phone)"))
        connection.execute(
            text("CREATE INDEX ix_login_codes_phone_created ON login_codes (phone, created_at)")
        )

    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_bot_create_code_returns_code_and_persists_record(db_session: Session) -> None:
    payload = BotCreateCodePayload(
        phone="+7 (999) 123-45-67",
        telegram_id=123456789,
        telegram_username="mini_den_bot",
    )

    response = api_bot_auth_create_code(payload, db=db_session)

    assert response["expires_in_seconds"] == LOGIN_CODE_TTL_SECONDS
    assert response["code"].isdigit()
    assert len(response["code"]) == LOGIN_CODE_LENGTH

    codes = db_session.scalars(select(LoginCode).where(LoginCode.phone == "79991234567")).all()
    assert len(codes) == 1
    assert codes[0].used_at is None

    user = db_session.scalar(select(User).where(User.phone == "79991234567"))
    assert user is not None
    assert user.telegram_id == 123456789


def test_bot_create_code_invalidates_previous_codes(db_session: Session) -> None:
    payload = BotCreateCodePayload(phone="79991234567", telegram_id=42, telegram_username="bot")

    first = api_bot_auth_create_code(payload, db=db_session)
    second = api_bot_auth_create_code(payload, db=db_session)

    assert first["code"] != second["code"]

    codes = db_session.scalars(
        select(LoginCode).where(LoginCode.phone == "79991234567").order_by(LoginCode.id.asc())
    ).all()

    assert len(codes) == 2
    assert codes[0].used_at is not None
    assert codes[1].used_at is None


def test_bot_create_code_conflict_when_phone_bound_to_other_telegram_id(db_session: Session) -> None:
    existing = User(phone="79991234567", telegram_id=100, created_at=datetime.utcnow())
    db_session.add(existing)
    db_session.flush()

    payload = BotCreateCodePayload(phone="79991234567", telegram_id=200, telegram_username="bot")

    with pytest.raises(HTTPException) as exc_info:
        api_bot_auth_create_code(payload, db=db_session)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "telegram_id_conflict"
