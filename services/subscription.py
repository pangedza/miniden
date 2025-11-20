import logging
from typing import Any

from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import REQUIRED_CHANNEL_ID, REQUIRED_CHANNEL_USERNAME, get_settings
from utils.texts import format_subscription_required_text


def _get_channel_identifier() -> Any:
    """Вернёт chat_id/username для проверки подписки."""

    if REQUIRED_CHANNEL_ID is not None:
        return REQUIRED_CHANNEL_ID
    return REQUIRED_CHANNEL_USERNAME


def _get_channel_link() -> str | None:
    settings = get_settings()

    if settings.required_channel_link:
        return settings.required_channel_link

    if REQUIRED_CHANNEL_USERNAME:
        return f"https://t.me/{REQUIRED_CHANNEL_USERNAME.lstrip('@')}"

    return None


def get_subscription_keyboard(
    callback_data: str = "sub_check:start",
) -> InlineKeyboardMarkup:
    """Единая клавиатура для приглашения подписаться."""

    buttons: list[list[InlineKeyboardButton]] = []
    channel_link = _get_channel_link()

    if channel_link:
        buttons.append(
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_link)]
        )

    buttons.append(
        [InlineKeyboardButton(text="✅ Я подписался", callback_data=callback_data)]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
    """Проверка статуса участника канала."""

    if REQUIRED_CHANNEL_USERNAME is None and REQUIRED_CHANNEL_ID is None:
        return True

    chat_id = _get_channel_identifier()

    if chat_id is None:
        return True

    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Не удалось проверить подписку пользователя", exc_info=exc)
        return False

    status = getattr(member, "status", None)
    return status in {"member", "creator", "administrator", "owner"}


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

    if is_admin:
        return True

    user_id = message_or_callback.from_user.id

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
