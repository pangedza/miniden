import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from services import users as users_service


class EnsureUserMiddleware(BaseMiddleware):
    """Создаёт или обновляет пользователя по telegram_id при первом обращении."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = getattr(event, "from_user", None)

        if telegram_user:
            try:
                users_service.get_or_create_user_from_telegram(
                    {
                        "id": telegram_user.id,
                        "username": telegram_user.username,
                        "first_name": telegram_user.first_name,
                        "last_name": telegram_user.last_name,
                    }
                )
            except Exception:  # noqa: BLE001
                logging.exception("Не удалось создать/обновить пользователя в БД")

        return await handler(event, data)
