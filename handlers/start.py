from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import CallbackQuery

from config import ADMIN_IDS, get_settings
from database import get_session
from models import AuthSession
from services import users as users_service
from keyboards.main_menu import get_main_menu
from services.bot_config import NodeView, load_node
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


def _ensure_user_exists(telegram_user: types.User) -> None:
    users_service.get_or_create_user_from_telegram(
        {
            "id": telegram_user.id,
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
        }
    )


# -------------------------------------------------------------------
#   Экран приветствия /start
# -------------------------------------------------------------------


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: types.Message, command: CommandObject):
    """
    /start auth_<token>
    Этот обработчик вызывается, когда пользователь переходит из сайта в бота по ссылке
    https://t.me/BotMiniden_bot?start=auth_<token>.
    """
    payload = (command.args or "").strip()
    if not payload.startswith("auth_"):
        # обычный /start без авторизации, тут оставляем текущую приветственную логику
        # (если уже есть handler для CommandStart без deep_link — НЕ ломать его)
        return

    token = payload[len("auth_") :]

    _ensure_user_exists(message.from_user)

    # связываем token ↔ telegram_id
    with get_session() as s:
        session = s.query(AuthSession).filter(AuthSession.token == token).first()
        if not session:
            await message.answer("Ссылка для авторизации устарела или неверна. Попробуйте начать авторизацию на сайте заново.")
            return

        session.telegram_id = message.from_user.id

    await message.answer(
        "✅ Авторизация для сайта выполнена!\n\n"
        "Вернитесь в браузер и обновите страницу — ваш профиль и корзина будут доступны."
    )


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    _ensure_user_exists(message.from_user)

    payload = (message.text or "").split(maxsplit=1)
    deep_link = payload[1] if len(payload) > 1 else ""
    if deep_link.startswith("auth_"):
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

    _ensure_user_exists(message.from_user)

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
    if await _send_dynamic_start_screen(message):
        return

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


async def _send_dynamic_start_screen(message: types.Message) -> bool:
    start_node = load_node("MAIN_MENU")
    if not start_node:
        return False

    await _send_node_message(message, start_node)
    return True


async def _send_node_message(message: types.Message, node: NodeView) -> None:
    settings = get_settings()
    keyboard = node.keyboard
    photo = node.image_url or settings.banner_start or settings.start_banner_id

    if photo:
        await message.answer_photo(
            photo=photo,
            caption=node.message_text,
            parse_mode=node.parse_mode,
            reply_markup=keyboard,
        )
    else:
        await message.answer(
            node.message_text,
            parse_mode=node.parse_mode,
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("OPEN_NODE:"))
async def handle_open_node(callback: CallbackQuery):
    _, node_code = callback.data.split(":", maxsplit=1)
    node = load_node(node_code)

    if not node:
        await callback.answer("Раздел временно недоступен", show_alert=True)
        return

    await _send_node_message(callback.message, node)
    await callback.answer()


@router.callback_query(F.data.startswith("SEND_TEXT:"))
async def handle_send_text(callback: CallbackQuery):
    _, node_code = callback.data.split(":", maxsplit=1)
    node = load_node(node_code)

    if not node:
        await callback.answer("Элемент недоступен", show_alert=True)
        return

    await callback.message.answer(
        node.message_text,
        parse_mode=node.parse_mode,
        reply_markup=node.keyboard,
    )
    await callback.answer()
