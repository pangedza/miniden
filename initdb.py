"""
Инициализация базы данных и миграции без Alembic.
Вызывается вручную или при dev-запуске.
"""

from __future__ import annotations

from sqlalchemy import select, text, func, or_

from config import ADMIN_IDS_SET
from database import SessionLocal, engine, get_session
from models import HomeBanner, User
from models import (
    BotAction,
    BotButton,
    BotEventTrigger,
    BotNode,
    BotRuntime,
    BotTemplate,
    BotTrigger,
)
from utils.home_images import HOME_PLACEHOLDER_URL


def init_db() -> None:
    from models import Base  # noqa: WPS433

    Base.metadata.create_all(bind=engine)

    def _ensure_optional_columns() -> None:
        """Добавить недостающие колонки без разрушения существующей схемы."""

        alter_statements = [
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS wb_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS ozon_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS yandex_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS avito_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS stock INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS masterclass_url TEXT",
            "ALTER TABLE products_baskets ADD COLUMN IF NOT EXISTS short_description TEXT",
            "ALTER TABLE products_courses ADD COLUMN IF NOT EXISTS short_description TEXT",
            "ALTER TABLE products_courses ADD COLUMN IF NOT EXISTS stock INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE products_courses ADD COLUMN IF NOT EXISTS masterclass_url TEXT",
            "ALTER TABLE product_reviews ADD COLUMN IF NOT EXISTS masterclass_id INTEGER",
            "ALTER TABLE product_reviews ALTER COLUMN product_id DROP NOT NULL",
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS page_id INTEGER",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS session_key VARCHAR(64)",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS user_identifier TEXT",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS client_ip VARCHAR(64)",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMP",
            "ALTER TABLE webchat_sessions ADD COLUMN IF NOT EXISTS unread_for_manager INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE webchat_messages ADD COLUMN IF NOT EXISTS is_read_by_manager BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE webchat_messages ADD COLUMN IF NOT EXISTS is_read_by_client BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE adminsite_items ADD COLUMN IF NOT EXISTS stock INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE adminsite_pages ADD COLUMN IF NOT EXISTS theme JSONB DEFAULT '{}'",
            "ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS image_url TEXT",
            "ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS type VARCHAR(32) NOT NULL DEFAULT 'product'",
            "ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS parent_id INTEGER",
            "ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS legacy_link TEXT",
            "ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS stock_qty INTEGER",
            "ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS hero_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE cart_items ADD COLUMN IF NOT EXISTS session_id VARCHAR(64)",
            "ALTER TABLE cart_items ALTER COLUMN user_id DROP NOT NULL",
        ]

        with engine.begin() as conn:
            for statement in alter_statements:
                conn.execute(text(statement))

            conn.execute(
                text("ALTER TABLE menu_items DROP CONSTRAINT IF EXISTS ck_menu_items_type")
            )
            conn.execute(
                text(
                    "ALTER TABLE menu_items ADD CONSTRAINT ck_menu_items_type "
                    "CHECK (type IN ('product', 'course', 'service', 'masterclass'))"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE menu_categories DROP CONSTRAINT IF EXISTS ck_menu_categories_type"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE menu_categories ADD CONSTRAINT ck_menu_categories_type "
                    "CHECK (type IN ('product', 'masterclass'))"
                )
            )

            conn.execute(text("UPDATE menu_categories SET type='product' WHERE type IS NULL"))

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

            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_menu_categories_parent_id "
                    "ON menu_categories(parent_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_menu_categories_type "
                    "ON menu_categories(type)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_menu_items_category_id "
                    "ON menu_items(category_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_cart_items_session_id "
                    "ON cart_items(session_id)"
                )
            )

    _ensure_optional_columns()

    def _seed_menu_back_compat_categories() -> None:
        from models import MenuCategory  # noqa: WPS433

        seed_map = {
            "korzinki": "Корзинки",
            "basket": "Basket",
            "cradle": "Cradle",
            "set": "Set",
        }
        with SessionLocal() as session:
            existing = (
                session.query(MenuCategory)
                .filter(MenuCategory.slug.in_(list(seed_map.keys())))
                .all()
            )
            existing_slugs = {category.slug for category in existing}
            max_order = session.query(func.max(MenuCategory.order_index)).scalar() or 0
            order_offset = 1
            for slug, title in seed_map.items():
                if slug in existing_slugs:
                    continue
                category = MenuCategory(
                    title=title,
                    slug=slug,
                    description=None,
                    order_index=int(max_order) + order_offset,
                    is_active=True,
                )
                session.add(category)
                order_offset += 1
            session.commit()

    _seed_menu_back_compat_categories()

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
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS cond_var_key VARCHAR",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS cond_operator VARCHAR",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS cond_value TEXT",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS next_node_code_true VARCHAR",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS next_node_code_false VARCHAR",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS next_node_code VARCHAR",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS config_json JSONB",
            "ALTER TABLE bot_nodes ADD COLUMN IF NOT EXISTS clear_chat BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE user_state ADD COLUMN IF NOT EXISTS bot_message_ids JSONB",
            "ALTER TABLE user_state ADD COLUMN IF NOT EXISTS current_node_code VARCHAR",
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
            current_node_code VARCHAR NULL,
            waiting_node_code VARCHAR NULL,
            waiting_input_type VARCHAR NULL,
            waiting_var_key VARCHAR NULL,
            next_node_code_success VARCHAR NULL,
            next_node_code_cancel VARCHAR NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        create_bot_node_actions = """
        CREATE TABLE IF NOT EXISTS bot_node_actions (
            id BIGSERIAL PRIMARY KEY,
            node_code VARCHAR(64) NOT NULL,
            action_type VARCHAR(32) NOT NULL,
            action_payload JSONB NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE
        );
        """

        create_user_tags = """
        CREATE TABLE IF NOT EXISTS user_tags (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            tag VARCHAR(64) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        create_user_tags_index = """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_user_tags_user_tag
            ON user_tags (user_id, tag);
        """

        with engine.begin() as conn:
            for statement in alter_statements:
                conn.execute(text(statement))

            conn.execute(text(create_user_vars))
            conn.execute(text(create_user_vars_index))
            conn.execute(text(create_user_state))
            conn.execute(text(create_bot_node_actions))
            conn.execute(text(create_user_tags))
            conn.execute(text(create_user_tags_index))

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

    def _ensure_bot_buttons_extensions() -> None:
        """Расширение кнопок для действий NODE/URL/WebApp."""

        alter_statements = [
            "ALTER TABLE bot_buttons ADD COLUMN IF NOT EXISTS action_type VARCHAR(16) NOT NULL DEFAULT 'NODE'",
            "ALTER TABLE bot_buttons ADD COLUMN IF NOT EXISTS target_node_code VARCHAR(64)",
            "ALTER TABLE bot_buttons ADD COLUMN IF NOT EXISTS url TEXT",
            "ALTER TABLE bot_buttons ADD COLUMN IF NOT EXISTS webapp_url TEXT",
            "ALTER TABLE bot_buttons ADD COLUMN IF NOT EXISTS render VARCHAR(16) NOT NULL DEFAULT 'INLINE'",
            "ALTER TABLE bot_buttons ADD COLUMN IF NOT EXISTS action_payload TEXT",
        ]

        with engine.begin() as conn:
            for statement in alter_statements:
                conn.execute(text(statement))

            conn.execute(
                text(
                    """
                    UPDATE bot_buttons
                    SET action_type = CASE
                        WHEN COALESCE(action_type, '') = '' THEN
                            CASE
                                WHEN type = 'url' THEN 'URL'
                                WHEN type = 'webapp' THEN 'WEBAPP'
                                WHEN type = 'callback' AND payload NOT LIKE 'OPEN_NODE:%' THEN 'LEGACY'
                                ELSE 'NODE'
                            END
                        ELSE action_type
                    END,
                    target_node_code = CASE
                        WHEN COALESCE(target_node_code, '') = '' AND type = 'callback' AND payload LIKE 'OPEN_NODE:%' THEN split_part(payload, ':', 2)
                        ELSE target_node_code
                    END,
                    url = CASE WHEN url IS NULL AND type = 'url' THEN payload ELSE url END,
                    webapp_url = CASE WHEN webapp_url IS NULL AND type = 'webapp' THEN payload ELSE webapp_url END
                    """
                )
            )

    _ensure_bot_buttons_extensions()

    def _drop_adminsite_webapp_settings() -> None:
        """Удаление устаревшей таблицы настроек WebApp-кнопки AdminSite."""

        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS adminsite_webapp_settings"))

    _drop_adminsite_webapp_settings()

    def _ensure_bot_runtime_settings() -> None:
        alter_statements = [
            "ALTER TABLE bot_runtime ADD COLUMN IF NOT EXISTS start_node_code VARCHAR(64)",
        ]

        create_bot_settings = """
        CREATE TABLE IF NOT EXISTS bot_settings (
            key VARCHAR(64) PRIMARY KEY,
            value TEXT
        );
        """

        with engine.begin() as conn:
            for statement in alter_statements:
                conn.execute(text(statement))

            conn.execute(text(create_bot_settings))

    _ensure_bot_runtime_settings()

    def _seed_bot_triggers() -> None:
        with SessionLocal() as session:
            existing = {
                (trigger.trigger_type or "", (trigger.trigger_value or "").strip()): trigger
                for trigger in session.query(BotTrigger).all()
            }

            seeds = [
                {
                    "trigger_type": "COMMAND",
                    "trigger_value": "start",
                    "match_mode": "EXACT",
                    "target_node_code": "MAIN_MENU",
                    "priority": 1,
                },
                {
                    "trigger_type": "FALLBACK",
                    "trigger_value": None,
                    "match_mode": "EXACT",
                    "target_node_code": "MAIN_MENU",
                    "priority": 9999,
                },
            ]

            for seed in seeds:
                lookup_key = (seed["trigger_type"], (seed.get("trigger_value") or "").strip())
                if lookup_key in existing:
                    continue

                session.add(
                    BotTrigger(
                        trigger_type=seed["trigger_type"],
                        trigger_value=seed.get("trigger_value"),
                        match_mode=seed.get("match_mode", "EXACT"),
                        target_node_code=seed["target_node_code"],
                        priority=seed.get("priority", 100),
                        is_enabled=True,
                    )
                )
            session.commit()

    _seed_bot_triggers()

    def _seed_bot_event_triggers() -> None:
        with SessionLocal() as session:
            existing = (
                session.query(BotEventTrigger)
                .filter(BotEventTrigger.event_code == "webapp_checkout_created")
                .first()
            )
            if existing:
                return

            session.add(
                BotEventTrigger(
                    event_code="webapp_checkout_created",
                    title="Заказ из WebApp",
                    message_template=(
                        "🛒 Новый заказ из витрины\n"
                        "Вы выбрали:\n"
                        "{items}\n"
                        "Итого: {qty_total} шт, {sum_total} {currency}"
                    ),
                    buttons_json=[
                        {
                            "title": "Связаться",
                            "type": "callback",
                            "value": "trigger:contact_manager",
                            "row": 0,
                        },
                        {
                            "title": "Открыть витрину",
                            "type": "url",
                            "value": "{webapp_url}",
                            "row": 1,
                        },
                    ],
                    is_enabled=True,
                )
            )
            session.commit()

    _seed_bot_event_triggers()

    def _ensure_bot_templates_table() -> None:
        create_table = """
        CREATE TABLE IF NOT EXISTS bot_templates (
            id BIGSERIAL PRIMARY KEY,
            code VARCHAR(64) UNIQUE NOT NULL,
            title VARCHAR(128) NOT NULL,
            description TEXT NULL,
            template_json JSONB NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """

        alter_statements = [
            "ALTER TABLE bot_templates ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE bot_templates ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()",
        ]

        with engine.begin() as conn:
            conn.execute(text(create_table))
            for statement in alter_statements:
                conn.execute(text(statement))

    _ensure_bot_templates_table()

    def _seed_bot_templates() -> None:
        from services.bot_templates import STARTER_TEMPLATES

        with SessionLocal() as session:
            existing_codes = {
                code for (code,) in session.query(BotTemplate.code).all() if code
            }

            for template in STARTER_TEMPLATES:
                if template.get("code") in existing_codes:
                    continue

                session.add(
                    BotTemplate(
                        code=template.get("code"),
                        title=template.get("title") or template.get("code"),
                        description=template.get("description"),
                        template_json=template.get("template_json") or {},
                    )
                )

            session.commit()

    _seed_bot_templates()

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

        create_admin_roles = """
        CREATE TABLE IF NOT EXISTS admin_roles (
            id BIGSERIAL PRIMARY KEY,
            code VARCHAR(32) UNIQUE NOT NULL,
            title VARCHAR(64) NOT NULL,
            description TEXT NULL
        );
        """

        create_admin_permissions = """
        CREATE TABLE IF NOT EXISTS admin_permissions (
            id BIGSERIAL PRIMARY KEY,
            code VARCHAR(64) UNIQUE NOT NULL,
            title VARCHAR(128) NOT NULL,
            description TEXT NULL
        );
        """

        create_admin_user_roles = """
        CREATE TABLE IF NOT EXISTS admin_user_roles (
            user_id BIGINT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
            role_id BIGINT NOT NULL REFERENCES admin_roles(id) ON DELETE CASCADE,
            CONSTRAINT uq_admin_user_role UNIQUE (user_id, role_id)
        );
        """

        create_admin_role_permissions = """
        CREATE TABLE IF NOT EXISTS admin_role_permissions (
            role_id BIGINT NOT NULL REFERENCES admin_roles(id) ON DELETE CASCADE,
            permission_id BIGINT NOT NULL REFERENCES admin_permissions(id) ON DELETE CASCADE,
            CONSTRAINT uq_admin_role_permission UNIQUE (role_id, permission_id)
        );
        """

        alter_statements = [
            "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()",
            "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS password_hash TEXT",
            "ALTER TABLE admin_users ALTER COLUMN role SET DEFAULT 'superadmin'",
            "ALTER TABLE admin_sessions ALTER COLUMN app SET DEFAULT 'admin'",
            "ALTER TABLE admin_users DROP CONSTRAINT IF EXISTS ck_admin_users_role",
            "ALTER TABLE admin_users ADD CONSTRAINT ck_admin_users_role CHECK (role IN ('superadmin','admin_bot','admin_site','moderator','viewer'))",
        ]

        with engine.begin() as conn:
            conn.execute(text(create_admin_users))
            conn.execute(text(create_admin_sessions))
            conn.execute(text(create_admin_roles))
            conn.execute(text(create_admin_permissions))
            conn.execute(text(create_admin_user_roles))
            conn.execute(text(create_admin_role_permissions))
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

    def _seed_admin_roles_and_permissions() -> None:
        from models import AdminPermission, AdminRoleModel, AdminRolePermission, AdminUser, AdminUserRole

        role_seed = [
            {
                "code": "superadmin",
                "title": "Суперадмин",
                "description": "Полный доступ ко всем функциям",
            },
            {
                "code": "admin_bot",
                "title": "Админ бота",
                "description": "Управление конструктором бота (узлы, кнопки, триггеры)",
            },
            {
                "code": "moderator",
                "title": "Модератор",
                "description": "Может просматривать и редактировать контент/узлы, но без системных настроек",
            },
            {
                "code": "viewer",
                "title": "Только просмотр",
                "description": "Только просмотр, без изменений",
            },
        ]

        permissions_seed = [
            {
                "code": "admins.manage",
                "title": "Управление администраторами",
                "description": "Создание/редактирование/блокировка админов",
            },
            {
                "code": "nodes.read",
                "title": "Просмотр узлов",
                "description": "Просмотр сценариев",
            },
            {
                "code": "nodes.write",
                "title": "Редактирование узлов",
                "description": "Создание/изменение узлов",
            },
            {
                "code": "buttons.write",
                "title": "Редактирование кнопок",
                "description": "Создание/изменение кнопок",
            },
            {
                "code": "triggers.write",
                "title": "Редактирование триггеров",
                "description": "Создание/изменение триггеров",
            },
            {
                "code": "logs.read",
                "title": "Просмотр логов",
                "description": "Доступ к странице логов",
            },
        ]

        role_permissions_map = {
            "superadmin": [perm["code"] for perm in permissions_seed],
            "admin_bot": [
                "nodes.read",
                "nodes.write",
                "buttons.write",
                "triggers.write",
                "logs.read",
            ],
            "moderator": [
                "nodes.read",
                "nodes.write",
                "buttons.write",
                "logs.read",
            ],
            "viewer": ["nodes.read", "logs.read"],
        }

        with SessionLocal() as session:
            existing_roles = {
                role.code: role for role in session.query(AdminRoleModel).all()
            }
            for role_data in role_seed:
                role = existing_roles.get(role_data["code"])
                if not role:
                    role = AdminRoleModel(**role_data)
                    session.add(role)
                else:
                    role.title = role_data["title"]
                    role.description = role_data["description"]
                existing_roles[role.code] = role

            existing_perms = {
                perm.code: perm for perm in session.query(AdminPermission).all()
            }
            for perm_data in permissions_seed:
                perm = existing_perms.get(perm_data["code"])
                if not perm:
                    perm = AdminPermission(**perm_data)
                    session.add(perm)
                else:
                    perm.title = perm_data["title"]
                    perm.description = perm_data["description"]
                existing_perms[perm.code] = perm

            session.flush()

            for role_code, perm_codes in role_permissions_map.items():
                role = existing_roles.get(role_code)
                if not role:
                    continue
                attached_codes = {perm.code for perm in role.permissions}
                for code in perm_codes:
                    perm = existing_perms.get(code)
                    if perm and perm.code not in attached_codes:
                        session.add(
                            AdminRolePermission(role_id=role.id, permission_id=perm.id)
                        )

            session.commit()

            # Автоматически проставляем роли существующим пользователям
            default_superadmin = existing_roles.get("superadmin")
            if default_superadmin:
                for user in session.query(AdminUser).all():
                    if user.roles:
                        continue
                    role_code = user.role or "superadmin"
                    role = existing_roles.get(role_code, default_superadmin)
                    if role:
                        session.add(
                            AdminUserRole(user_id=user.id, role_id=role.id)
                        )
                session.commit()

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
    _seed_admin_roles_and_permissions()

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

    def _ensure_logs_node_buttons() -> None:
        with get_session() as session:
            logs_node = (
                session.query(BotNode)
                .filter(
                    or_(
                        BotNode.title.ilike("логи"),
                        BotNode.title.ilike("работа бота"),
                        BotNode.code.in_(["LOGS", "BOT_LOGS", "BOT_RUNTIME"]),
                    )
                )
                .order_by(BotNode.id.asc())
                .first()
            )

            if not logs_node:
                return

            existing_buttons = (
                session.query(BotButton)
                .filter(BotButton.node_id == logs_node.id)
                .all()
            )
            existing_titles = {(btn.title or "").strip() for btn in existing_buttons}

            base_row = (
                session.query(func.coalesce(func.max(BotButton.row), 0))
                .filter(BotButton.node_id == logs_node.id)
                .scalar()
                or 0
            )
            desired_buttons: list[dict[str, object]] = []

            added = False
            for item in desired_buttons:
                if item["title"] in existing_titles:
                    continue

                session.add(
                    BotButton(
                        node_id=logs_node.id,
                        title=item["title"],
                        type="callback",
                        payload="",
                        render="INLINE",
                        action_type=item["action_type"],
                        action_payload=None,
                        target_node_code=None,
                        url=None,
                        webapp_url=None,
                        row=base_row + 1,
                        pos=item["pos"],
                        is_enabled=True,
                    )
                )
                added = True

            if added:
                runtime = session.query(BotRuntime).first()
                if not runtime:
                    runtime = BotRuntime(config_version=1, start_node_code="MAIN_MENU")
                runtime.config_version = (runtime.config_version or 1) + 1
                session.add(runtime)
                session.commit()

    _ensure_logs_node_buttons()

    if ADMIN_IDS_SET:
        with get_session() as session:
            for admin_id in ADMIN_IDS_SET:
                user = session.scalar(select(User).where(User.telegram_id == admin_id))
                if user:
                    if not user.is_admin:
                        user.is_admin = True
                else:
                    session.add(User(telegram_id=admin_id, is_admin=True))
