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
            "ALTER TABLE product_reviews ADD COLUMN IF NOT EXISTS masterclass_id INTEGER",
            "ALTER TABLE product_reviews ALTER COLUMN product_id DROP NOT NULL",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS session_key VARCHAR(64)",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS user_identifier TEXT",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS client_ip VARCHAR(64)",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMP",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS unread_for_manager INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE webchat_messages ADD COLUMN IF NOT EXISTS is_read_by_manager BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE webchat_messages ADD COLUMN IF NOT EXISTS is_read_by_client BOOLEAN NOT NULL DEFAULT FALSE",
        ]

        with engine.begin() as conn:
            for statement in alter_statements:
                conn.execute(text(statement))

            conn.execute(
                text(
                    "UPDATE webchat_sessions SET session_key = session_id WHERE session_key IS NULL"
                )
            )

            conn.execute(
                text(
                    """
                    UPDATE webchat_sessions
                    SET last_message_at = COALESCE(last_message_at, updated_at, created_at)
                    WHERE last_message_at IS NULL
                    """
                )
            )

    _ensure_optional_columns()

    def _ensure_product_categories_table() -> None:
        create_statement = """
        CREATE TABLE IF NOT EXISTS product_categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            slug VARCHAR NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            type VARCHAR NOT NULL DEFAULT 'basket',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        alter_statements = [
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS type VARCHAR NOT NULL DEFAULT 'basket'",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()",
        ]

        with engine.begin() as conn:
            conn.execute(text(create_statement))
            for statement in alter_statements:
                conn.execute(text(statement))

    _ensure_product_categories_table()

    def _ensure_promocodes_table() -> None:
        create_statement = """
        CREATE TABLE IF NOT EXISTS promocodes (
            id SERIAL PRIMARY KEY,
            code VARCHAR NOT NULL UNIQUE,
            discount_type VARCHAR NOT NULL,
            discount_value NUMERIC(10, 2) NOT NULL DEFAULT 0,
            scope VARCHAR NOT NULL DEFAULT 'all',
            target_id INTEGER NULL,
            date_start TIMESTAMP NULL,
            date_end TIMESTAMP NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            max_uses INTEGER NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            one_per_user BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        alter_statements = [
            "ALTER TABLE promocodes ADD COLUMN IF NOT EXISTS discount_value NUMERIC(10, 2) NOT NULL DEFAULT 0",
            "ALTER TABLE promocodes ADD COLUMN IF NOT EXISTS scope VARCHAR NOT NULL DEFAULT 'all'",
            "ALTER TABLE promocodes ADD COLUMN IF NOT EXISTS target_id INTEGER NULL",
            "ALTER TABLE promocodes ADD COLUMN IF NOT EXISTS date_start TIMESTAMP NULL",
            "ALTER TABLE promocodes ADD COLUMN IF NOT EXISTS date_end TIMESTAMP NULL",
            "ALTER TABLE promocodes ADD COLUMN IF NOT EXISTS one_per_user BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE promocodes ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()",
        ]

        with engine.begin() as conn:
            conn.execute(text(create_statement))
            for statement in alter_statements:
                conn.execute(text(statement))

            backfill_discount_value = text(
                """
                DO $$
                BEGIN
                    IF EXISTS(
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'promocodes' AND column_name = 'value'
                    ) THEN
                        UPDATE promocodes
                        SET discount_value = COALESCE(discount_value, value)
                        WHERE discount_value IS NULL;
                    END IF;
                END
                $$;
                """
            )
            conn.execute(backfill_discount_value)

    _ensure_promocodes_table()

    if ADMIN_IDS_SET:
        with get_session() as session:
            for admin_id in ADMIN_IDS_SET:
                user = session.scalar(select(User).where(User.telegram_id == admin_id))
                if user:
                    if not user.is_admin:
                        user.is_admin = True
                else:
                    session.add(User(telegram_id=admin_id, is_admin=True))
