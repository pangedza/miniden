import json
from pathlib import Path
from typing import Any

from database import get_connection

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

BASKETS_JSON = DATA_DIR / "products_baskets.json"
COURSES_JSON = DATA_DIR / "products_courses.json"


def _ensure_category_support() -> dict[tuple[str, str], int]:
    """
    Создаём таблицу категорий при необходимости и возвращаем карту {(type, slug): id}.

    Используется в сервисе, чтобы гарантировать наличие категорий даже
    если init_db() не был вызван ранее (например, при тестовом запуске).
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        """
    )

    # Добавляем колонку category_id в products, если её нет
    cur.execute("PRAGMA table_info(products);")
    columns = [row["name"] for row in cur.fetchall()]
    if "category_id" not in columns:
        cur.execute(
            """
            ALTER TABLE products
            ADD COLUMN category_id INTEGER;
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

    cur.execute("SELECT COUNT(*) AS cnt FROM categories;")
    total = int(cur.fetchone()["cnt"])
    if total == 0:
        cur.executemany(
            """
            INSERT INTO categories (type, slug, name, sort_order)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("basket", "baskets", "Корзинки", 1),
                ("basket", "cradles", "Люльки", 2),
                ("basket", "bags", "Сумки", 3),
                ("basket", "other", "Другое", 100),
                ("course", "free", "Бесплатные", 1),
                ("course", "paid", "Платные", 2),
            ],
        )

    cur.execute("SELECT id, type, slug FROM categories WHERE is_active = 1;")
    categories_map: dict[tuple[str, str], int] = {}
    for row in cur.fetchall():
        categories_map[(row["type"], row["slug"])] = row["id"]

    conn.commit()
    conn.close()
    return categories_map


def _load_json(path: Path) -> list[dict[str, Any]]:
    """
    Загрузить JSON-файл со списком товаров.
    Если файла нет или формат неверный — вернуть пустой список.
    """
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # Если JSON битый — просто не поднимаем товары из него
        return []

    if not isinstance(data, list):
        return []

    # Гарантируем, что каждый элемент — dict
    result: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            result.append(item)
    return result


def _init_products_table_if_needed() -> None:
    """
    Если таблица products пустая — заполняем её из JSON-файлов.

    ВАЖНО:
    - НЕТ глобального флага, который бы мешал переинициализации.
    - При каждом вызове делаем быстрый SELECT COUNT(*).
      Если товаров уже > 0 — просто выходим.
    """
    categories_map = _ensure_category_support()

    conn = get_connection()
    cur = conn.cursor()

    # Проверяем, есть ли уже хоть один продукт
    cur.execute("SELECT COUNT(*) AS cnt FROM products;")
    row = cur.fetchone()
    count = int(row["cnt"] if row is not None else 0)

    if count > 0:
        conn.close()
        return

    # Таблица пустая — пробуем загрузить стартовые данные из JSON
    baskets = _load_json(BASKETS_JSON)
    courses = _load_json(COURSES_JSON)

    # Корзинки
    for item in baskets:
        try:
            item_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue

        name = (item.get("name") or "").strip()
        if not name:
            continue

        price = int(item.get("price", 0))
        description = (item.get("description") or "").strip()
        detail_url = item.get("detail_url")

        cur.execute(
            """
            INSERT OR REPLACE INTO products (
                id, type, name, price, description, detail_url, is_active, image_file_id, category_id
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, NULL, ?)
            """,
            (
                item_id,
                "basket",
                name,
                price,
                description,
                detail_url,
                categories_map.get(("basket", "baskets")),
            ),
        )

    # Курсы
    for item in courses:
        try:
            item_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue

        name = (item.get("name") or "").strip()
        if not name:
            continue

        price = int(item.get("price", 0))
        description = (item.get("description") or "").strip()
        detail_url = item.get("detail_url")

        cur.execute(
            """
            INSERT OR REPLACE INTO products (
                id, type, name, price, description, detail_url, is_active, image_file_id, category_id
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, NULL, ?)
            """,
            (
                item_id,
                "course",
                name,
                price,
                description,
                detail_url,
                categories_map.get(("course", "free" if price == 0 else "paid")),
            ),
        )

    conn.commit()
    conn.close()


def _fetch_products_by_type(product_type: str) -> list[dict[str, Any]]:
    """
    Внутренняя функция: забрать продукты заданного типа из БД.
    """
    _init_products_table_if_needed()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, price, description, detail_url, image_file_id, is_active, type, category_id
        FROM products
        WHERE type = ?
        ORDER BY id ASC
        """,
        (product_type,),
    )
    rows = cur.fetchall()
    conn.close()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "price": row["price"],
                "description": row["description"] or "",
                "detail_url": row["detail_url"],
                "image_file_id": row["image_file_id"],
                "is_active": int(row["is_active"] or 0),
                "type": row["type"],
                "category_id": row["category_id"],
            }
        )
    return result


def _fetch_product_by_id(product_type: str, item_id: int) -> dict[str, Any] | None:
    _init_products_table_if_needed()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, price, description, detail_url, image_file_id, is_active, type, category_id
        FROM products
        WHERE type = ? AND id = ?
        LIMIT 1
        """,
        (product_type, item_id),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "price": row["price"],
        "description": row["description"] or "",
        "detail_url": row["detail_url"],
        "image_file_id": row["image_file_id"],
        "is_active": int(row["is_active"] or 0),
        "type": row["type"],
        "category_id": row["category_id"],
    }


# ---------- Публичные функции для каталога ----------


def get_baskets() -> list[dict[str, Any]]:
    """Список корзинок (из БД). Показываем только активные."""
    return [p for p in _fetch_products_by_type("basket") if p["is_active"] == 1]


def get_courses() -> list[dict[str, Any]]:
    """Список всех курсов (из БД). Показываем только активные."""
    return [p for p in _fetch_products_by_type("course") if p["is_active"] == 1]


def list_categories(product_type: str) -> list[dict[str, Any]]:
    """Активные категории для заданного типа товара."""

    _ensure_category_support()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, type, slug, name, sort_order
        FROM categories
        WHERE type = ? AND is_active = 1
        ORDER BY sort_order, name
        """,
        (product_type,),
    )
    rows = cur.fetchall()
    conn.close()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "type": row["type"],
                "slug": row["slug"],
                "name": row["name"],
                "sort_order": row["sort_order"],
            }
        )
    return result


def list_products_by_category(product_type: str, category_slug: str | None = None) -> list[dict[str, Any]]:
    """
    Возвращает активные товары по типу и категории.

    TODO: использовать в API фильтры каталога.
    """

    _init_products_table_if_needed()

    conn = get_connection()
    cur = conn.cursor()

    query = [
        "SELECT p.id, p.name, p.price, p.description, p.detail_url, p.image_file_id,",
        "p.is_active, p.type, p.category_id, c.slug",
        "FROM products p",
        "LEFT JOIN categories c ON c.id = p.category_id",
        "WHERE p.type = ? AND p.is_active = 1",
    ]
    params: list[Any] = [product_type]

    if category_slug:
        query.append("AND c.slug = ?")
        params.append(category_slug)

    query.append("ORDER BY p.id ASC")

    cur.execute("\n".join(query), tuple(params))
    rows = cur.fetchall()
    conn.close()

    products: list[dict[str, Any]] = []
    for row in rows:
        products.append(
            {
                "id": row["id"],
                "name": row["name"],
                "price": row["price"],
                "description": row["description"] or "",
                "detail_url": row["detail_url"],
                "image_file_id": row["image_file_id"],
                "is_active": int(row["is_active"] or 0),
                "type": row["type"],
                "category_id": row["category_id"],
                "category_slug": row["slug"],
            }
        )
    return products


def list_products(product_type: str, category_slug: str | None = None) -> list[dict[str, Any]]:
    """
    Возвращает активные товары по типу и опциональной категории.

    Используется API-слоем для выдачи каталога.
    """

    _init_products_table_if_needed()

    conn = get_connection()
    cur = conn.cursor()

    query = [
        "SELECT p.id, p.name, p.price, p.description, p.detail_url, p.image_file_id,",
        "p.is_active, p.type, p.category_id, c.slug AS category_slug, c.name AS category_name",
        "FROM products p",
        "LEFT JOIN categories c ON c.id = p.category_id",
        "WHERE p.type = ? AND p.is_active = 1",
    ]
    params: list[Any] = [product_type]

    if category_slug:
        query.append("AND c.slug = ?")
        params.append(category_slug)

    query.append("ORDER BY c.sort_order, p.id ASC")

    cur.execute("\n".join(query), tuple(params))
    rows = cur.fetchall()
    conn.close()

    products: list[dict[str, Any]] = []
    for row in rows:
        products.append(
            {
                "id": row["id"],
                "name": row["name"],
                "price": row["price"],
                "description": row["description"] or "",
                "detail_url": row["detail_url"],
                "image_file_id": row["image_file_id"],
                "is_active": int(row["is_active"] or 0),
                "type": row["type"],
                "category_id": row["category_id"],
                "category_slug": row["category_slug"],
                "category_name": row["category_name"],
            }
        )
    return products


def get_product_with_category(product_id: int) -> dict[str, Any] | None:
    """Получить активный товар по ID вместе с категорией."""

    _init_products_table_if_needed()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.id, p.name, p.price, p.description, p.detail_url, p.image_file_id, p.is_active, p.type,
               p.category_id, c.slug AS category_slug, c.name AS category_name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.id = ? AND p.is_active = 1
        LIMIT 1
        """,
        (product_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "price": row["price"],
        "description": row["description"] or "",
        "detail_url": row["detail_url"],
        "image_file_id": row["image_file_id"],
        "is_active": int(row["is_active"] or 0),
        "type": row["type"],
        "category_id": row["category_id"],
        "category_slug": row["category_slug"],
        "category_name": row["category_name"],
    }


def get_free_courses() -> list[dict[str, Any]]:
    """Список бесплатных курсов (price = 0)."""

    return [
        p for p in get_courses() if int(p.get("price", 0) or 0) == 0
    ]


def get_paid_courses() -> list[dict[str, Any]]:
    """Список платных курсов (price > 0)."""

    return [
        p for p in get_courses() if int(p.get("price", 0) or 0) > 0
    ]


def get_basket_by_id(item_id: int) -> dict[str, Any] | None:
    """Найти корзинку по ID (в БД)."""
    prod = _fetch_product_by_id("basket", item_id)
    if prod and prod["is_active"] == 1:
        return prod
    return None


def get_course_by_id(item_id: int) -> dict[str, Any] | None:
    """Найти курс по ID (в БД)."""
    prod = _fetch_product_by_id("course", item_id)
    if prod and prod["is_active"] == 1:
        return prod
    return None


# ---------- Общий доступ по ID (для админки) ----------


def get_product_by_id(product_id: int) -> dict[str, Any] | None:
    """
    Найти товар по ID независимо от типа.
    (Используется в админке и сервисах.)
    """
    _init_products_table_if_needed()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, type, name, price, description, detail_url, image_file_id, is_active
        FROM products
        WHERE id = ?
        LIMIT 1
        """,
        (product_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": row["id"],
        "type": row["type"],
        "name": row["name"],
        "price": row["price"],
        "description": row["description"] or "",
        "detail_url": row["detail_url"],
        "image_file_id": row["image_file_id"],
        "is_active": int(row["is_active"] or 0),
    }


# ---------- Создание товара из админки ----------


def create_product(
    product_type: str,
    name: str,
    price: int,
    description: str = "",
    detail_url: str | None = None,
    image_file_id: str | None = None,
    category_id: int | None = None,
) -> int:
    """
    Добавить новый товар в БД (корзинка или курс).
    product_type: 'basket' или 'course'
    Возвращает ID созданного товара.
    """
    _init_products_table_if_needed()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO products (
            type, name, price, description, detail_url, image_file_id, is_active, category_id
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (product_type, name, price, description, detail_url, image_file_id, category_id),
    )
    product_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(product_id)


# ---------- Сервис для админки: списки/редактирование ----------


def list_products(product_type: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    Список товаров указанного типа (включая скрытые).
    """
    products = _fetch_products_by_type(product_type)
    return products[:limit]


def list_products_by_status(
    product_type: str,
    status: str = "all",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Список товаров указанного типа с фильтром по статусу.

    status:
        - "all"     — все (и активные, и скрытые)
        - "active"  — только активные (is_active = 1)
        - "hidden"  — только скрытые/удалённые (is_active = 0)
        - "deleted" — считаем как скрытые (для удобства, синоним)
    """
    products = _fetch_products_by_type(product_type)

    status = (status or "all").lower()

    if status == "active":
        filtered = [p for p in products if p.get("is_active") == 1]
    elif status in ("hidden", "inactive", "deleted"):
        filtered = [p for p in products if p.get("is_active") == 0]
    else:
        # "all" — без фильтра
        filtered = products

    return filtered[:limit]


def soft_delete_product(product_id: int) -> bool:
    """
    "Удалить" товар — сделать его неактивным (is_active = 0).
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET is_active = 0
        WHERE id = ?
        """,
        (product_id,),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def toggle_product_active(product_id: int) -> bool:
    """
    Переключить статус is_active: 1 -> 0, 0 -> 1.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET is_active = CASE is_active WHEN 1 THEN 0 ELSE 1 END
        WHERE id = ?
        """,
        (product_id,),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def update_product_price(product_id: int, price: int) -> bool:
    """
    Изменить цену товара.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET price = ?
        WHERE id = ?
        """,
        (price, product_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def update_product_name(product_id: int, name: str) -> bool:
    """
    Изменить название товара.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET name = ?
        WHERE id = ?
        """,
        (name, product_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def update_product_description(product_id: int, description: str) -> bool:
    """
    Изменить описание товара.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET description = ?
        WHERE id = ?
        """,
        (description, product_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def update_product_detail_url(product_id: int, detail_url: str | None) -> bool:
    """
    Изменить ссылку «Подробнее».
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET detail_url = ?
        WHERE id = ?
        """,
        (detail_url, product_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def update_product_image(product_id: int, image_file_id: str | None) -> bool:
    """
    Изменить file_id картинки товара.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET image_file_id = ?
        WHERE id = ?
        """,
        (image_file_id, product_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated
