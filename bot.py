import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties  # 👈 ДОБАВИЛИ ЭТОТ ИМПОРТ

from config import get_settings
from database import init_db

from handlers import (
    start,
    baskets,
    courses,
    cart,
    checkout,
    payments,
    admin,
    profile,
)


async def main() -> None:
    # Логирование
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Загружаем настройки из .env (токен, админы, канал и т.д.)
    settings = get_settings()

    # Инициализация БД (создаём таблицы при первом запуске)
    init_db()

    # Инициализация бота
    # В aiogram 3.7.0+ parse_mode нужно передавать через DefaultBotProperties
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # FSM-хранилище в памяти (для состояний при оформлении заказа и т.п.)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем все роутеры
    dp.include_router(start.router)
    dp.include_router(baskets.router)
    dp.include_router(courses.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)
    dp.include_router(profile.router)

    # Старт поллинга
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
