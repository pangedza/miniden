from __future__ import annotations

from typing import Any

from database import get_connection
from services import orders as orders_service


def get_user_order_stats(user_id: int) -> dict[str, Any]:
    """Подсчитать статистику по заказам пользователя для CRM."""

    result: dict[str, Any] = {
        "user_id": user_id,
        "total_orders": 0,
        "total_amount": 0,
        "orders_by_status": {
            orders_service.STATUS_NEW: 0,
            orders_service.STATUS_IN_PROGRESS: 0,
            orders_service.STATUS_PAID: 0,
            orders_service.STATUS_SENT: 0,
            orders_service.STATUS_ARCHIVED: 0,
        },
        "last_order_id": None,
        "last_order_created_at": None,
    }

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) AS cnt, COALESCE(SUM(total), 0) AS total_amount
        FROM orders
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cur.fetchone()
    if row:
        result["total_orders"] = int(row["cnt"] or 0)
        result["total_amount"] = int(row["total_amount"] or 0)

    cur.execute(
        """
        SELECT status, COUNT(*) AS cnt
        FROM orders
        WHERE user_id = ?
        GROUP BY status
        """,
        (user_id,),
    )
    for status_row in cur.fetchall():
        status = status_row["status"]
        count = int(status_row["cnt"] or 0)
        if status in result["orders_by_status"]:
            result["orders_by_status"][status] = count

    cur.execute(
        """
        SELECT id, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    last_order = cur.fetchone()
    conn.close()

    if last_order:
        result["last_order_id"] = int(last_order["id"])
        result["last_order_created_at"] = last_order["created_at"]

    return result


def get_user_courses_summary(user_id: int) -> dict[str, Any]:
    """Сводка по курсам, к которым у пользователя есть доступ."""

    courses = orders_service.get_user_courses_with_access(user_id)
    return {
        "count": len(courses),
        "courses": courses,
    }
