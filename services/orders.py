from typing import Any, Optional
from datetime import datetime

from database import get_connection

# Статусы заказов
STATUS_NEW = "new"
STATUS_IN_PROGRESS = "in_progress"
STATUS_SENT = "sent"

STATUS_TITLES = {
    STATUS_NEW: "новый",
    STATUS_IN_PROGRESS: "в работе",
    STATUS_SENT: "отправлен",
}


def add_order(
    user_id: int,
    user_name: str,
    items: list[dict[str, Any]],
    total: int,
    customer_name: str,
    contact: str,
    comment: str,
    order_text: str,
) -> int:
    """
    Сохранить заказ в БД и вернуть его ID.

    items — список словарей, пришедший из корзины:
        {
            "product_id": "1" (строка с int),
            "name": "Название",
            "price": 1000,
            "qty": 2,
        }

    Теперь мы дополнительно сохраняем product_id в таблицу order_items.
    """
    conn = get_connection()
    cur = conn.cursor()

    created_at = datetime.now().isoformat(timespec="seconds")

    # Вставляем сам заказ
    cur.execute(
        """
        INSERT INTO orders (
            user_id, user_name,
            customer_name, contact, comment,
            total, status, order_text, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            user_name,
            customer_name,
            contact,
            comment,
            total,
            STATUS_NEW,  # новый заказ
            order_text,
            created_at,
        ),
    )

    order_id = cur.lastrowid

    # Вставляем позиции заказа
    for item in items:
        name = item.get("name", "Товар")
        price = int(item.get("price", 0))
        qty = int(item.get("qty", 0))

        raw_pid = item.get("product_id")
        try:
            product_id = int(raw_pid) if raw_pid is not None else None
        except (TypeError, ValueError):
            product_id = None

        cur.execute(
            """
            INSERT INTO order_items (order_id, product_id, product_name, price, qty)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, product_id, name, price, qty),
        )

    conn.commit()
    conn.close()

    return int(order_id)


def get_last_orders(limit: int = 10) -> list[dict[str, Any]]:
    """
    Вернуть последние заказы (без позиций, только заголовки).
    Используется для /orders.
    """
    if limit <= 0:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id,
            customer_name,
            contact,
            total,
            status,
            created_at
        FROM orders
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "customer_name": row["customer_name"],
                "contact": row["contact"],
                "total": row["total"],
                "status": row["status"],
                "created_at": row["created_at"],
            }
        )

    return result


def get_orders_by_user(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """
    Список заказов конкретного пользователя (для профиля).

    Возвращаем только "заголовки" заказов без позиций.
    """
    if limit <= 0:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id,
            customer_name,
            contact,
            total,
            status,
            created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "customer_name": row["customer_name"],
                "contact": row["contact"],
                "total": row["total"],
                "status": row["status"],
                "created_at": row["created_at"],
            }
        )

    return result


def get_order_by_id(order_id: int) -> Optional[dict[str, Any]]:
    """
    Найти заказ по номеру и подтянуть его позиции.
    Используется для /order <id>.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Сам заказ
    cur.execute(
        """
        SELECT
            id,
            user_id,
            user_name,
            customer_name,
            contact,
            comment,
            total,
            status,
            order_text,
            created_at
        FROM orders
        WHERE id = ?
        """,
        (order_id,),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        return None

    order: dict[str, Any] = {
        "id": row["id"],
        "user_id": row["user_id"],
        "user_name": row["user_name"],
        "customer_name": row["customer_name"],
        "contact": row["contact"],
        "comment": row["comment"],
        "total": row["total"],
        "status": row["status"],
        "order_text": row["order_text"],
        "created_at": row["created_at"],
    }

    # Позиции этого заказа
    cur.execute(
        """
        SELECT product_id, product_name, price, qty
        FROM order_items
        WHERE order_id = ?
        """,
        (order_id,),
    )
    item_rows = cur.fetchall()
    conn.close()

    items: list[dict[str, Any]] = []
    for item in item_rows:
        price = int(item["price"] or 0)
        qty = int(item["qty"] or 0)
        items.append(
            {
                "product_id": item["product_id"],
                "name": item["product_name"],
                "price": price,
                "qty": qty,
            }
        )

    order["items"] = items
    return order


def set_order_status(order_id: int, new_status: str) -> bool:
    """
    Установить статус заказа. Возвращает True,
    если заказ найден и статус изменён.
    """
    if new_status not in STATUS_TITLES:
        return False

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE orders
        SET status = ?
        WHERE id = ?
        """,
        (new_status, order_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated
