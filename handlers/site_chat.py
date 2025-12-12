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
    def __init__(self, status: int, body: str):
        super().__init__(f"Backend request failed: {status} {body}")
        self.status = status
        self.body = body


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


async def _post_json(url: str, payload: dict, timeout: int = 15) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        ) as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise BackendRequestError(resp.status, body)
            return body


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
        await message.answer("❌ Пустое сообщение.")
        return

    url = f"{API_BASE_URL}/api/webchat/manager_reply"
    logging.info(
        "Sending manager reply via POST to %s, session_id=%s", url, session_id
    )

    try:
        await _post_json(
            url,
            {"session_id": int(session_id), "text": text},
        )
    except BackendRequestError as exc:
        logging.exception("Failed to send manager reply to backend")
        await message.answer(
            f"❌ Ошибка отправки на сайт: {exc.status} {exc.body}"
        )
        return
    except Exception as exc:
        logging.exception("Failed to send manager reply to backend")
        await message.answer(
            f"❌ Не удалось отправить ответ на сайт: неизвестная ошибка ({exc})"
        )
        return

    await message.answer(f"✅ Ответ отправлен на сайт (чат #{session_id})")
