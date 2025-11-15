from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="🧺 Корзинки"),
            KeyboardButton(text="🎓 Онлайн-курсы"),
        ],
        [
            KeyboardButton(text="🛒 Корзина"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел меню",
    )
