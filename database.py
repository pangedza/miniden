"""
Конфигурация SQLAlchemy + PostgreSQL.
Используется одновременно Telegram-ботом и backend webapi.py.
Таблицы создаются через Base.metadata.create_all.
.env НЕ изменяем.
"""

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker


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


def init_db() -> None:
    from config import ADMIN_IDS_SET  # noqa: WPS433
    from models import Base, User  # noqa: WPS433

    Base.metadata.create_all(bind=engine)

    def _ensure_optional_columns() -> None:
        """Добавить недостающие колонки без разрушения существующей схемы."""

        alter_statements = [
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS wb_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS ozon_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS yandex_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS avito_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS masterclass_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS short_description TEXT",
            "ALTER TABLE products_courses ADD COLUMN IF NOT EXISTS short_description TEXT",
            "ALTER TABLE products_courses ADD COLUMN IF NOT EXISTS masterclass_url TEXT",
        ]

        with engine.begin() as conn:
            for statement in alter_statements:
                conn.execute(text(statement))

    _ensure_optional_columns()

    if ADMIN_IDS_SET:
        with get_session() as session:
            for admin_id in ADMIN_IDS_SET:
                user = session.scalar(select(User).where(User.telegram_id == admin_id))
                if user:
                    if not user.is_admin:
                        user.is_admin = True
                else:
                    session.add(User(telegram_id=admin_id, is_admin=True))
