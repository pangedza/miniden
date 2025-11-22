from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from database import get_connection
from services import products as products_service

# Статусы заказов
STATUS_NEW = "new"
STATUS_IN_PROGRESS = "in_progress"
STATUS_PAID = "paid"
STATUS_SENT = "sent"
STATUS_ARCHIVED = "archived"

STATUS_TITLES = {
    STATUS_NEW: "новый",
    STATUS_IN_PROGRESS: "в работе",
    STATUS_PAID: "оплачен",
    STATUS_SENT: "отправлен",
    STATUS_ARCHIVED: "архив",
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
    promocode_code: str | None = None,
    discount_amount: int | None = None,
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
            total, promocode_code, discount_amount,
            status, order_text, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            user_name,
            customer_name,
            contact,
            comment,
            total,
            promocode_code,
            discount_amount,
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
        "user_id": row["user_id"],
        "user_name": row["user_name"],
        "customer_name": row["customer_name"],
        "contact": row["contact"],
        "promocode_code": row["promocode_code"] if "promocode_code" in row.keys() else None,
        "discount_amount": row["discount_amount"] if "discount_amount" in row.keys() else None,
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
        SELECT id, user_id, user_name, customer_name, contact, total, status, created_at
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
        SELECT DISTINCT o.id, o.user_id, o.user_name, o.customer_name, o.contact, o.total, o.status, o.created_at
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
        SELECT id, user_id, user_name, customer_name, contact, total, status, created_at
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
        SELECT id, user_id, user_name, customer_name, contact, comment, total, promocode_code, discount_amount, status, order_text, created_at
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
        "promocode_code": row["promocode_code"],
        "discount_amount": row["discount_amount"],
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


def get_orders_for_admin(status_filter: str = "all", limit: int = 30) -> list[dict[str, Any]]:
    """Вернуть заказы для админки с фильтром по статусу."""
    if limit <= 0:
        return []

    status_filter = (status_filter or "all").lower()
    valid_statuses = set(STATUS_TITLES.keys())

    where_clause = ""
    params: list[Any] = []

    if status_filter == "all":
        where_clause = ""
    elif status_filter in valid_statuses:
        where_clause = "WHERE status = ?"
        params.append(status_filter)
    else:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, user_id, user_name, customer_name, contact, total, status, created_at
        FROM orders
        {where_clause}
        ORDER BY id DESC
        LIMIT ?
        """,
        (*params, limit),
    )
    rows = cur.fetchall()
    conn.close()

    return [_make_order_row(row) for row in rows]


def grant_course_access(
    user_id: int,
    course_id: int,
    granted_by: int | None,
    source_order_id: int | None,
    comment: str | None = None,
) -> bool:
    """Выдать пользователю доступ к курсу (или обновить существующий)."""

    granted_at = datetime.now().isoformat(timespec="seconds")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO user_courses (
            user_id, course_id, source_order_id, granted_by, granted_at, status, comment
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        ON CONFLICT(user_id, course_id) DO UPDATE SET
            status = 'active',
            source_order_id = excluded.source_order_id,
            granted_by = excluded.granted_by,
            granted_at = excluded.granted_at,
            comment = excluded.comment
        """,
        (user_id, course_id, source_order_id, granted_by, granted_at, comment),
    )
    conn.commit()
    success = cur.rowcount > 0
    conn.close()
    return success


def revoke_course_access(user_id: int, course_id: int) -> bool:
    """Забрать доступ к курсу (пометить как revoked)."""

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE user_courses
        SET status = 'revoked', granted_at = ?
        WHERE user_id = ? AND course_id = ?
        """,
        (datetime.now().isoformat(timespec="seconds"), user_id, course_id),
    )
    conn.commit()
    success = cur.rowcount > 0
    conn.close()
    return success


def get_user_courses_with_access(user_id: int) -> list[dict[str, Any]]:
    """Курсы с активным доступом для пользователя."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.id, p.name, p.description, p.detail_url, p.image_file_id
        FROM user_courses uc
        JOIN products p ON p.id = uc.course_id
        WHERE uc.user_id = ?
          AND uc.status = 'active'
          AND p.type = 'course'
        ORDER BY p.id ASC
        """,
        (user_id,),
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


def get_course_users(course_id: int) -> list[dict[str, Any]]:
    """Список пользователей с активным доступом к курсу."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT uc.user_id, uc.source_order_id, uc.granted_by, uc.granted_at, uc.comment
        FROM user_courses uc
        JOIN products p ON p.id = uc.course_id
        WHERE uc.course_id = ?
          AND uc.status = 'active'
          AND p.type = 'course'
        ORDER BY uc.granted_at ASC, uc.user_id ASC
        """,
        (course_id,),
    )

    rows = cur.fetchall()
    conn.close()

    users: list[dict[str, Any]] = []
    for row in rows:
        users.append(
            {
                "user_id": row["user_id"],
                "source_order_id": row["source_order_id"],
                "granted_by": row["granted_by"],
                "granted_at": row["granted_at"],
                "comment": row["comment"],
            }
        )

    return users


def _extract_course_products(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Вернуть список активных курсов из позиций заказа.
    """

    courses: list[dict[str, Any]] = []

    for item in items:
        raw_product_id = item.get("product_id")
        try:
            product_id = int(raw_product_id) if raw_product_id is not None else None
        except (TypeError, ValueError):
            product_id = None

        if product_id is None:
            continue

        product = products_service.get_product_by_id(product_id)
        if not product:
            continue

        if product.get("type") == "course" and int(product.get("is_active", 0) or 0) == 1:
            courses.append(product)

    return courses


def get_courses_from_order(order_id: int) -> list[dict[str, Any]]:
    """Вернуть список курсов из позиций заказа (только активные)."""

    order = get_order_by_id(order_id)
    if not order:
        return []

    items = order.get("items") or []
    return _extract_course_products(items)


def grant_courses_from_order(order_id: int, admin_id: int | None = None) -> int:
    """Выдать доступ ко всем курсам из заказа. Возвращает количество курсов."""

    order = get_order_by_id(order_id)
    if not order:
        return 0

    user_id = order.get("user_id")
    if not user_id:
        return 0

    items = order.get("items") or []
    courses = _extract_course_products(items)

    granted_count = 0
    for course in courses:
        success = grant_course_access(
            user_id,
            int(course["id"]),
            admin_id,
            order_id,
            comment="Выдано по оплаченному заказу",
        )
        if success:
            granted_count += 1

    return granted_count
