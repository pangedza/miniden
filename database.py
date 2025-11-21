import sqlite3
from pathlib import Path

# Путь к БД: data/bot.db
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "bot.db"


def get_connection() -> sqlite3.Connection:
    """
    Открыть соединение с БД.
    row_factory настроен на dict-подобный доступ: row["column_name"].
    ВАЖНО: включаем поддержку внешних ключей (FOREIGN KEY).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Включаем поддержку внешних ключей для КАЖДОГО нового соединения.
    # Иначе ON DELETE CASCADE и другие ограничения работать не будут.
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def init_db() -> None:
    """
    Создать таблицы, если их ещё нет, и добавить недостающие колонки.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Таблица заказов
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            customer_name TEXT,
            contact TEXT,
            comment TEXT,
            total INTEGER,
            status TEXT,
            order_text TEXT,
            created_at TEXT
        );
        """
    )

    # Таблица позиций в заказе
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT,
            price INTEGER,
            qty INTEGER,
            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
        );
        """
    )

    # 🔹 Добавляем колонку product_id, если её нет (для старых БД)
    cur.execute("PRAGMA table_info(order_items);")
    oi_columns = [row["name"] for row in cur.fetchall()]
    if "product_id" not in oi_columns:
        cur.execute(
            """
            ALTER TABLE order_items
            ADD COLUMN product_id INTEGER;
            """
        )

    # Таблица корзины
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cart_items (
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            name TEXT,
            price INTEGER,
            qty INTEGER,
            PRIMARY KEY (user_id, product_id)
        );
        """
    )

    # Таблица продуктов (корзинки + курсы)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            type TEXT NOT NULL,          -- 'basket' или 'course'
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT,
            detail_url TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        """
    )

    # Таблица избранного
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    # Таблица ручного управления доступом к курсам
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            source_order_id INTEGER NULL,
            granted_by INTEGER NULL,
            granted_at TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            comment TEXT NULL,
            FOREIGN KEY (course_id) REFERENCES products (id),
            FOREIGN KEY (source_order_id) REFERENCES orders (id)
        );
        """
    )

    # 🔹 Добавляем колонку image_file_id, если её ещё нет
    cur.execute("PRAGMA table_info(products);")
    p_columns = [row["name"] for row in cur.fetchall()]
    if "image_file_id" not in p_columns:
        cur.execute(
            """
            ALTER TABLE products
            ADD COLUMN image_file_id TEXT;
            """
    )

    # Таблица статуса пользователя (бан/разбан)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_status (
            user_id INTEGER PRIMARY KEY,
            is_banned INTEGER NOT NULL DEFAULT 0,
            ban_reason TEXT,
            updated_at TEXT,
            updated_by INTEGER
        );
        """
    )

    # Таблица заметок по пользователям
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT
        );
        """
    )

    # Индексы для ускорения запросов
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cart_items_user
        ON cart_items (user_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orders_user
        ON orders (user_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orders_created_at
        ON orders (created_at);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_products_type_active
        ON products (type, is_active);
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_courses_unique
        ON user_courses (user_id, course_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_notes_user
        ON user_notes(user_id);
        """
    )

    # Индексы для избранного
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_user_product
        ON favorites (user_id, product_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_favorites_user
        ON favorites (user_id);
        """
    )

    conn.commit()
    conn.close()
