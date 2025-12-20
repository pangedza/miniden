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


def init_db() -> None:
    from config import ADMIN_IDS_SET  # noqa: WPS433
    from models import Base, HomeBanner, User  # noqa: WPS433
    from models import BotAction, BotButton, BotNode, BotRuntime  # noqa: WPS433

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

    def _ensure_bot_constructor_extensions() -> None:
        """Колонки и таблицы для узлов с ожиданием ввода."""

        alter_statements = [
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS node_type VARCHAR NOT NULL DEFAULT 'MESSAGE'",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS input_type VARCHAR",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS input_var_key VARCHAR",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS input_required BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS input_min_len INTEGER",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS input_error_text TEXT",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS next_node_code_success VARCHAR",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS next_node_code_cancel VARCHAR",
        ]

        create_user_vars = """
        CREATE TABLE IF NOT EXISTS user_vars (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            key VARCHAR NOT NULL,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        create_user_vars_index = """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_user_vars_user_key
            ON user_vars (user_id, key);
        """

        create_user_state = """
        CREATE TABLE IF NOT EXISTS user_state (
            user_id BIGINT PRIMARY KEY,
            waiting_node_code VARCHAR NULL,
            waiting_input_type VARCHAR NULL,
            waiting_var_key VARCHAR NULL,
            next_node_code_success VARCHAR NULL,
            next_node_code_cancel VARCHAR NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        with engine.begin() as conn:
            for statement in alter_statements:
                conn.execute(text(statement))

            conn.execute(text(create_user_vars))
            conn.execute(text(create_user_vars_index))
            conn.execute(text(create_user_state))

            conn.execute(
                text(
                    """
                    UPDATE bot_nodes
                    SET node_type = COALESCE(NULLIF(node_type, ''), 'MESSAGE')
                    WHERE node_type IS NULL OR node_type = ''
                    """
                )
            )

    _ensure_bot_constructor_extensions()

    def _ensure_admin_tables() -> None:
        create_admin_users = """
        CREATE TABLE IF NOT EXISTS admin_users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(150) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'superadmin',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        create_admin_sessions = """
        CREATE TABLE IF NOT EXISTS admin_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
            token VARCHAR(128) NOT NULL UNIQUE,
            app VARCHAR(32) NOT NULL DEFAULT 'admin',
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        alter_statements = [
            "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()",
            "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS password_hash TEXT",
            "ALTER TABLE admin_users ALTER COLUMN role SET DEFAULT 'superadmin'",
            "ALTER TABLE admin_sessions ALTER COLUMN app SET DEFAULT 'admin'",
        ]

        with engine.begin() as conn:
            conn.execute(text(create_admin_users))
            conn.execute(text(create_admin_sessions))
            for statement in alter_statements:
                conn.execute(text(statement))

            conn.execute(
                text(
                    "UPDATE admin_users SET role = 'superadmin' WHERE lower(role) = 'superadmin'"
                )
            )
            conn.execute(
                text(
                    "UPDATE admin_users SET role = 'admin_bot' WHERE lower(role) IN ('adminbot', 'admin_bot')"
                )
            )
            conn.execute(
                text(
                    "UPDATE admin_users SET role = 'admin_site' WHERE lower(role) IN ('adminsite', 'admin_site')"
                )
            )

    _ensure_admin_tables()

    def _ensure_default_superadmin() -> None:
        from models import AdminUser
        from models.admin_user import AdminRole
        from services.passwords import hash_password

        with get_session() as session:
            exists = session.query(AdminUser).limit(1).first()
            if exists:
                return

            session.add(
                AdminUser(
                    username="admin",
                    password_hash=hash_password("admin"),
                    role=AdminRole.superadmin.value,
                    is_active=True,
                )
            )

    _ensure_default_superadmin()

    def _ensure_product_categories_table() -> None:
        create_statement = """
        CREATE TABLE IF NOT EXISTS product_categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            slug VARCHAR NULL UNIQUE,
            description TEXT NULL,
            image_url TEXT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            type VARCHAR NOT NULL DEFAULT 'basket',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        def column_exists(conn, table: str, column: str) -> bool:
            result = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = :table AND column_name = :column
                    LIMIT 1
                    """
                ),
                {"table": table, "column": column},
            ).scalar()
            return bool(result)

        alter_statements = [
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS description TEXT NULL",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS image_url TEXT NULL",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS type VARCHAR NOT NULL DEFAULT 'basket'",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()",
        ]

        with engine.begin() as conn:
            conn.execute(text(create_statement))
            for statement in alter_statements:
                conn.execute(text(statement))

            if not column_exists(conn, "product_categories", "updated_at"):
                conn.execute(text("UPDATE product_categories SET updated_at = NOW()"))
            if not column_exists(conn, "product_categories", "description"):
                conn.execute(text("UPDATE product_categories SET description = NULL"))
            if not column_exists(conn, "product_categories", "image_url"):
                conn.execute(text("UPDATE product_categories SET image_url = NULL"))

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

    def _ensure_home_banners_table() -> None:
        create_statement = """
        CREATE TABLE IF NOT EXISTS home_banners (
            id SERIAL PRIMARY KEY,
            block_key VARCHAR(100) NULL,
            title VARCHAR(255) NOT NULL,
            subtitle TEXT NULL,
            body TEXT NULL,
            button_text VARCHAR(100) NULL,
            button_link VARCHAR(500) NULL,
            image_url VARCHAR(500) NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        alter_statements = [
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS block_key VARCHAR(100)",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS subtitle TEXT",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS body TEXT",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS button_text VARCHAR(100)",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS button_link VARCHAR(500)",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS image_url VARCHAR(500)",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()",
            "ALTER TABLE home_banners ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()",
        ]

        with engine.begin() as conn:
            conn.execute(text(create_statement))
            for statement in alter_statements:
                conn.execute(text(statement))

            conn.execute(
                text(
                    """
                    UPDATE home_banners
                    SET block_key = COALESCE(NULLIF(block_key, ''), 'legacy_banner')
                    WHERE block_key IS NULL OR block_key = ''
                    """
                )
            )

            conn.execute(
                text(
                    """
                    UPDATE home_banners
                    SET is_active = TRUE
                    WHERE is_active IS NULL
                    """
                )
            )

            conn.execute(
                text(
                    """
                    UPDATE home_banners
                    SET sort_order = 0
                    WHERE sort_order IS NULL
                    """
                )
            )

    _ensure_home_banners_table()

    def _ensure_home_block_seed() -> None:
        required_blocks: list[dict[str, str | int | bool | None]] = [
            {
                "block_key": "hero_main",
                "title": "Дом, который вяжется руками",
                "subtitle": "Miniden • домашнее вязание",
                "body": "Мини-истории о корзинках, детских комнатах и спокойных вечерах. Всё, что делаю — про уют, семью и обучение без спешки.",
                "button_text": "Узнать историю",
                "button_link": "#story",
                "image_url": HOME_PLACEHOLDER_URL,
                "is_active": True,
                "sort_order": 10,
            },
            {
                "block_key": "tile_home_kids",
                "title": "Дом и дети",
                "body": "Тёплые вещи для дома",
                "button_link": "/products",
                "image_url": HOME_PLACEHOLDER_URL,
                "is_active": True,
                "sort_order": 20,
            },
            {
                "block_key": "tile_process",
                "title": "Процесс",
                "body": "От пряжи до упаковки",
                "button_link": "/masterclasses",
                "image_url": HOME_PLACEHOLDER_URL,
                "is_active": True,
                "sort_order": 21,
            },
            {
                "block_key": "tile_baskets",
                "title": "Мои корзинки",
                "body": "Корзинки и наборы",
                "button_link": "/products",
                "image_url": HOME_PLACEHOLDER_URL,
                "is_active": True,
                "sort_order": 22,
            },
            {
                "block_key": "tile_learning",
                "title": "Обучение",
                "body": "Начните с нуля",
                "button_link": "/masterclasses",
                "image_url": HOME_PLACEHOLDER_URL,
                "is_active": True,
                "sort_order": 23,
            },
            {
                "block_key": "about_short",
                "title": "Немного обо мне",
                "body": "Я вяжу дома. Учу так, как училась сама: без спешки, в тишине и с акцентом на уютные вещи для семьи.",
                "sort_order": 30,
                "is_active": True,
            },
            {
                "block_key": "process_text",
                "title": "Процесс",
                "body": "От выбора пряжи до упаковки — всё делаю сама, небольшими партиями и с вниманием к мелочам.",
                "sort_order": 40,
                "is_active": True,
            },
            {
                "block_key": "shop_entry",
                "title": "Корзинки и наборы",
                "body": "Небольшие вещи, которые собирают дом воедино.",
                "button_text": "Перейти в каталог",
                "button_link": "/products",
                "image_url": HOME_PLACEHOLDER_URL,
                "is_active": True,
                "sort_order": 50,
            },
            {
                "block_key": "learning_entry",
                "title": "Мастер-классы",
                "body": "Простые шаги, поддержка и вдохновение, чтобы связать своё первое изделие.",
                "button_text": "Смотреть обучение",
                "button_link": "/masterclasses",
                "image_url": HOME_PLACEHOLDER_URL,
                "is_active": True,
                "sort_order": 60,
            },
        ]

        with get_session() as session:
            existing = {
                row.block_key: row
                for row in session.execute(
                    select(HomeBanner).where(HomeBanner.block_key.in_([b["block_key"] for b in required_blocks]))
                ).scalars()
            }
            for block in required_blocks:
                current = existing.get(block["block_key"])
                if current:
                    if not current.sort_order:
                        current.sort_order = block["sort_order"]
                else:
                    session.add(HomeBanner(**block))

    _ensure_home_block_seed()

    def _ensure_bot_constructor_seed() -> None:
        with get_session() as session:
            runtime = session.query(BotRuntime).first()
            if not runtime:
                session.add(BotRuntime(config_version=1))

            main_menu = (
                session.query(BotNode)
                .filter(BotNode.code == "MAIN_MENU")
                .first()
            )
            if not main_menu:
                main_menu = BotNode(
                    code="MAIN_MENU",
                    title="Главное меню",
                    message_text="Добро пожаловать! Используйте кнопки ниже, чтобы открыть разделы магазина.",
                    parse_mode="HTML",
                    is_enabled=True,
                )
                session.add(main_menu)
                session.flush()

            has_buttons = (
                session.query(BotButton)
                .filter(BotButton.node_id == main_menu.id)
                .count()
            )

            if not has_buttons:
                default_buttons = [
                    {
                        "title": "🛍 Товары",
                        "type": "callback",
                        "payload": "OPEN_NODE:PRODUCTS",
                        "row": 0,
                        "pos": 0,
                    },
                    {
                        "title": "🎓 Мастер-классы",
                        "type": "callback",
                        "payload": "OPEN_NODE:MASTERCLASSES",
                        "row": 0,
                        "pos": 1,
                    },
                    {
                        "title": "💬 Написать в чат",
                        "type": "url",
                        "payload": "https://t.me/miniden_chat",
                        "row": 1,
                        "pos": 0,
                    },
                    {
                        "title": "ℹ️ Помощь / Канал",
                        "type": "url",
                        "payload": "https://t.me/miniden_ru",
                        "row": 1,
                        "pos": 1,
                    },
                ]

                for button in default_buttons:
                    session.add(BotButton(node_id=main_menu.id, **button))

            existing_actions = {
                action.action_code
                for action in session.query(BotAction).all()
            }

            if "OPEN_NODE" not in existing_actions:
                session.add(
                    BotAction(
                        action_code="OPEN_NODE",
                        description="Открыть узел по его коду",
                        handler_type="open_node",
                    )
                )

            if "SEND_TEXT" not in existing_actions:
                session.add(
                    BotAction(
                        action_code="SEND_TEXT",
                        description="Отправить текстовое сообщение",
                        handler_type="send_text",
                    )
                )

    _ensure_bot_constructor_seed()

    if ADMIN_IDS_SET:
        with get_session() as session:
            for admin_id in ADMIN_IDS_SET:
                user = session.scalar(select(User).where(User.telegram_id == admin_id))
                if user:
                    if not user.is_admin:
                        user.is_admin = True
                else:
                    session.add(User(telegram_id=admin_id, is_admin=True))
