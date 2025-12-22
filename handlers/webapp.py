import json
import logging

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from config import get_settings
from services.cart import add_to_cart
from services.products import get_product_by_id

router = Router()


def _build_adminsite_menu() -> InlineKeyboardMarkup:
    settings = get_settings()
    cart_url = settings.webapp_cart_url or settings.webapp_index_url

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    if cart_url:
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text="Оплатить сейчас",
                    web_app=WebAppInfo(url=cart_url),
                )
            ]
        )
    inline_keyboard.append(
        [InlineKeyboardButton(text="Связаться в чат", callback_data="contact_manager")]
    )
    if cart_url:
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text="Корзина",
                    web_app=WebAppInfo(url=cart_url),
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _is_valid_adminsite_item(item: dict) -> bool:
    return isinstance(item, dict) and item.get("id") is not None


async def _handle_adminsite_payload(message: Message, payload: dict) -> None:
    if payload.get("source") != "adminsite":
        return

    items = payload.get("items")
    if not isinstance(items, list):
        logging.warning("Некорректный items в adminsite payload: %s", items)
        return

    mapped_type = "course" if payload.get("type") == "course" else "basket"

    added_count = 0
    for item in items:
        if not _is_valid_adminsite_item(item):
            continue
        try:
            product_id = int(item.get("id"))
            qty = int(item.get("qty") or 1)
            qty = max(qty, 1)
        except (TypeError, ValueError):
            logging.warning("Некорректный item в adminsite payload: %s", item)
            continue

        try:
            add_to_cart(
                user_id=message.from_user.id,
                product_id=product_id,
                product_type=mapped_type,
                qty=qty,
            )
        except Exception:
            logging.exception(
                "Ошибка при добавлении товара из adminsite web_app_data: %s", item
            )
            continue
        added_count += 1

    reply_markup = _build_adminsite_menu()
    await message.answer(
        f"Добавлено: {added_count} позиций", reply_markup=reply_markup, disable_notification=True
    )


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message) -> None:
    """
    Обработка данных, пришедших из Telegram WebApp (sendData).
    Ожидается JSON: {"action": "add_to_cart", "product_id": ..., "source": "..."}.
    """

    if not message.web_app_data or not message.web_app_data.data:
        return

    if not message.from_user:
        logging.warning("web_app_data received without from_user")
        return

    raw = message.web_app_data.data
    try:
        data = json.loads(raw)
    except Exception:
        logging.exception("Не удалось разобрать web_app_data: %s", raw)
        return

    if data.get("source") == "adminsite":
        await _handle_adminsite_payload(message, data)
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

    try:
        add_to_cart(
            user_id=message.from_user.id,
            product_id=product_id_int,
            product_type=product.get("type") or "basket",
            qty=1,
        )
    except Exception:
        logging.exception("Ошибка при добавлении товара из WebApp в корзину")
        return

    # Можно не отправлять ответ, чтобы не спамить в чат
    # await message.answer("✅ Товар добавлен в корзину")
