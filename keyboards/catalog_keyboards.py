from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_product_card_kb(
    product: dict, has_access: bool, is_favorite: bool
) -> InlineKeyboardMarkup:
    """Inline-клавиатура для карточки товара/курса."""

    product_id = product.get("id")
    product_type = product.get("type")
    detail_url = product.get("detail_url")

    rows: list[list[InlineKeyboardButton]] = []

    if detail_url and has_access:
        rows.append([InlineKeyboardButton(text="🔗 Перейти", url=detail_url)])

    favorite_button = InlineKeyboardButton(
        text="💔 Убрать из избранного" if is_favorite else "❤️ В избранное",
        callback_data=(
            f"fav:remove:{product_id}" if is_favorite else f"fav:add:{product_id}"
        ),
    )
    rows.append([favorite_button])

    rows.append(
        [
            InlineKeyboardButton(
                text="➕ В корзину",
                callback_data=f"cart:add:{product_type}:{product_id}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_pagination_kb(
    section: str, page: int, has_prev: bool, has_next: bool
) -> InlineKeyboardMarkup:
    """Кнопки пагинации каталога."""

    buttons: list[InlineKeyboardButton] = []

    if has_prev:
        buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад", callback_data=f"catalog:prev:{section}:{page - 1}"
            )
        )
    if has_next:
        buttons.append(
            InlineKeyboardButton(
                text="▶️ Вперёд", callback_data=f"catalog:next:{section}:{page + 1}"
            )
        )

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def catalog_product_actions_kb(
    product_type: str,
    product_id: int,
    is_favorite: bool = False,
    url: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Совместимость со старым именем функции."""

    product = {"id": product_id, "type": product_type, "detail_url": url}
    return build_product_card_kb(
        product=product, has_access=bool(url), is_favorite=is_favorite
    )
