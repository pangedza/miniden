from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command(commands=["checkout", "order"]))
async def checkout(message: types.Message) -> None:
    await message.answer(
        "Здесь будет оформление заказа. \n"
        "Пока вы можете написать мне в личные сообщения, чтобы завершить покупку ❤️"
    )
