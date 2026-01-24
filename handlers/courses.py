from aiogram import F, Router, types
from aiogram.types import CallbackQuery

from config import ADMIN_IDS
from utils.telegram import answer_with_thread
from services.subscription import ensure_subscribed

router = Router()

WEBAPP_COURSES_MESSAGE = (
    "Курсы и мастер-классы теперь доступны в WebApp.\n"
    "Нажмите «🎓 Мастер-классы (WebApp)» в главном меню, чтобы открыть каталог."
)


@router.message(F.text == "🎓 Курсы")
async def courses_entry(message: types.Message) -> None:
    """Сообщение о переносе каталога курсов в WebApp."""
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await answer_with_thread(message, WEBAPP_COURSES_MESSAGE)


@router.callback_query(F.data.startswith("courses:list:"))
async def courses_list_callback(callback: CallbackQuery) -> None:
    """Ответ на старые callback-кнопки списка курсов."""
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await answer_with_thread(callback.message, WEBAPP_COURSES_MESSAGE)
    await callback.answer()


@router.callback_query(F.data.startswith("catalog:"))
async def courses_catalog_callback(callback: CallbackQuery) -> None:
    """Ответ на старые callback-кнопки каталога курсов."""
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    data = callback.data or ""
    try:
        parts = data.split(":")
        if len(parts) < 3:
            raise ValueError
        _, _action, section = parts[:3]
        if section != "courses":
            return
    except Exception:
        await callback.answer("Некорректные данные запроса 😕", show_alert=True)
        return

    await answer_with_thread(callback.message, WEBAPP_COURSES_MESSAGE)
    await callback.answer()


@router.callback_query(F.data.startswith("cart:add:course:"))
async def add_course_to_cart(callback: CallbackQuery) -> None:
    """Ответ на старые кнопки добавления курса в корзину."""
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await answer_with_thread(callback.message, WEBAPP_COURSES_MESSAGE)
    await callback.answer()
