from aiogram import Router, types, F

from services.products import get_baskets
from utils.texts import format_basket_list

router = Router()


@router.message(F.text == "🧺 Корзинки")
async def show_baskets(message: types.Message) -> None:
    baskets = get_baskets()
    if not baskets:
        await message.answer("Список корзинок пока пуст. Попробуйте позже 🙈")
        return

    text = format_basket_list(baskets)
    await message.answer(text, disable_web_page_preview=True)
