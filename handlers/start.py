from aiogram import Router, types
from aiogram.filters import CommandStart

from keyboards.main_menu import main_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    text = (
        "Привет! 🧶\n\n"
        "Это бот-магазин корзинок и онлайн-курсов по вязанию.\n\n"
        "Выберите, что вас интересует:"
    )
    await message.answer(text, reply_markup=main_menu_kb())
