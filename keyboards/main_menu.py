from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from utils.commands_map import get_admin_commands
from config import get_settings


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
    keyboard: list[list[KeyboardButton]] = []

    webapp_buttons: list[KeyboardButton] = []

    base_url = getattr(settings, "webapp_base_url", None) or settings.webapp_index_url
    if base_url:
        webapp_buttons.append(
            KeyboardButton(
                text="🏠 Главная (WebApp)",
                web_app=WebAppInfo(url=base_url),
            )
        )

    if settings.webapp_products_url:
        webapp_buttons.append(
            KeyboardButton(
                text="🛍 Товары (WebApp)",
                web_app=WebAppInfo(url=settings.webapp_products_url),
            )
        )

    if settings.webapp_masterclasses_url:
        webapp_buttons.append(
            KeyboardButton(
                text="🎓 Мастер-классы (WebApp)",
                web_app=WebAppInfo(url=settings.webapp_masterclasses_url),
            )
        )

    if settings.webapp_cart_url:
        webapp_buttons.append(
            KeyboardButton(
                text="🛒 Корзина (WebApp)",
                web_app=WebAppInfo(url=settings.webapp_cart_url),
            )
        )

    if settings.webapp_profile_url:
        webapp_buttons.append(
            KeyboardButton(
                text="👤 Профиль (WebApp)",
                web_app=WebAppInfo(url=settings.webapp_profile_url),
            )
        )

    row: list[KeyboardButton] = []
    for button in webapp_buttons:
        row.append(button)
        if len(row) >= 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if is_admin and getattr(settings, "webapp_admin_url", None):
        keyboard.append(
            [
                KeyboardButton(
                    text="⚙️ Админка (WebApp)",
                    web_app=WebAppInfo(url=settings.webapp_admin_url),
                )
            ]
        )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Откройте магазин через WebApp…",
    )


def get_admin_menu() -> ReplyKeyboardMarkup:
    """Клавиатура админского меню, собранная из ADMIN_COMMANDS."""

    admin_commands = get_admin_commands()
    settings = get_settings()

    keyboard: list[list[KeyboardButton]] = []

    if "orders" in admin_commands:
        keyboard.append([KeyboardButton(text="📦 Заказы")])

    if "client" in admin_commands:
        keyboard.append([KeyboardButton(text="👤 Клиент (CRM)")])

    if {"ban", "unban"} & admin_commands.keys():
        keyboard.append([KeyboardButton(text="🚫 Бан / ✅ Разбан")])

    if {"note", "notes"} & admin_commands.keys():
        keyboard.append([KeyboardButton(text="📝 Заметки")])

    keyboard.append([KeyboardButton(text="🎓 Доступ к курсам")])

    if getattr(settings, "webapp_admin_url", None):
        keyboard.append(
            [
                KeyboardButton(
                    text="⚙️ Админка (WebApp)",
                    web_app=WebAppInfo(url=settings.webapp_admin_url),
                )
            ]
        )

    keyboard.append([KeyboardButton(text="⬅️ В главное меню")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
    )
