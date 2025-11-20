from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from utils.commands_map import get_admin_commands, get_user_commands

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

    user_commands = get_user_commands()

    keyboard: list[list[KeyboardButton]] = [
        [KeyboardButton(text="🔵 Старт")],
        [KeyboardButton(text="🧺 Корзинки"), KeyboardButton(text="🎓 Онлайн-курсы")],
    ]

    row: list[KeyboardButton] = [KeyboardButton(text="🛒 Корзина")]
    if "profile" in user_commands:
        row.append(KeyboardButton(text=PROFILE_BUTTON_TEXT))
    keyboard.append(row)

    if "help" in user_commands:
        keyboard.append([KeyboardButton(text="❓ Помощь")])

    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Админка")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел…",
    )


def get_admin_menu() -> ReplyKeyboardMarkup:
    """Клавиатура админского меню, собранная из ADMIN_COMMANDS."""

    admin_commands = get_admin_commands()

    keyboard: list[list[KeyboardButton]] = []

    if "orders" in admin_commands:
        keyboard.append([KeyboardButton(text="📦 Заказы")])

    keyboard.append([KeyboardButton(text="📊 Статистика")])

    keyboard.append(
        [
            KeyboardButton(text="📋 Товары: корзинки"),
            KeyboardButton(text="📋 Товары: курсы"),
        ]
    )

    if "client" in admin_commands:
        keyboard.append([KeyboardButton(text="👤 Клиент (CRM)")])

    if {"ban", "unban"} & admin_commands.keys():
        keyboard.append([KeyboardButton(text="🚫 Бан / ✅ Разбан")])

    if {"note", "notes"} & admin_commands.keys():
        keyboard.append([KeyboardButton(text="📝 Заметки")])

    keyboard.append([KeyboardButton(text="🎓 Доступ к курсам")])

    keyboard.append([KeyboardButton(text="⬅️ В главное меню")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
    )
