"""
Конфигурация SQLAlchemy + PostgreSQL.
Используется одновременно Telegram-ботом и backend webapi.py.
Таблицы создаются через Base.metadata.create_all.
.env НЕ изменяем.
"""

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, select, text, func, or_
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from utils.home_images import HOME_PLACEHOLDER_URL


DB_NAME = os.getenv("DB_NAME", "miniden")
DB_USER = os.getenv("DB_USER", "miniden_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "strongpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

engine = create_engine(DATABASE_URL, future=True, echo=os.getenv("SQLALCHEMY_ECHO") == "1")
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)
Base = declarative_base()


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


