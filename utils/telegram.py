from __future__ import annotations

from typing import Any

from aiogram import types
from aiogram.client.bot import Bot


def _get_message_thread_id(message: types.Message | None) -> int | None:
    if not message:
        return None
    thread_id = getattr(message, "message_thread_id", None)
    return thread_id if thread_id is not None else None


def _should_use_thread(source_message: types.Message | None, chat_id: int | None) -> bool:
    if not source_message or chat_id is None:
        return False
    return bool(source_message.chat and source_message.chat.id == chat_id)


def apply_message_thread_id(
    source_message: types.Message | None,
    chat_id: int | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    if "message_thread_id" in kwargs:
        return kwargs

    if not _should_use_thread(source_message, chat_id):
        return kwargs

    thread_id = _get_message_thread_id(source_message)
    if thread_id is None:
        return kwargs

    return {**kwargs, "message_thread_id": thread_id}


async def answer_with_thread(message: types.Message, text: str, **kwargs: Any):
    patched_kwargs = apply_message_thread_id(
        message,
        message.chat.id if message.chat else None,
        kwargs,
    )
    return await message.answer(text, **patched_kwargs)


async def answer_photo_with_thread(message: types.Message, **kwargs: Any):
    patched_kwargs = apply_message_thread_id(
        message,
        message.chat.id if message.chat else None,
        kwargs,
    )
    return await message.answer_photo(**patched_kwargs)


async def send_message_with_thread(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    source_message: types.Message | None = None,
    **kwargs: Any,
):
    patched_kwargs = apply_message_thread_id(source_message, chat_id, kwargs)
    return await bot.send_message(chat_id, text, **patched_kwargs)
