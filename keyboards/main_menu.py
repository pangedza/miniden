from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

PROFILE_BUTTON_TEXT = "👤 Профиль"


def get_start_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура только с одной кнопкой «Старт».
    Используется до прохождения проверки подписки.
    """
    keyboard = [
        [KeyboardButton(text="🔵 Старт")],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Нажмите «Старт» для начала…",
    )


def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Главное меню после прохождения проверки подписки.
    Кнопка «🔵 Старт» остаётся, чтобы всегда можно было
    перепроверять подписку.
    """
    keyboard = [
        [
            KeyboardButton(text="🔵 Старт")
        ],
        [
            KeyboardButton(text="🧺 Корзинки"),
            KeyboardButton(text="🎓 Онлайн-курсы"),
        ],
        [
            KeyboardButton(text="🛒 Корзина"),
            KeyboardButton(text=PROFILE_BUTTON_TEXT),
        ],
    ]

    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Админка")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел…",
    )
