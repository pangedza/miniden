from typing import Any, Sequence

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


def _extract_button_field(button: Any, field: str, default: Any = None) -> Any:
    if isinstance(button, dict):
        return button.get(field, default)
    return getattr(button, field, default)


def get_main_menu(
    menu_buttons: Sequence[Any] | None = None, *, include_fallback: bool = True
) -> ReplyKeyboardMarkup | None:
    """
    Динамическое меню из конструктора AdminBot.
    Если кнопок нет, возвращает клавиатуру только с кнопкой «Меню»
    или None, если include_fallback=False.
    """

    prepared_rows: dict[int, list[KeyboardButton]] = {}

    for button in menu_buttons or []:
        text = (_extract_button_field(button, "text") or "").strip()
        row = _extract_button_field(button, "row", 0) or 0
        position = _extract_button_field(button, "position", 0) or 0

        if not text:
            continue

        prepared_rows.setdefault(row, []).append(
            (position, KeyboardButton(text=text))
        )

    if not prepared_rows:
        if not include_fallback:
            return None
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Меню")]],
            resize_keyboard=True,
            input_field_placeholder="Открыть меню…",
        )

    keyboard_rows: list[list[KeyboardButton]] = []
    for row in sorted(prepared_rows.keys()):
        sorted_buttons = [btn for _, btn in sorted(prepared_rows[row], key=lambda item: (item[0], item[1].text))]
        if sorted_buttons:
            keyboard_rows.append(sorted_buttons)

    if not keyboard_rows:
        return None

    return ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел…",
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
