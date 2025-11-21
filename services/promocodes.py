from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from database import get_connection


def normalize_code(code: str) -> str:
    """Привести код к единообразному виду: обрезать и сделать верхний регистр."""

    normalized = " ".join((code or "").strip().split())
    return normalized.upper()


def create_promocode(
    code: str,
    discount_type: str,
    discount_value: int,
    min_order_total: int = 0,
    max_uses: int = 0,
    valid_from: str | None = None,
    valid_to: str | None = None,
    description: str | None = None,
) -> int:
    """Создать промокод и вернуть его id. Возвращает -1 при дублировании кода."""

    discount_type = (discount_type or "").strip().lower()
    if discount_type not in {"percent", "fixed"}:
        raise ValueError("discount_type должен быть 'percent' или 'fixed'")

    if discount_value is None or int(discount_value) <= 0:
        raise ValueError("discount_value должен быть больше 0")

    code_norm = normalize_code(code)

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO promocodes (
                code, discount_type, discount_value,
                min_order_total, max_uses, valid_from, valid_to, description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code_norm,
                discount_type,
                int(discount_value),
                int(min_order_total or 0),
                int(max_uses or 0),
                valid_from,
                valid_to,
                description,
            ),
        )
    except sqlite3.IntegrityError:
        conn.close()
        return -1

    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(new_id)


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()} if row else {}


def get_promocode_by_code(code: str) -> dict | None:
    code_norm = normalize_code(code)
    if not code_norm:
        return None

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM promocodes
        WHERE code = ?
        LIMIT 1
        """,
        (code_norm,),
    )
    row = cur.fetchone()
    conn.close()

    return _row_to_dict(row) if row else None


def list_promocodes(limit: int = 50) -> list[dict]:
    if limit <= 0:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM promocodes
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def set_promocode_active(code: str, is_active: bool) -> bool:
    code_norm = normalize_code(code)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE promocodes
        SET is_active = ?
        WHERE code = ?
        """,
        (1 if is_active else 0, code_norm),
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def increment_promocode_usage(code: str) -> None:
    code_norm = normalize_code(code)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE promocodes
        SET used_count = used_count + 1
        WHERE code = ?
        """,
        (code_norm,),
    )
    conn.commit()
    conn.close()


def validate_promocode_for_order(
    promo: dict, order_total: int, now: datetime | None = None
) -> tuple[bool, str | None]:
    now = now or datetime.now()

    if not promo:
        return False, "Промокод не найден"

    if int(promo.get("is_active", 0)) != 1:
        return False, "Промокод неактивен"

    valid_from = promo.get("valid_from")
    if valid_from:
        try:
            starts_at = datetime.fromisoformat(valid_from)
            if now < starts_at:
                return False, "Промокод ещё не активен"
        except ValueError:
            pass

    valid_to = promo.get("valid_to")
    if valid_to:
        try:
            ends_at = datetime.fromisoformat(valid_to)
            if now > ends_at:
                return False, "Промокод истёк"
        except ValueError:
            pass

    max_uses = int(promo.get("max_uses", 0) or 0)
    used_count = int(promo.get("used_count", 0) or 0)
    if max_uses > 0 and used_count >= max_uses:
        return False, "Лимит использований исчерпан"

    min_order_total = int(promo.get("min_order_total", 0) or 0)
    if min_order_total > 0 and order_total < min_order_total:
        return False, f"Минимальная сумма заказа {min_order_total} ₽"

    return True, None


def calculate_discount_amount(promo: dict, order_total: int) -> int:
    if not promo:
        return 0

    discount_type = promo.get("discount_type")
    discount_value = int(promo.get("discount_value", 0) or 0)
    amount = 0

    if discount_type == "percent":
        amount = order_total * discount_value // 100
    elif discount_type == "fixed":
        amount = discount_value

    if amount < 0:
        amount = 0

    if amount > order_total:
        amount = order_total

    return amount


def get_promocodes_usage_summary(limit: int = 50) -> list[dict]:
    if limit <= 0:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT code, discount_type, discount_value, used_count, max_uses, is_active
        FROM promocodes
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]
