from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from services.cart import (
    get_cart_items,
    clear_cart,
    change_qty,
    remove_from_cart,
    get_cart_total,
)
from utils.texts import format_cart
from keyboards.cart_keyboards import cart_kb
from .checkout import CheckoutState  # из checkout.py
from config import ADMIN_IDS
from services.subscription import ensure_subscribed

router = Router()


async def _update_cart_message(callback: CallbackQuery) -> None:
    """
    Обновить сообщение с корзиной после изменения количества/удаления.
    """
    user_id = callback.from_user.id
    items = get_cart_items(user_id)

    if not items:
        await callback.message.edit_text("🛒 Ваша корзина пока пуста.")
        return

    text = format_cart(items)
    kb = cart_kb(items)
    await callback.message.edit_text(text, reply_markup=kb)


# ---------------------- Показ корзины -----------------------

@router.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    items = get_cart_items(user_id)
    text = format_cart(items)

    if items:
        kb = cart_kb(items)
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text)


@router.message(Command("clear_cart"))
async def clear_user_cart(message: types.Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    clear_cart(user_id)
    await message.answer("🧹 Ваша корзина очищена.")


# ---------------------- Callback-кнопки -----------------------

@router.callback_query(F.data == "cart:nop")
async def cart_nop(callback: CallbackQuery):
    """
    placeholder-кнопка (цифра количества).
    """
    await callback.answer()


@router.callback_query(F.data == "cart:clear")
async def cart_clear_cb(callback: CallbackQuery):
    """
    Очистить корзину по кнопке.
    """
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    clear_cart(user_id)
    await callback.answer("Корзина очищена 🧹")
    await callback.message.edit_text("🛒 Ваша корзина пока пуста.")


# ---------------------- Увеличение количества -----------------------

@router.callback_query(F.data.startswith("cart:inc:"))
async def cart_inc_cb(callback: CallbackQuery):
    """
    Увеличить количество товара.
    Формат: cart:inc:<product_id>
    """
    data = callback.data or ""
    try:
        _, action, product_id = data.split(":")
    except Exception:
        await callback.answer("Ошибка данных 😕", show_alert=True)
        return

    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    change_qty(user_id, product_id, delta=+1)
    await callback.answer("Добавлено")
    await _update_cart_message(callback)


# ---------------------- Уменьшение количества -----------------------

@router.callback_query(F.data.startswith("cart:dec:"))
async def cart_dec_cb(callback: CallbackQuery):
    """
    Уменьшить количество товара.
    Формат: cart:dec:<product_id>
    """
    data = callback.data or ""
    try:
        _, action, product_id = data.split(":")
    except Exception:
        await callback.answer("Ошибка данных 😕", show_alert=True)
        return

    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    change_qty(user_id, product_id, delta=-1)
    await callback.answer("Убрано")
    await _update_cart_message(callback)


# ---------------------- Удаление товара -----------------------

@router.callback_query(F.data.startswith("cart:remove:"))
async def cart_remove_cb(callback: CallbackQuery):
    """
    Удалить товар из корзины.
    Формат: cart:remove:<product_id>
    """
    data = callback.data or ""
    try:
        _, action, product_id = data.split(":")
    except Exception:
        await callback.answer("Ошибка данных 😕", show_alert=True)
        return

    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    remove_from_cart(user_id, product_id)
    await callback.answer("Удалено")
    await _update_cart_message(callback)


# ---------------------- Кнопка «Оформить заказ» -----------------------

@router.callback_query(F.data == "cart:checkout")
async def cart_checkout_cb(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    items = get_cart_items(user_id)

    if not items:
        await callback.answer("🛒 Корзина пуста.", show_alert=True)
        return

    total = get_cart_total(user_id)
    text = format_cart(items)

    await callback.message.answer(
        text
        + "\n\nДавайте оформим заказ. Как вас зовут? 🙂"
    )

    await state.set_state(CheckoutState.waiting_for_name)
    await callback.answer()
