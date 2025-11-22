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
            promocode_code TEXT,
            discount_amount INTEGER,
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

    # 🔹 Добавляем новые колонки в orders, если их ещё нет
    cur.execute("PRAGMA table_info(orders);")
    orders_columns = [row["name"] for row in cur.fetchall()]
    if "promocode_code" not in orders_columns:
        cur.execute(
            """
            ALTER TABLE orders
            ADD COLUMN promocode_code TEXT;
            """
        )
    if "discount_amount" not in orders_columns:
        cur.execute(
            """
            ALTER TABLE orders
            ADD COLUMN discount_amount INTEGER;
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

    # Таблица категорий для товаров и курсов
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,       -- 'basket' или 'course'
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
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

    # 🔹 Добавляем колонку category_id и image_file_id, если их ещё нет
    cur.execute("PRAGMA table_info(products);")
    p_columns = [row["name"] for row in cur.fetchall()]
    if "category_id" not in p_columns:
        cur.execute(
            """
            ALTER TABLE products
            ADD COLUMN category_id INTEGER;
            """
        )

    # Обновляем список колонок, чтобы последующие проверки были актуальны
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

    # Таблица промокодов
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            discount_type TEXT NOT NULL,
            discount_value INTEGER NOT NULL,
            min_order_total INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 0,
            used_count INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            valid_from TEXT,
            valid_to TEXT,
            description TEXT
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
        CREATE INDEX IF NOT EXISTS idx_categories_type
        ON categories(type);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_products_category
        ON products(category_id);
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

    # Индексы для промокодов
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_promocodes_code
        ON promocodes(code);
        """
    )

    # Стартовые категории, если таблица пуста
    cur.execute("SELECT COUNT(*) AS cnt FROM categories;")
    cat_count = int(cur.fetchone()["cnt"])
    if cat_count == 0:
        start_categories = [
            ("basket", "baskets", "Корзинки", 1),
            ("basket", "cradles", "Люльки", 2),
            ("basket", "bags", "Сумки", 3),
            ("basket", "other", "Другое", 100),
            ("course", "free", "Бесплатные", 1),
            ("course", "paid", "Платные", 2),
        ]
        cur.executemany(
            """
            INSERT INTO categories (type, slug, name, sort_order)
            VALUES (?, ?, ?, ?);
            """,
            start_categories,
        )

    # Привязка существующих товаров к категориям, если category_id пустой
    cur.execute("SELECT id, type, price, category_id FROM products;")
    products_rows = cur.fetchall()
    cur.execute("SELECT id, type, slug FROM categories;")
    categories_map = {(row["type"], row["slug"]): row["id"] for row in cur.fetchall()}

    for row in products_rows:
        if row["category_id"]:
            continue

        slug = None
        if row["type"] == "basket":
            slug = "baskets"
        elif row["type"] == "course":
            price = int(row["price"] or 0)
            slug = "free" if price == 0 else "paid"

        if slug is None:
            continue

        cat_id = categories_map.get((row["type"], slug))
        if cat_id:
            cur.execute(
                """
                UPDATE products
                SET category_id = ?
                WHERE id = ? AND category_id IS NULL;
                """,
                (cat_id, row["id"]),
            )

    conn.commit()
    conn.close()
