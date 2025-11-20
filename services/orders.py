from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from database import get_connection

# Статусы заказов
STATUS_NEW = "new"
STATUS_IN_PROGRESS = "in_progress"
STATUS_SENT = "sent"
STATUS_PAID = "paid"

STATUS_TITLES = {
    STATUS_NEW: "новый",
    STATUS_IN_PROGRESS: "в работе",
    STATUS_SENT: "отправлен",
    STATUS_PAID: "оплачен, доступ к курсам открыт",
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
    """Сохранить заказ в БД и вернуть его ID."""

    conn = get_connection()
    cur = conn.cursor()

    created_at = datetime.now().isoformat(timespec="seconds")

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
            STATUS_NEW,
            order_text,
            created_at,
        ),
    )

    order_id = cur.lastrowid

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


def _make_order_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "contact": row["contact"],
        "total": row["total"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def get_last_orders(limit: int = 10) -> list[dict[str, Any]]:
    """Вернуть последние заказы (без позиций)."""
    if limit <= 0:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, customer_name, contact, total, status, created_at
        FROM orders
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    return [_make_order_row(row) for row in rows]


def get_last_course_orders(limit: int = 20) -> list[dict[str, Any]]:
    """Последние заказы, в которых есть курсы."""
    if limit <= 0:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT o.id, o.customer_name, o.contact, o.total, o.status, o.created_at
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN products p ON p.id = oi.product_id
        WHERE p.type = 'course'
        ORDER BY o.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    return [_make_order_row(row) for row in rows]


def get_orders_by_user(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """Список заказов конкретного пользователя."""
    if limit <= 0:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, customer_name, contact, total, status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()

    return [_make_order_row(row) for row in rows]


def get_order_by_id(order_id: int) -> Optional[dict[str, Any]]:
    """Найти заказ по номеру и подтянуть позиции."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, user_name, customer_name, contact, comment, total, status, order_text, created_at
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
    """Установить статус заказа."""
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


def get_user_courses_with_access(user_id: int) -> list[dict[str, Any]]:
    """Курсы, к которым у пользователя открыт доступ (заказы со статусом paid)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT p.id, p.name, p.description, p.detail_url, p.image_file_id
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN products p ON p.id = oi.product_id
        WHERE o.user_id = ?
          AND o.status = ?
          AND p.type = 'course'
        ORDER BY p.id ASC
        """,
        (user_id, STATUS_PAID),
    )
    rows = cur.fetchall()
    conn.close()

    courses: list[dict[str, Any]] = []
    for row in rows:
        courses.append(
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "detail_url": row["detail_url"],
                "image_file_id": row["image_file_id"],
            }
        )

    return courses
