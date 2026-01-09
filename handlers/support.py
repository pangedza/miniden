from __future__ import annotations

from typing import Dict

from aiogram import F, Router, types

from config import ADMIN_IDS, ADMIN_IDS_SET
from config import get_settings

support_router = Router()

USER_LAST_QUESTION: Dict[int, str] = {}
ADMIN_REPLY_TARGETS: Dict[int, int] = {}


def remember_user_question(user_id: int, question: str) -> None:
    if question:
        USER_LAST_QUESTION[user_id] = question


@support_router.callback_query(F.data.in_({"contact_manager", "trigger:contact_manager"}))
async def contact_manager(callback: types.CallbackQuery):
    user = callback.from_user
    settings = get_settings()
    question = USER_LAST_QUESTION.get(user.id) or "—"
    await callback.message.answer("Я передал ваш вопрос менеджеру, скоро он ответит.")

    admin_message = (
        "Новый запрос от пользователя: "
        f"{user.username or user.full_name or user.id}.\n"
        f"Последний вопрос: {question}.\n"
        "Чтобы ответить, просто напишите ответ в реплай на это сообщение."
    )

    admin_chat_ids = ADMIN_IDS or ([] if settings.admin_chat_id is None else [settings.admin_chat_id])
    for chat_id in admin_chat_ids:
        sent = await callback.bot.send_message(chat_id, admin_message)
        ADMIN_REPLY_TARGETS[sent.message_id] = user.id

    await callback.answer()


@support_router.message(F.reply_to_message)
async def relay_admin_reply(message: types.Message):
    if message.from_user.id not in ADMIN_IDS_SET:
        return
    reply_to = message.reply_to_message
    if not reply_to:
        return
    target_user_id = ADMIN_REPLY_TARGETS.get(reply_to.message_id)
    if not target_user_id:
        return

    response_text = message.text or message.caption
    if not response_text:
        return

    await message.bot.send_message(target_user_id, response_text)
