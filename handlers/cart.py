from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from services.subscription import ensure_subscribed

router = Router()

WEBAPP_CART_MESSAGE = (
    "Корзина теперь открывается только в WebApp.\n"
    "Нажмите «🛒 Корзина (WebApp)» в главном меню."
)


@router.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await message.answer(WEBAPP_CART_MESSAGE)


@router.message(Command("clear_cart"))
async def clear_user_cart(message: types.Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await message.answer(WEBAPP_CART_MESSAGE)


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

    await callback.message.answer(WEBAPP_CART_MESSAGE)
    await callback.answer()


@router.callback_query(F.data.startswith("cart:inc:"))
async def cart_inc_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await callback.message.answer(WEBAPP_CART_MESSAGE)
    await callback.answer()


@router.callback_query(F.data.startswith("cart:dec:"))
async def cart_dec_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await callback.message.answer(WEBAPP_CART_MESSAGE)
    await callback.answer()


@router.callback_query(F.data.startswith("cart:remove:"))
async def cart_remove_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await callback.message.answer(WEBAPP_CART_MESSAGE)
    await callback.answer()


@router.callback_query(F.data == "cart:checkout")
async def cart_checkout_cb(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await state.clear()
    await callback.message.answer(WEBAPP_CART_MESSAGE)
    await callback.answer()
