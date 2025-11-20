from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def catalog_product_actions_kb(
    product_type: str,
    product_id: int,
    url: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Кнопки под товаром в пользовательском каталоге:
    - «Подробнее» (если есть ссылка)
    - «Добавить в корзину»
    """
    rows: list[list[InlineKeyboardButton]] = []

    # Кнопка с внешней ссылкой (если URL есть)
    if url:
        rows.append([InlineKeyboardButton(text="🔗 Подробнее", url=url)])

    # Кнопка добавления в корзину (всегда)
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ В корзину",
                callback_data=f"cart:add:{product_type}:{product_id}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
