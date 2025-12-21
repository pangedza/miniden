import logging
from typing import Any

from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMIN_IDS, get_settings
from utils.texts import format_subscription_required_text


def _get_channel_identifier() -> Any:
    """Вернёт chat_id/username для проверки подписки."""

    settings = get_settings()

    if settings.required_channel_id is not None:
        return settings.required_channel_id

    return None


def _get_channel_link() -> str | None:
    settings = get_settings()

    if settings.required_channel_link:
        return settings.required_channel_link

    channel_identifier = settings.required_channel_id
    if isinstance(channel_identifier, str) and channel_identifier:
        return f"https://t.me/{channel_identifier}"

    return None


def guess_channel_link(channels: list[str], explicit_link: str | None = None) -> str | None:
    if explicit_link:
        return explicit_link

    for channel in channels:
        normalized = (channel or "").strip()
        if not normalized:
            continue
        if normalized.startswith("http"):
            return normalized
        if normalized.startswith("@"):
            return f"https://t.me/{normalized.lstrip('@')}"
        return f"https://t.me/{normalized}"
    return None


def get_subscription_keyboard(
    callback_data: str = "sub_check:start",
    *,
    subscribe_url: str | None = None,
    channels: list[str] | None = None,
    subscribe_button_text: str = "📢 Подписаться на канал",
    check_button_text: str = "✅ Я подписался",
) -> InlineKeyboardMarkup:
    """Единая клавиатура для приглашения подписаться."""

    buttons: list[list[InlineKeyboardButton]] = []
    channel_link = guess_channel_link(channels or [], subscribe_url) or _get_channel_link()

    if channel_link:
        buttons.append(
            [InlineKeyboardButton(text=subscribe_button_text, url=channel_link)]
        )

    buttons.append([InlineKeyboardButton(text=check_button_text, callback_data=callback_data)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def check_channels_subscription(
    bot: Bot, user_id: int, channels: list[str]
) -> tuple[bool, str | None]:
    """
    Проверяет подписку пользователя на список каналов.

    Возвращает (is_ok, error_message). Если error_message не None — проблема на стороне Telegram.
    """

    normalized_channels = [ch.strip() for ch in channels if (ch or "").strip()]
    if not normalized_channels:
        return True, None

    for channel in normalized_channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "Не удалось проверить подписку для chat_id=%s: %s", channel, exc
            )
            return False, "error"

        status = getattr(member, "status", None)
        if status in {"left", "kicked"}:
            return False, None

    return True, None


async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
    """Проверка статуса участника канала из глобальных настроек."""

    chat_id = _get_channel_identifier()

    if chat_id is None:
        return True

    ok, _ = await check_channels_subscription(bot, user_id, [chat_id])
    return ok


async def ensure_subscribed(
    message_or_callback: Message | CallbackQuery,
    bot: Bot,
    *,
    is_admin: bool = False,
) -> bool:
    """
    Проверяет подписку и, при необходимости, отправляет приглашение.

    Возвращает True, если можно продолжать выполнение хендлера.
    """

    user_id = message_or_callback.from_user.id

    if is_admin or user_id in ADMIN_IDS:
        return True

    if await is_user_subscribed(bot, user_id):
        return True

    keyboard = get_subscription_keyboard()
    text = format_subscription_required_text()

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.answer(text, reply_markup=keyboard)
        try:
            await message_or_callback.answer(
                "Подписка на канал обязательна для продолжения.", show_alert=True
            )
        except Exception:  # noqa: BLE001
            pass
    else:
        await message_or_callback.answer(text, reply_markup=keyboard)

    return False
