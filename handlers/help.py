from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from utils.telegram import answer_with_thread

router = Router()

HELP_MESSAGE = (
    "Весь каталог, корзина, оформление заказов и курсы теперь доступны в WebApp.\n"
    "Запустите WebApp через кнопки в главном меню (товары, мастер-классы, корзина, профиль).\n\n"
    "Бот нужен для /start, проверки подписки и быстрого входа в WebApp."
)


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message) -> None:
    await answer_with_thread(message, HELP_MESSAGE)


@router.callback_query(F.data == "help:main")
async def cb_help_main(callback: CallbackQuery) -> None:
    await answer_with_thread(callback.message, HELP_MESSAGE)
    await callback.answer()


@router.callback_query(F.data == "help:order")
async def cb_help_order(callback: CallbackQuery) -> None:
    await answer_with_thread(callback.message, HELP_MESSAGE)
    await callback.answer()


@router.callback_query(F.data == "help:payment")
async def cb_help_payment(callback: CallbackQuery) -> None:
    await answer_with_thread(callback.message, HELP_MESSAGE)
    await callback.answer()


@router.callback_query(F.data == "help:course")
async def cb_help_course(callback: CallbackQuery) -> None:
    await answer_with_thread(callback.message, HELP_MESSAGE)
    await callback.answer()
