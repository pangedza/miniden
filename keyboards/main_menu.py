from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from utils.commands_map import get_admin_commands, get_user_commands
from config import get_settings

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
    """

    settings = get_settings()
    user_commands = get_user_commands()
    admin_commands = get_admin_commands()

    keyboard: list[list[KeyboardButton]] = [
        [KeyboardButton(text="🧺 Корзинки"), KeyboardButton(text="🎓 Курсы")],
    ]

    row: list[KeyboardButton] = [KeyboardButton(text="🛒 Корзина")]
    row.append(KeyboardButton(text="❤️ Избранное"))
    if "profile" in user_commands:
        row.append(KeyboardButton(text=PROFILE_BUTTON_TEXT))
    keyboard.append(row)

    webapp_row: list[KeyboardButton] = []
    if settings.webapp_baskets_url:
        webapp_row.append(
            KeyboardButton(
                text="🧺 Корзинки (WebApp)", web_app=WebAppInfo(url=settings.webapp_baskets_url)
            )
        )
    if settings.webapp_courses_url:
        webapp_row.append(
            KeyboardButton(
                text="🎓 Курсы (WebApp)", web_app=WebAppInfo(url=settings.webapp_courses_url)
            )
        )
    if webapp_row:
        keyboard.append(webapp_row)

    if "help" in user_commands:
        keyboard.append([KeyboardButton(text="❓ Помощь")])

    if is_admin:
        admin_row: list[KeyboardButton] = [KeyboardButton(text="⚙️ Админка")]
        if "stats" in admin_commands:
            admin_row.append(KeyboardButton(text="📊 Статистика"))
        keyboard.append(admin_row)

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

    if "stats" in admin_commands:
        keyboard.append([KeyboardButton(text="📊 Статистика")])

    keyboard.append([KeyboardButton(text="🎟 Промокоды")])

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
