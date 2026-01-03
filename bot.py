"""
Точка входа Telegram-бота MiniDeN.
- Проверка подписки
- Стартовый экран
- Главное меню с WebApp-кнопками (магазин работает в браузере)
- Мини-CRM для админов (заказы, клиенты, заметки, бан/разбан)
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties  # 👈 ДОБАВИЛИ ЭТОТ ИМПОРТ
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientError, ClientTimeout
from aiohttp.client_exceptions import ServerDisconnectedError

from config import get_settings
from database import init_db
from utils.logging_config import BOT_LOG_FILE, setup_logging

from handlers import admin, baskets, cart, courses, start, webapp
from handlers import faq, site_chat, support
from middlewares.user_registration import EnsureUserMiddleware


async def main() -> None:
    # Логирование
    setup_logging(level=logging.INFO, log_file=BOT_LOG_FILE)

    # Загружаем настройки из .env (токен, админы, канал и т.д.)
    settings = get_settings()

    # Инициализация БД (создаём таблицы при первом запуске)
    init_db()

    # Инициализация бота
    # В aiogram 3.7.0+ parse_mode нужно передавать через DefaultBotProperties
    session = AiohttpSession(timeout=ClientTimeout(total=60))
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )

    # FSM-хранилище в памяти (для состояний при оформлении заказа и т.п.)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем пользователя по telegram_id при первом обращении
    dp.message.middleware(EnsureUserMiddleware())
    dp.callback_query.middleware(EnsureUserMiddleware())

    # Подключаем актуальные роутеры
    dp.include_router(admin.router)
    dp.include_router(baskets.router)
    dp.include_router(cart.router)
    dp.include_router(courses.router)
    dp.include_router(webapp.router)
    dp.include_router(faq.faq_router)
    dp.include_router(site_chat.site_chat_router)
    dp.include_router(support.support_router)
    dp.include_router(start.router)

    # Старт поллинга
    await bot.delete_webhook(drop_pending_updates=True)
    while True:
        try:
            await dp.start_polling(
                bot,
                polling_timeout=30,
                request_timeout=60
            )    
            break
        except (TelegramNetworkError, ClientError, asyncio.TimeoutError, ServerDisconnectedError) as exc:
            logging.warning(
                "Polling interrupted due to network error: %s. Restarting soon", exc
            )
            await asyncio.sleep(5)
            continue
        except Exception as exc:  # pragma: no cover - unexpected errors
            logging.exception("Unexpected error during polling: %s", exc)
            await asyncio.sleep(5)
            continue


if __name__ == "__main__":
    asyncio.run(main())
