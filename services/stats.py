from __future__ import annotations

from datetime import datetime, timedelta

from database import get_connection


def _build_date_filters(date_from: str | None, date_to: str | None) -> tuple[str, list[str]]:
    conditions: list[str] = []
    params: list[str] = []

    if date_from:
        conditions.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= ?")
        params.append(date_to)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    return where_clause, params


def get_orders_stats_summary(date_from: str | None = None, date_to: str | None = None) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        where_clause, params = _build_date_filters(date_from, date_to)

        cur.execute(
            f"""
            SELECT COUNT(*) AS total_orders, COALESCE(SUM(total), 0) AS total_amount
            FROM orders
            {where_clause}
            """,
            params,
        )
        row = cur.fetchone() or {}

        cur.execute(
            f"""
            SELECT status, COUNT(*) AS cnt
            FROM orders
            {where_clause}
            GROUP BY status
            """,
            params,
        )
        status_rows = cur.fetchall() or []
    finally:
        conn.close()

    by_status: dict[str, int] = {row["status"]: int(row["cnt"]) for row in status_rows if row["status"]}

    return {
        "total_orders": int(row.get("total_orders", 0) or 0),
        "total_amount": int(row.get("total_amount", 0) or 0),
        "by_status": by_status,
    }


def get_orders_stats_by_day(limit_days: int = 7) -> list[dict]:
    if limit_days <= 0:
        return []

    today = datetime.now().date()
    date_from = (today - timedelta(days=limit_days - 1)).isoformat()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT SUBSTR(created_at, 1, 10) AS day,
                   COUNT(*) AS orders_count,
                   COALESCE(SUM(total), 0) AS total_amount
            FROM orders
            WHERE created_at >= ?
            GROUP BY day
            ORDER BY day DESC
            LIMIT ?
            """,
            (date_from, limit_days),
        )
        rows = cur.fetchall() or []
    finally:
        conn.close()

    return [
        {
            "date": row["day"],
            "orders_count": int(row["orders_count"] or 0),
            "total_amount": int(row["total_amount"] or 0),
        }
        for row in rows
    ]


def get_top_products(limit: int = 5) -> list[dict]:
    if limit <= 0:
        return []

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                oi.product_id AS product_id,
                COALESCE(p.name, oi.product_name) AS name,
                SUM(COALESCE(oi.qty, 0)) AS total_qty,
                SUM(COALESCE(oi.qty, 0) * COALESCE(oi.price, 0)) AS total_amount
            FROM order_items oi
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE oi.product_id IS NOT NULL OR oi.product_name IS NOT NULL
            GROUP BY oi.product_id, name
            HAVING name IS NOT NULL AND TRIM(name) != ''
            ORDER BY total_amount DESC, total_qty DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall() or []
    finally:
        conn.close()

    return [
        {
            "product_id": row["product_id"],
            "name": row["name"],
            "total_qty": int(row["total_qty"] or 0),
            "total_amount": int(row["total_amount"] or 0),
        }
        for row in rows
    ]


def get_top_courses(limit: int = 5) -> list[dict]:
    if limit <= 0:
        return []

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                oi.product_id AS product_id,
                COALESCE(p.name, oi.product_name) AS name,
                SUM(COALESCE(oi.qty, 0)) AS total_qty,
                SUM(COALESCE(oi.qty, 0) * COALESCE(oi.price, 0)) AS total_amount
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            WHERE p.type = 'course'
            GROUP BY oi.product_id, name
            HAVING name IS NOT NULL AND TRIM(name) != ''
            ORDER BY total_amount DESC, total_qty DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall() or []
    finally:
        conn.close()

    return [
        {
            "product_id": row["product_id"],
            "name": row["name"],
            "total_qty": int(row["total_qty"] or 0),
            "total_amount": int(row["total_amount"] or 0),
        }
        for row in rows
    ]
