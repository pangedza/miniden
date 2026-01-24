import logging
import os
import re

import aiohttp
from aiogram import F, Router
from aiogram.types import Message

from config import get_settings
from utils.telegram import answer_with_thread
from utils import site_chat_storage

API_BASE_URL = os.getenv("API_URL") or os.getenv("BASE_URL", "http://localhost:8000")
API_BASE_URL = (API_BASE_URL or "http://localhost:8000").rstrip("/")
if API_BASE_URL.endswith("/api"):
    API_BASE_URL = API_BASE_URL[: -len("/api")]

site_chat_router = Router()


def _extract_session_id(text: str) -> int | None:
    if not text:
        return None

    patterns = [r"Новый чат с сайта\s*#(\d+)", r"Новый запрос от пользователя.*?#(\d+)", r"#(\d+)"]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                return int(m.group(1))
            except (TypeError, ValueError):
                continue
    return None


async def _post_manager_reply(
    backend_url: str, session_id: int, text: str, timeout: int = 15
):
    url = f"{backend_url}/api/webchat/manager_reply"
    payload = {"text": text, "session_id": session_id}
    logging.info("MANAGER_REPLY POST %s payload=%s", url, payload)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=timeout) as resp:
            body = await resp.text()
            logging.info(
                "MANAGER_REPLY response status=%s body=%s", resp.status, body
            )
            if resp.status >= 400:
                raise Exception(f"{resp.status} {body}")
            return body


@site_chat_router.message(F.reply_to_message)
async def handle_manager_reply(message: Message):
    settings = get_settings()
    admin_ids = settings.admin_ids or set()
    primary_admin = settings.admin_chat_id
    sender_id = message.from_user.id if message.from_user else None
    if sender_id not in admin_ids and sender_id != primary_admin:
        return

    if not message.reply_to_message:
        return

    reply = message.reply_to_message
    reply_text = reply.text or reply.caption
    session_id = _extract_session_id(reply_text or "")
    if not session_id:
        session_id = site_chat_storage.get_session_id_for_message(
            reply.message_id
        )
    if not session_id:
        await answer_with_thread(message,
            "❌ Не вижу номер чата (#ID). Ответь реплаем на уведомление о запросе."
        )
        return

    logging.info(
        "Site chat: reply detected session_id=%s for message_id=%s", session_id, reply.message_id
    )

    text = message.text or message.caption
    if not text:
        await answer_with_thread(message, "❌ Пустое сообщение.")
        return

    try:
        await _post_manager_reply(API_BASE_URL, session_id, text)
    except Exception as exc:
        logging.exception("Failed to send manager reply to backend")
        await answer_with_thread(message, f"❌ Ошибка отправки на сайт: {exc}")
        return

    await answer_with_thread(message, f"✅ Отправлено на сайт (чат #{session_id})")
