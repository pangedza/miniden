from aiogram import Router, types, F

router = Router()


@router.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message) -> None:
    # Здесь позже можно будет показать реальные товары из корзины
    await message.answer(
        "Пока мы показываем только список товаров. \n"
        "Логика корзины и оформления заказа будет добавлена позже 🛒"
    )
