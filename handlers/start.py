from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from config import ADMIN_IDS, get_settings
from keyboards.main_menu import get_main_menu, get_start_keyboard

router = Router()


def _welcome_text() -> str:
    """
    Текст приветствия, когда пользователь допущен в бот.
    """
    return (
        "Привет! 👋\n\n"
        "Это бот-магазин MiniDeN:\n"
        "— корзинки ручной работы\n"
        "— онлайн-курсы по вязанию\n\n"
        "Выберите нужный раздел ниже 👇"
    )


def _subscription_text() -> str:
    """
    Текст, когда пользователь должен подписаться на канал.
    """
    return (
        "Чтобы пользоваться ботом и оформлять заказы, нужно быть подписанным "
        "на наш канал 📣\n\n"
        "1️⃣ Подпишитесь на канал по кнопке ниже.\n"
        "2️⃣ После этого нажмите «✅ Я подписался» или снова «🔵 Старт».\n\n"
        "Без подписки продолжить работу с ботом нельзя."
    )


def _subscription_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    """
    Кнопки под сообщением о подписке:
    - переход в канал
    - проверка подписки
    """
    buttons: list[list[InlineKeyboardButton]] = []

    if channel_link:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="📎 Перейти в канал",
                    url=channel_link,
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="✅ Я подписался",
                callback_data="sub:check",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _is_user_subscribed(bot, user_id: int) -> bool:
    """
    Проверка, подписан ли пользователь на канал.

    Возвращает True, если:
    - канал не настроен (REQUIRED_CHANNEL_ID не задан)
    - или пользователь является участником канала.
    """
    settings = get_settings()
    channel_id = settings.required_channel_id

    # Если канал не задан — считаем, что проверка отключена
    if not channel_id:
        return True

    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        status = getattr(member, "status", None)
        # Считаем подписанным, если он участник, админ или создатель
        return status in ("member", "administrator", "creator")
    except Exception as e:
        # Если не удалось получить статус — считаем, что НЕ подписан
        # и пишем ошибку в логи для отладки.
        print("❗ Ошибка проверки подписки:", repr(e))
        return False


def _get_channel_link() -> str:
    """
    Вернуть ссылку на канал:
    - сначала берём REQUIRED_CHANNEL_LINK из .env, если есть
    - если нет, а REQUIRED_CHANNEL_ID — это @username, собираем https://t.me/username
    """
    settings = get_settings()
    if settings.required_channel_link:
        return settings.required_channel_link

    cid = settings.required_channel_id
    if cid and cid.startswith("@"):
        return f"https://t.me/{cid.lstrip('@')}"

    # Если нет ни ссылки, ни username — вернём пустую строку
    return ""


# -------------------------------------------------------------------
#   /start — всегда показывает только кнопку «🔵 Старт», без меню
# -------------------------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    /start:
    - показываем приветствие
    - даём только клавиатуру с кнопкой «🔵 Старт»
    - проверка подписки будет выполняться по нажатию на «Старт»
    """
    await message.answer(
        "Привет! 👋\n\n"
        "Нажмите кнопку <b>«🔵 Старт»</b> ниже, чтобы бот проверил подписку "
        "и открыл меню.",
        reply_markup=get_start_keyboard(),
    )


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

    if await _is_user_subscribed(message.bot, user_id):
        # Пользователь подписан — показываем полноценное меню
        await message.answer(
            _welcome_text(),
            reply_markup=get_main_menu(is_admin=is_admin),
        )
    else:
        # Пользователь НЕ подписан — просим подписаться.
        channel_link = _get_channel_link()
        await message.answer(
            _subscription_text(),
            reply_markup=_subscription_keyboard(channel_link),
        )


# -------------------------------------------------------------------
#   Кнопка «✅ Я подписался» под сообщением о подписке
# -------------------------------------------------------------------


@router.callback_query(F.data == "sub:check")
async def cb_check_subscription(callback: CallbackQuery):
    """
    Обработка нажатия на кнопку «✅ Я подписался».

    Ещё раз проверяем подписку:
    - если подписан — показываем главное меню.
    - если нет — показываем alert и оставляем всё как есть.
    """
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if await _is_user_subscribed(callback.message.bot, user_id):
        # Подписка подтверждена
        try:
            await callback.message.delete()
        except Exception:
            pass

        await callback.message.answer(
            _welcome_text(),
            reply_markup=get_main_menu(is_admin=is_admin),
        )
        await callback.answer("Подписка подтверждена ✅")
    else:
        await callback.answer(
            "Похоже, вы ещё не подписаны на канал 🙈\n"
            "Подпишитесь и затем снова нажмите «🔵 Старт» или «✅ Я подписался».",
            show_alert=True,
        )
