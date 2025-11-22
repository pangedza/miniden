import json
import logging

from aiogram import F, Router
from aiogram.types import Message

from services.cart import add_to_cart
from services.products import get_product_by_id

router = Router()


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message) -> None:
    """
    Обработка данных, пришедших из Telegram WebApp (sendData).
    Ожидается JSON: {"action": "add_to_cart", "product_id": ..., "source": "..."}.
    """

    if not message.web_app_data or not message.web_app_data.data:
        return

    raw = message.web_app_data.data
    try:
        data = json.loads(raw)
    except Exception:
        logging.exception("Не удалось разобрать web_app_data: %s", raw)
        return

    if data.get("action") != "add_to_cart":
        return

    product_id = data.get("product_id")
    if product_id is None:
        return

    try:
        product_id_int = int(str(product_id))
    except (TypeError, ValueError):
        logging.warning("Некорректный product_id в web_app_data: %s", product_id)
        return

    product = get_product_by_id(product_id_int)
    if not product:
        logging.warning("Товар с id=%s не найден для web_app_data", product_id_int)
        return

    name = product.get("name", "Товар")
    price = int(product.get("price", 0) or 0)

    try:
        add_to_cart(
            user_id=message.from_user.id,
            product_id=str(product_id_int),
            name=name,
            price=price,
            qty=1,
        )
    except Exception:
        logging.exception("Ошибка при добавлении товара из WebApp в корзину")
        return

    # Можно не отправлять ответ, чтобы не спамить в чат
    # await message.answer("✅ Товар добавлен в корзину")
