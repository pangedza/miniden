from typing import Any, Sequence
from urllib.parse import urlencode

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


def _normalize_button_text(text: str) -> str:
    return " ".join((text or "").casefold().split())


def _build_category_url(slug: str, *, item_type: str | None = None, settings=None) -> str | None:
    normalized_slug = (slug or "").strip().strip("/")
    if not normalized_slug:
        return None

    settings = settings or get_settings()
    base_origin = (settings.bot_base_origin or "https://miniden.ru").rstrip("/")
    params: dict[str, str] = {}
    if item_type:
        params["type"] = item_type

    query = f"?{urlencode(params)}" if params else ""
    return f"{base_origin}/c/{normalized_slug}{query}"


def _special_menu_webapp_url(text: str, *, settings=None) -> str | None:
    settings = settings or get_settings()
    normalized = _normalize_button_text(text)
    slug_map: dict[str, tuple[str, str]] = {
        _normalize_button_text("Мои товары"): (
            settings.bot_products_category_slug,
            "product",
        ),
        _normalize_button_text("Мои работы"): (
            settings.bot_works_category_slug,
            "product",
        ),
        _normalize_button_text("Мои мастер-классы"): (
            settings.bot_masterclasses_category_slug,
            "masterclass",
        ),
    }

    slug_and_type = slug_map.get(normalized)
    if not slug_and_type:
        return None

    slug, item_type = slug_and_type
    return _build_category_url(slug, item_type=item_type, settings=settings)


def get_main_menu(
    menu_buttons: Sequence[Any] | None = None, *, include_fallback: bool = True
) -> ReplyKeyboardMarkup | None:
    """
    Динамическое меню из конструктора AdminBot.
    Если кнопок нет, возвращает клавиатуру только с кнопкой «Меню»
    или None, если include_fallback=False.
    """

    prepared_rows: dict[int, list[KeyboardButton]] = {}
    settings = get_settings()

    for button in menu_buttons or []:
        text = (_extract_button_field(button, "text") or "").strip()
        row = _extract_button_field(button, "row", 0) or 0
        position = _extract_button_field(button, "position", 0) or 0
        action_type = (_extract_button_field(button, "action_type", "") or "").upper()
        action_payload = _extract_button_field(button, "action_payload") or ""
        action_url = (
            action_payload
            or _extract_button_field(button, "webapp_url", "")
            or _extract_button_field(button, "url", "")
        ).strip()
        special_webapp_url = _special_menu_webapp_url(text, settings=settings)

        if special_webapp_url:
            action_type = "WEBAPP"
            action_url = special_webapp_url

        if not text:
            continue

        if action_type in {"WEBAPP", "URL"} and action_url:
            kb_button = KeyboardButton(text=text, web_app=WebAppInfo(url=action_url))
        else:
            kb_button = KeyboardButton(text=text)

        prepared_rows.setdefault(row, []).append(
            (position, kb_button)
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
