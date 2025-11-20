from typing import Iterable

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def cart_kb(items: Iterable[dict]) -> InlineKeyboardMarkup:
    """
    Клавиатура для корзины (новая версия с SQLite):
    - для каждой позиции: ➖ qty ➕ ❌
    - внизу: очистить и оформить заказ
    """
    items = list(items)
    inline_keyboard: list[list[InlineKeyboardButton]] = []

    for item in items:
        product_id = str(item.get("product_id"))
        qty = int(item.get("qty", 1))

        row = [
            InlineKeyboardButton(
                text="➖",
                callback_data=f"cart:dec:{product_id}",
            ),
            InlineKeyboardButton(
                text=str(qty),
                callback_data="cart:nop",
            ),
            InlineKeyboardButton(
                text="➕",
                callback_data=f"cart:inc:{product_id}",
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"cart:remove:{product_id}",
            ),
        ]
        inline_keyboard.append(row)

    # Нижний ряд — очистить / оформить заказ
    if items:
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text="🧹 Очистить",
                    callback_data="cart:clear",
                ),
                InlineKeyboardButton(
                    text="💳 Оформить заказ",
                    callback_data="cart:checkout",
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
