import logging
import os
import re

import aiohttp
from aiogram import F, Router
from aiogram.types import Message

from config import get_settings

API_BASE_URL = os.getenv("API_URL") or os.getenv("BASE_URL", "http://localhost:8000")
API_BASE_URL = (API_BASE_URL or "http://localhost:8000").rstrip("/")
if API_BASE_URL.endswith("/api"):
    API_BASE_URL = API_BASE_URL[: -len("/api")]

site_chat_router = Router()


class BackendRequestError(Exception):
    def __init__(self, status: int, text: str):
        super().__init__(f"{status} {text}")
        self.status = status
        self.text = text


def _extract_session_id(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"Новый чат с сайта\s*#(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


async def _send_manager_reply(session_id: int, text: str):
    url = f"{API_BASE_URL}/api/webchat/manager_reply"
    payload = {"session_id": session_id, "text": text}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            response_text = await response.text()
            if response.status >= 400:
                raise BackendRequestError(response.status, response_text)


@site_chat_router.message(F.reply_to_message)
async def handle_manager_reply(message: Message):
    settings = get_settings()
    admin_ids = settings.admin_ids or set()
    primary_admin = settings.admin_chat_id
    sender_id = message.from_user.id if message.from_user else None
    if sender_id not in admin_ids and sender_id != primary_admin:
        return

    reply = message.reply_to_message
    reply_text = (reply.text or reply.caption) if reply else None
    session_id = _extract_session_id(reply_text)
    if not session_id:
        return

    text = message.text or message.caption
    if not text:
        return

    try:
        await _send_manager_reply(session_id, text)
    except BackendRequestError as exc:
        logging.exception("Failed to send manager reply to backend")
        await message.answer(
            f"❌ Не удалось отправить ответ на сайт: {exc.status} {exc.text}"
        )
        return
    except Exception as exc:
        logging.exception("Failed to send manager reply to backend")
        await message.answer(
            f"❌ Не удалось отправить ответ на сайт: неизвестная ошибка ({exc})"
        )
        return

    await message.answer(f"✅ Ответ отправлен на сайт (чат #{session_id}).")
