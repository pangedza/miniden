import os
import re
import logging

import aiohttp
from aiogram import F, Router
from aiogram.types import Message

from config import get_settings

API_BASE_URL = os.getenv("API_URL") or (
    os.getenv("BASE_URL", "http://localhost:8000").rstrip("/") + "/api"
)

router = Router()


async def _post_json(path: str, payload: dict) -> dict:
    url = f"{API_BASE_URL}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            response.raise_for_status()
            return await response.json()


def _extract_session_id(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"#(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


@router.message(F.reply_to_message)
async def handle_manager_reply(message: Message):
    settings = get_settings()
    admin_ids = settings.admin_ids or set()
    primary_admin = settings.admin_chat_id
    if message.from_user.id not in admin_ids and message.from_user.id != primary_admin:
        return

    reply = message.reply_to_message
    session_id = _extract_session_id(reply.text if reply else None)
    if not session_id:
        return

    text = message.text or message.caption
    if not text:
        return

    try:
        await _post_json(
            "/webchat/manager_reply", {"session_id": session_id, "text": text}
        )
    except Exception:
        logging.exception("Failed to send manager reply to backend")
        await message.answer("Не удалось отправить сообщение в чат. Попробуйте позже.")
        return

    await message.answer("Сообщение отправлено в веб-чат.")
