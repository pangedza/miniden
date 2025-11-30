"""Карта пользовательских и админских команд бота."""

from __future__ import annotations

USER_COMMANDS: dict[str, str] = {
    "start": "Запуск бота",
    "help": "FAQ и поддержка (как пользоваться WebApp)",
}

ADMIN_COMMANDS: dict[str, str] = {
    "orders": "Список заказов и фильтры",
    "client": "CRM-профиль клиента",
    "ban": "Забанить пользователя",
    "unban": "Разбанить пользователя",
    "note": "Добавить заметку по клиенту",
    "notes": "Список заметок по клиенту",
    "debug_commands": "Показать все команды бота",
    "stats": "Статистика",
}


def get_user_commands() -> dict[str, str]:
    """Вернуть карту пользовательских команд."""

    return USER_COMMANDS


def get_admin_commands() -> dict[str, str]:
    """Вернуть карту админских команд."""

    return ADMIN_COMMANDS
