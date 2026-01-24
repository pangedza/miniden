import json
import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from config import get_settings
from services import menu_catalog, orders as orders_service, users as users_service
from services.cart import add_to_cart
from utils.texts import format_order_for_admin, format_price

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


def _build_cart_keyboard() -> InlineKeyboardMarkup | None:
    settings = get_settings()
    cart_url = settings.webapp_cart_url or settings.webapp_index_url
    if not cart_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть корзину", web_app=WebAppInfo(url=cart_url))]
        ]
    )


def _build_order_user_keyboard(order_id: int | None) -> InlineKeyboardMarkup:
    settings = get_settings()
    inline_keyboard: list[list[InlineKeyboardButton]] = []

    admin_chat_id = settings.admin_chat_id
    if admin_chat_id:
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text="Связаться с админом",
                    url=f"tg://user?id={admin_chat_id}",
                )
            ]
        )

    cancel_callback = f"webapp:order:cancel:{order_id or 0}"
    inline_keyboard.append(
        [InlineKeyboardButton(text="Отменить заказ", callback_data=cancel_callback)]
    )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _parse_webapp_order_payload(payload: dict) -> tuple[list[dict], int] | None:
    payload_type = payload.get("type")
    cart: dict | None = None
    items: list | None = None
    raw_total = None

    if payload_type == "webapp_order":
        cart = payload.get("cart")
        if not isinstance(cart, dict):
            logging.warning("webapp_order payload without cart: %s", payload)
            return None
        items = cart.get("items")
        raw_total = cart.get("total")
    elif payload_type is None and payload.get("telegram_id") and isinstance(payload.get("items"), list):
        items = payload.get("items")
        raw_total = payload.get("total")
        logging.info("Legacy webapp order payload detected")
    else:
        return None

    if not isinstance(items, list):
        logging.warning("webapp order payload without items list: %s", payload)
        return None

    parsed_items: list[dict] = []
    total_from_items = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id") or item.get("product_id") or item.get("item_id")
        try:
            product_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        try:
            qty = int(item.get("qty") or 0)
        except (TypeError, ValueError):
            qty = 0
        try:
            price = int(float(item.get("price") or 0))
        except (TypeError, ValueError):
            price = 0
        if qty <= 0:
            continue
        total_from_items += price * qty
        title = item.get("title") or item.get("name") or f"Товар #{product_id}"
        parsed_items.append(
            {
                "product_id": product_id,
                "name": title,
                "qty": qty,
                "price": price,
                "type": item.get("type") or "basket",
            }
        )

    if not parsed_items:
        logging.warning("webapp order payload has no valid items: %s", payload)
        return None

    try:
        total = int(float(raw_total))
    except (TypeError, ValueError):
        total = total_from_items

    if total <= 0:
        total = total_from_items

    return parsed_items, total


def _is_valid_adminsite_item(item: dict) -> bool:
    return isinstance(item, dict) and item.get("id") is not None


async def _handle_adminsite_payload(message: Message, payload: dict) -> None:
    if payload.get("source") not in {"adminsite", "menu"}:
        return

    items = payload.get("items")
    if not isinstance(items, list):
        logging.warning("Некорректный items в adminsite payload: %s", items)
        return

    payload_type = payload.get("type")
    mapped_type = payload_type if payload_type in menu_catalog.MENU_ITEM_TYPES else "product"

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

        item_type = item.get("type") if item.get("type") in menu_catalog.MENU_ITEM_TYPES else mapped_type
        if item_type in menu_catalog.MENU_ITEM_TYPES:
            menu_item = menu_catalog.get_item_by_id(product_id, include_inactive=False, item_type=item_type)
            if not menu_item:
                logging.warning("Menu item not found for adminsite payload: %s", item)
                continue
        try:
            add_to_cart(
                user_id=message.from_user.id,
                product_id=product_id,
                product_type=item_type,
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
    logging.info(
        "web_app_data received from user %s: %s",
        getattr(message.from_user, "id", None),
        raw,
    )
    try:
        data = json.loads(raw)
    except Exception:
        logging.exception("Не удалось разобрать web_app_data: %s", raw)
        return

    should_handle_order = data.get("type") == "webapp_order" or (
        data.get("type") is None
        and data.get("telegram_id")
        and isinstance(data.get("items"), list)
    )
    if should_handle_order:
        webapp_order = _parse_webapp_order_payload(data)
        if webapp_order is None:
            logging.warning("Не удалось распознать заказ из web_app_data: %s", data)
            await message.answer("Не удалось распознать заказ. Попробуйте ещё раз из корзины.")
            return
        items, total = webapp_order
        user_name = (
            message.from_user.full_name
            if message.from_user.full_name
            else message.from_user.username or "Пользователь"
        )
        user_record = users_service.get_user_by_telegram_id(message.from_user.id)
        contact = user_record.phone if user_record and user_record.phone else ""
        order_text = format_order_for_admin(
            user_id=message.from_user.id,
            user_name=user_name,
            items=items,
            total=total,
            customer_name=user_name,
            contact=contact,
            comment="",
        )
        order_id = orders_service.add_order(
            user_id=message.from_user.id,
            user_name=user_name,
            items=items,
            total=total,
            customer_name=user_name,
            contact=contact,
            comment="",
            order_text=order_text,
        )

        lines = ["✅ Заказ принят", "", "🛒 Ваш заказ:"]
        for idx, item in enumerate(items, start=1):
            subtotal = int(item.get("price", 0)) * int(item.get("qty", 0))
            lines.append(
                f"{idx}) {item.get('name')} — {format_price(item.get('price', 0))} x {item.get('qty')} = {format_price(subtotal)}"
            )
        lines.append("")
        lines.append(f"Итого: <b>{format_price(total)}</b>")
        await message.answer(
            "\n".join(lines),
            reply_markup=_build_order_user_keyboard(order_id),
        )

        settings = get_settings()
        admin_ids = settings.admin_ids or set()
        if admin_ids:
            admin_message = order_text.replace(
                "🆕 <b>Новый заказ</b>", "📦 <b>Новый заказ</b>", 1
            )
            for admin_id in admin_ids:
                try:
                    await message.bot.send_message(admin_id, admin_message)
                except Exception:
                    logging.exception("Не удалось отправить заказ админу %s", admin_id)
        return

    product_id = data.get("product_id")
    qty_raw = data.get("qty") or 1

    try:
        qty_int = max(int(qty_raw), 1)
    except (TypeError, ValueError):
        logging.warning("Некорректный qty в web_app_data: %s", qty_raw)
        qty_int = 1

    if data.get("source") in {"adminsite", "menu"}:
        await _handle_adminsite_payload(message, data)
        return

    if data.get("action") != "add_to_cart":
        return

    if product_id is None:
        return

    try:
        product_id_int = int(str(product_id))
    except (TypeError, ValueError):
        logging.warning("Некорректный product_id в web_app_data: %s", product_id)
        return

    product_type = data.get("type")
    resolved_type = menu_catalog.map_legacy_item_type(product_type) or "product"
    product = menu_catalog.get_item_by_id(
        product_id_int, include_inactive=False, item_type=resolved_type
    )
    if not product:
        logging.warning("Товар с id=%s не найден для web_app_data", product_id_int)
        return

    try:
        add_to_cart(
            user_id=message.from_user.id,
            product_id=product_id_int,
            product_type=resolved_type or product.get("type") or "product",
            qty=qty_int,
        )
    except Exception:
        logging.exception("Ошибка при добавлении товара из WebApp в корзину")
        return

    product_name = product.get("title") or product.get("name") or f"Товар #{product_id_int}"
    keyboard = _build_cart_keyboard()
    response_text = f"✅ Добавлено в корзину: {product_name} (x{qty_int}). Открыть корзину?"
    if keyboard:
        await message.answer(response_text, reply_markup=keyboard)
    else:
        await message.answer(f"{response_text}\n\nНажми 🛒 Корзина")


@router.callback_query(F.data.startswith("webapp:order:cancel:"))
async def handle_webapp_order_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Отмена заказа пока недоступна", show_alert=True)
