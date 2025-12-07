import os
from urllib.parse import quote_plus, unquote_plus

import aiohttp
from aiogram import F, Router, types

from handlers.support import remember_user_question

API_BASE_URL = os.getenv("API_URL") or (os.getenv("BASE_URL", "http://localhost:8000").rstrip("/") + "/api")

faq_router = Router()


async def _get_json(path: str, params: dict | None = None):
    url = f"{API_BASE_URL}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status == 404:
                return None
            response.raise_for_status()
            return await response.json()


def _build_category_callback(category: str) -> str:
    return f"faq:cat:{quote_plus(category)}"


def _parse_category_callback(data: str) -> str | None:
    try:
        return unquote_plus(data.split("faq:cat:", 1)[1])
    except Exception:
        return None


def _build_question_callback(question_id: int) -> str:
    return f"faq:q:{question_id}"


def _parse_question_callback(data: str) -> int | None:
    try:
        return int(data.split("faq:q:", 1)[1])
    except Exception:
        return None


def _truncate(text: str, limit: int = 60) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit - 1]}…"


@faq_router.message(F.text == "❓ Вопросы и ответы")
async def show_faq_categories(message: types.Message):
    data = await _get_json("/faq") or []
    if not data:
        await message.answer("База знаний пока пуста.")
        return

    categories = []
    for item in data:
        category = item.get("category")
        if category and category not in categories:
            categories.append(category)

    if not categories:
        await message.answer("Категории не найдены.")
        return

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=category, callback_data=_build_category_callback(category))]
            for category in categories
        ]
    )
    await message.answer("Выберите раздел", reply_markup=keyboard)


@faq_router.callback_query(F.data.startswith("faq:cat:"))
async def load_category(callback: types.CallbackQuery):
    category = _parse_category_callback(callback.data)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    data = await _get_json("/faq", params={"category": category}) or []
    if not data:
        await callback.message.edit_text("В этой категории пока нет вопросов.")
        await callback.answer()
        return

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=_truncate(item.get("question") or "", 60),
                    callback_data=_build_question_callback(int(item.get("id"))),
                )
            ]
            for item in data
        ]
    )
    await callback.message.edit_text(f"Раздел: {category}\nВыберите вопрос:", reply_markup=keyboard)
    await callback.answer()


@faq_router.callback_query(F.data.startswith("faq:q:"))
async def load_question(callback: types.CallbackQuery):
    question_id = _parse_question_callback(callback.data)
    if not question_id:
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    item = await _get_json(f"/faq/{question_id}")
    if not item:
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    question = item.get("question") or "Вопрос"
    answer = item.get("answer") or "Ответ"
    remember_user_question(callback.from_user.id, question)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Связаться с менеджером", callback_data="contact_manager"
                )
            ]
        ]
    )
    await callback.message.answer(f"<b>{question}</b>\n\n{answer}", reply_markup=keyboard)
    await callback.answer()
