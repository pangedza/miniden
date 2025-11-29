from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery

from config import ADMIN_IDS, get_settings
from services import auth_sessions as auth_sessions_service
from services import users as users_service
from keyboards.main_menu import get_main_menu
from services.subscription import (
    ensure_subscribed,
    get_subscription_keyboard,
    is_user_subscribed,
)
from utils.texts import format_start_text, format_subscription_required_text

router = Router()


async def _send_subscription_invite(target_message) -> None:
    await target_message.answer(
        format_subscription_required_text(),
        reply_markup=get_subscription_keyboard(),
    )


async def _handle_deep_link_auth(message: types.Message, payload: str) -> bool:
    if not payload.startswith("auth_"):
        return False

    token = payload.removeprefix("auth_").strip()
    if not token:
        await message.answer("Некорректная ссылка авторизации. Сгенерируйте новую на сайте.")
        return True

    users_service.get_or_create_user_from_telegram(
        {
            "id": message.from_user.id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
        }
    )

    if not auth_sessions_service.attach_telegram_id(token, message.from_user.id):
        await message.answer("Ссылка авторизации устарела или неверна. Попробуйте авторизоваться на сайте заново.")
        return True

    await message.answer("Вы авторизованы! Вернитесь на сайт.")
    return True


# -------------------------------------------------------------------
#   Экран приветствия /start
# -------------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    payload = (message.text or "").split(maxsplit=1)
    deep_link = payload[1] if len(payload) > 1 else ""
    if deep_link and await _handle_deep_link_auth(message, deep_link):
        return

    if await ensure_subscribed(message, message.bot, is_admin=is_admin):
        await _send_start_screen(message, is_admin=is_admin)


# -------------------------------------------------------------------
#   Кнопка «🔵 Старт» — ПЕРВИЧНАЯ ПРОВЕРКА ПОДПИСКИ
# -------------------------------------------------------------------


@router.message(F.text == "🔵 Старт")
async def start_button(message: types.Message):
    """
    Обработка нажатия на кнопку «🔵 Старт».

    1) Проверяем подписку на канал.
    2) Если подписан — показываем главное меню.
    3) Если нет — показываем экран с просьбой подписаться.
    """
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if await ensure_subscribed(message, message.bot, is_admin=is_admin):
        await _send_start_screen(message, is_admin=is_admin)


# -------------------------------------------------------------------
#   Кнопка «✅ Я подписался» под сообщением о подписке
# -------------------------------------------------------------------


@router.callback_query(F.data == "sub_check:start")
async def cb_check_subscription(callback: CallbackQuery):
    """
    Обработка нажатия на кнопку «✅ Я подписался».

    Ещё раз проверяем подписку:
    - если подписан — показываем главное меню.
    - если нет — показываем alert и оставляем всё как есть.
    """
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if is_admin or await is_user_subscribed(callback.message.bot, user_id):
        try:
            await callback.message.delete()
        except Exception:
            pass

        await _send_start_screen(callback.message, is_admin=is_admin)
        await callback.answer("✅ Спасибо, подписка подтверждена!")
    else:
        await callback.answer(
            "❌ Подписка не найдена. Подпишитесь на канал и нажмите «Я подписался» ещё раз.",
            show_alert=True,
        )
        await _send_subscription_invite(callback.message)


async def _send_start_screen(message: types.Message, is_admin: bool) -> None:
    settings = get_settings()
    main_menu = get_main_menu(is_admin=is_admin)
    banner = settings.banner_start or settings.start_banner_id

    if banner:
        await message.answer_photo(
            photo=banner,
            caption=format_start_text(),
            reply_markup=main_menu,
        )
    else:
        await message.answer(
            format_start_text(),
            reply_markup=main_menu,
        )
