from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_IDS, get_settings
from services.subscription import ensure_subscribed

router = Router()

PROFILE_BUTTON_TEXT = "👤 Профиль"

WEBAPP_PROFILE_MESSAGE = (
    "Ваш профиль, заказы и доступ к курсам теперь доступны в WebApp.\n"
    "Откройте его через кнопку «👤 Профиль (WebApp)» в главном меню."
)


def _build_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Открыть профиль в WebApp", callback_data="profile:webapp")]]
    )


@router.message(Command("profile"))
@router.message(F.text == PROFILE_BUTTON_TEXT)
async def show_profile(message: types.Message) -> None:
    telegram_id = message.from_user.id
    is_admin = telegram_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    banner = get_settings().banner_profile
    if banner:
        await message.answer_photo(photo=banner, caption="👤 Ваш профиль")

    await message.answer(WEBAPP_PROFILE_MESSAGE, reply_markup=_build_profile_keyboard())


@router.message(F.text == "❤️ Избранное")
async def show_favorites(message: types.Message) -> None:
    """Перенаправление раздела избранного в WebApp."""
    telegram_id = message.from_user.id
    is_admin = telegram_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await message.answer(WEBAPP_PROFILE_MESSAGE, reply_markup=_build_profile_keyboard())


@router.callback_query(F.data == "profile:orders:active")
async def profile_orders_active(callback: types.CallbackQuery) -> None:
    telegram_id = callback.from_user.id
    is_admin = telegram_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await callback.message.answer(WEBAPP_PROFILE_MESSAGE, reply_markup=_build_profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:orders:finished")
async def profile_orders_finished(callback: types.CallbackQuery) -> None:
    telegram_id = callback.from_user.id
    is_admin = telegram_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await callback.message.answer(WEBAPP_PROFILE_MESSAGE, reply_markup=_build_profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:courses")
async def profile_courses(callback: types.CallbackQuery) -> None:
    telegram_id = callback.from_user.id
    is_admin = telegram_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await callback.message.answer(WEBAPP_PROFILE_MESSAGE, reply_markup=_build_profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:webapp")
async def profile_open_webapp(callback: types.CallbackQuery) -> None:
    telegram_id = callback.from_user.id
    is_admin = telegram_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await callback.message.answer(WEBAPP_PROFILE_MESSAGE, reply_markup=_build_profile_keyboard())
    await callback.answer()
