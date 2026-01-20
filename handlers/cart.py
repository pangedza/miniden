from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from keyboards.cart_keyboards import cart_kb
from services import cart as cart_service
from services import menu_catalog
from services.subscription import ensure_subscribed
from handlers.checkout import start_checkout_flow

router = Router()

EMPTY_CART_MESSAGE = "Корзина пуста. Добавьте товары из каталога."


def _format_cart_text(items: list[dict], total: int, removed_ids: list[int]) -> str:
    if not items:
        return EMPTY_CART_MESSAGE

    lines = ["🛒 Ваша корзина:"]
    for index, item in enumerate(items, start=1):
        name = item.get("name") or "Без названия"
        qty = int(item.get("qty", 1))
        price = int(item.get("price", 0))
        subtotal = qty * price
        lines.append(f"{index}. {name} — {qty} × {price} ₽ = {subtotal} ₽")

    lines.append(f"\nИтого: {total} ₽")

    if removed_ids:
        removed_text = ", ".join(str(pid) for pid in removed_ids)
        lines.append(f"\n⚠️ Недоступные позиции удалены: {removed_text}")

    return "\n".join(lines)


def _parse_cart_item_callback(data: str) -> tuple[str | None, int | None]:
    parts = data.split(":")
    if len(parts) == 4:
        _, _, raw_type, raw_id = parts
    elif len(parts) == 3:
        _, _, raw_id = parts
        raw_type = "product"
    else:
        return None, None

    try:
        product_id = int(raw_id)
    except (TypeError, ValueError):
        return None, None

    normalized_type = menu_catalog.map_legacy_item_type(raw_type) or raw_type or "product"
    if normalized_type not in menu_catalog.MENU_ITEM_TYPES:
        normalized_type = "product"

    return normalized_type, product_id


async def _send_cart(message: types.Message, *, edit: bool = False) -> None:
    user_id = message.from_user.id
    items, removed_ids = cart_service.get_cart_items(user_id)
    total = sum(int(item.get("price", 0)) * int(item.get("qty", 0)) for item in items)
    text = _format_cart_text(items, total, removed_ids)
    keyboard = cart_kb(items) if items else None

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


@router.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await _send_cart(message)


@router.message(Command("clear_cart"))
async def clear_user_cart(message: types.Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    cart_service.clear_cart(user_id)
    await message.answer("Корзина очищена.")


@router.callback_query(F.data == "cart:nop")
async def cart_nop(callback: CallbackQuery):
    """Ответ на placeholder-кнопку."""
    await callback.answer()


@router.callback_query(F.data == "cart:clear")
async def cart_clear_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    cart_service.clear_cart(user_id)
    if callback.message:
        await callback.message.edit_text("Корзина очищена.")
    await callback.answer()


@router.callback_query(F.data.startswith("cart:inc:"))
async def cart_inc_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    item_type, product_id = _parse_cart_item_callback(callback.data or "")
    if item_type is None or product_id is None:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    cart_service.change_qty(user_id, product_id, delta=1, product_type=item_type)
    if callback.message:
        await _send_cart(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("cart:dec:"))
async def cart_dec_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    item_type, product_id = _parse_cart_item_callback(callback.data or "")
    if item_type is None or product_id is None:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    cart_service.change_qty(user_id, product_id, delta=-1, product_type=item_type)
    if callback.message:
        await _send_cart(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("cart:remove:"))
async def cart_remove_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    item_type, product_id = _parse_cart_item_callback(callback.data or "")
    if item_type is None or product_id is None:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    cart_service.remove_from_cart(user_id, product_id, product_type=item_type)
    if callback.message:
        await _send_cart(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "cart:checkout")
async def cart_checkout_cb(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    if callback.message:
        await start_checkout_flow(callback.message, state)
    await callback.answer()
