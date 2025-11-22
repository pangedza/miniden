from typing import Any, List, Tuple

from database import get_connection



def _normalize_product_id(raw_product_id: Any) -> str:
    """Привести product_id из БД к строке."""

    return "" if raw_product_id is None else str(raw_product_id).strip()


def get_cart_items(user_id: int) -> Tuple[List[dict[str, Any]], List[dict[str, Any]]]:
    """
    Вернуть содержимое корзины пользователя и список удалённых позиций.

    Всегда возвращает кортеж (items, removed_items):
    - items: валидные товары {product_id, name, price, qty};
    - removed_items: позиции, удалённые из корзины (битый id, qty <= 0).
      Каждая запись: {product_id, name?, reason}.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT product_id, name, price, qty
        FROM cart_items
        WHERE user_id = ?
        ORDER BY rowid ASC
        """,
        (user_id,),
    )
    rows = cur.fetchall()

    items: list[dict[str, Any]] = []
    removed_items: list[dict[str, Any]] = []
    to_delete: list[str] = []
    delete_null_product_id = False

    for row in rows:
        raw_product_id = row["product_id"]
        qty = int(row["qty"] or 0)

        if raw_product_id is None:
            delete_null_product_id = True
            removed_items.append(
                {
                    "product_id": None,
                    "reason": "missing_product_id",
                }
            )
            continue

        product_id_str = _normalize_product_id(raw_product_id)

        if qty <= 0:
            to_delete.append(product_id_str)
            removed_items.append(
                {
                    "product_id": product_id_str,
                    "name": row["name"],
                    "reason": "non_positive_qty",
                }
            )
            continue

        items.append(
            {
                "product_id": product_id_str,
                "name": row["name"],
                "price": int(row["price"] or 0),
                "qty": qty,
            }
        )

    # Чистим корзину от неактуальных записей (битые id, нулевые количества)
    if delete_null_product_id:
        cur.execute(
            """
            DELETE FROM cart_items
            WHERE user_id = ? AND product_id IS NULL
            """,
            (user_id,),
        )

    if to_delete:
        cur.executemany(
            """
            DELETE FROM cart_items
            WHERE user_id = ? AND product_id = ?
            """,
            [(user_id, pid) for pid in to_delete],
        )
        conn.commit()

    conn.close()
    return items, removed_items


def get_cart_total(user_id: int) -> int:
    """
    Посчитать общую сумму корзины пользователя.
    """
    items, _ = get_cart_items(user_id)
    total = 0
    for item in items:
        total += int(item["price"]) * int(item["qty"])
    return total


def add_to_cart(
    user_id: int,
    product_id: str,
    name: str,
    price: int,
    qty: int = 1,
) -> None:
    """
    Добавить товар в корзину.
    Если такой product_id уже есть — увеличиваем количество.

    product_id:
        строка, но должна быть целым числом в строковом виде (например, "1", "2").
    """
    conn = get_connection()
    cur = conn.cursor()

    # Проверяем, есть ли уже такой товар
    cur.execute(
        """
        SELECT qty FROM cart_items
        WHERE user_id = ? AND product_id = ?
        """,
        (user_id, product_id),
    )
    row = cur.fetchone()

    if row is None:
        # Новый товар
        cur.execute(
            """
            INSERT INTO cart_items (user_id, product_id, name, price, qty)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, product_id, name, price, qty),
        )
    else:
        # Уже есть — увеличиваем количество
        current_qty = int(row["qty"] or 0)
        new_qty = current_qty + qty
        if new_qty <= 0:
            # если ушли в ноль или минус — удаляем позицию
            cur.execute(
                """
                DELETE FROM cart_items
                WHERE user_id = ? AND product_id = ?
                """,
                (user_id, product_id),
            )
        else:
            cur.execute(
                """
                UPDATE cart_items
                SET qty = ?
                WHERE user_id = ? AND product_id = ?
                """,
                (new_qty, user_id, product_id),
            )

    conn.commit()
    conn.close()


def change_qty(user_id: int, product_id: str, delta: int) -> None:
    """
    Изменить количество товара в корзине на delta.
    delta = +1 -> плюс один, delta = -1 -> минус один.
    Если станет 0 или меньше — позиция удаляется.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT qty FROM cart_items
        WHERE user_id = ? AND product_id = ?
        """,
        (user_id, product_id),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        return

    current_qty = int(row["qty"] or 0)
    new_qty = current_qty + delta

    if new_qty <= 0:
        cur.execute(
            """
            DELETE FROM cart_items
            WHERE user_id = ? AND product_id = ?
            """,
            (user_id, product_id),
        )
    else:
        cur.execute(
            """
            UPDATE cart_items
            SET qty = ?
            WHERE user_id = ? AND product_id = ?
            """,
            (new_qty, user_id, product_id),
        )

    conn.commit()
    conn.close()


def remove_from_cart(user_id: int, product_id: str) -> None:
    """
    Полностью удалить товар из корзины.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM cart_items
        WHERE user_id = ? AND product_id = ?
        """,
        (user_id, product_id),
    )
    conn.commit()
    conn.close()


def clear_cart(user_id: int) -> None:
    """
    Очистить корзину пользователя полностью.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM cart_items
        WHERE user_id = ?
        """,
        (user_id,),
    )
    conn.commit()
    conn.close()
