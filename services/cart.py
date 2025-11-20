from typing import Any, List

from database import get_connection
from . import products as products_service


def get_cart_items(user_id: int) -> List[dict[str, Any]]:
    """
    Вернуть список товаров в корзине пользователя.

    Каждый элемент: {product_id, name, price, qty}.

    ВАЖНО:
    - Имя и цена берутся из АКТУАЛЬНЫХ данных таблицы products,
      если товар существует и активен.
    - Если товар скрыт, удалён или id некорректен — позиция
      автоматически удаляется из корзины.
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
    to_delete: list[str] = []

    for row in rows:
        raw_product_id = row["product_id"]
        qty = int(row["qty"] or 0)

        # Пропускаем некорректные записи и нулевые количества
        try:
            product_id_int = int(raw_product_id)
        except (TypeError, ValueError):
            to_delete.append(str(raw_product_id))
            continue

        if qty <= 0:
            to_delete.append(str(raw_product_id))
            continue

        # Берём актуальные данные товара из таблицы products
        product = products_service.get_product_by_id(product_id_int)
        if not product or product.get("is_active") != 1:
            # Товар скрыт или не существует — удаляем его из корзины
            to_delete.append(str(raw_product_id))
            continue

        name = product.get("name") or row["name"]
        price = int(product.get("price") or row["price"] or 0)

        items.append(
            {
                "product_id": str(product_id_int),
                "name": name,
                "price": price,
                "qty": qty,
            }
        )

    # Чистим корзину от неактуальных записей (битые id, скрытые товары и т.п.)
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
    return items


def get_cart_total(user_id: int) -> int:
    """
    Посчитать общую сумму корзины пользователя.

    Сумма считается по актуальным ценам из products,
    потому что get_cart_items уже обновляет price.
    """
    items = get_cart_items(user_id)
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
