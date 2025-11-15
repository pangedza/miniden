from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def product_link_kb(url: str) -> InlineKeyboardMarkup:
    """Кнопка с переходом на внешний сайт/лендинг товара."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Подробнее", url=url)]]
    )
