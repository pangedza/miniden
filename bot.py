import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import get_settings
from handlers import start, baskets, courses, cart, checkout, payments


async def main() -> None:
    settings = get_settings()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Регистрируем роутеры
    dp.include_router(start.router)
    dp.include_router(baskets.router)
    dp.include_router(courses.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)
    dp.include_router(payments.router)

    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
