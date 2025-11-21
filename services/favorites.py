import sqlite3
from datetime import datetime
from typing import List

from database import get_connection


def add_favorite(user_id: int, product_id: int) -> bool:
    """Добавить товар в избранное. Возвращает True, если вставка успешна."""

    conn = get_connection()
    cur = conn.cursor()
    created_at = datetime.now().isoformat()

    try:
        cur.execute(
            """
            INSERT INTO favorites (user_id, product_id, created_at)
            VALUES (?, ?, ?);
            """,
            (user_id, product_id, created_at),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_favorite(user_id: int, product_id: int) -> bool:
    """Удалить товар из избранного. Возвращает True, если запись удалена."""

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DELETE FROM favorites
            WHERE user_id = ? AND product_id = ?;
            """,
            (user_id, product_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def is_favorite(user_id: int, product_id: int) -> bool:
    """Проверить, находится ли товар в избранном у пользователя."""

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM favorites
        WHERE user_id = ? AND product_id = ?
        LIMIT 1;
        """,
        (user_id, product_id),
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_user_favorites(user_id: int) -> List[dict]:
    """Вернуть список избранных товаров пользователя (с данными продукта)."""

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            p.id,
            p.name,
            p.price,
            p.description,
            p.type,
            p.image_file_id,
            p.detail_url,
            p.is_active
        FROM favorites f
        JOIN products p ON p.id = f.product_id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC;
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    favorites: List[dict] = []
    for row in rows:
        favorites.append(
            {
                "id": row["id"],
                "name": row["name"],
                "price": row["price"],
                "description": row["description"] or "",
                "type": row["type"],
                "image_file_id": row["image_file_id"],
                "detail_url": row["detail_url"],
                "is_active": int(row["is_active"] or 0),
            }
        )

    return favorites
