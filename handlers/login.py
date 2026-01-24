import logging
import os
import re

import aiohttp
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import get_settings
from utils.telegram import answer_with_thread
from services.subscription import ensure_subscribed

router = Router()
logger = logging.getLogger(__name__)


class LoginState(StatesGroup):
    waiting_for_phone = State()


API_BASE_URL = os.getenv("API_URL") or os.getenv("BASE_URL", "http://localhost:8000")
API_BASE_URL = (API_BASE_URL or "http://localhost:8000").rstrip("/")
if API_BASE_URL.endswith("/api"):
    API_BASE_URL = API_BASE_URL[: -len("/api")]

CREATE_CODE_ENDPOINT = f"{API_BASE_URL}/api/bot/auth/create-code"

PHONE_CLEANUP_RE = re.compile(r"[\s\-()]+")


def _normalize_phone(raw_phone: str) -> str:
    cleaned = PHONE_CLEANUP_RE.sub("", (raw_phone or "").strip())
    digits_only = re.sub(r"\D", "", cleaned)

    if cleaned.startswith("8") and len(digits_only) == 11 and digits_only.startswith("8"):
        return f"+7{digits_only[1:]}"

    return cleaned


def _format_minutes(expires_in_seconds: int | None) -> int:
    if not expires_in_seconds:
        return 5
    minutes = max(1, round(expires_in_seconds / 60))
    return minutes


async def _request_login_code(payload: dict) -> tuple[int, dict | None]:
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(CREATE_CODE_ENDPOINT, json=payload) as response:
                data = await response.json(content_type=None)
                return response.status, data if isinstance(data, dict) else None
    except aiohttp.ClientError:
        logger.exception("Failed to call bot auth create-code API")
        return 0, None
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error during bot auth create-code API call")
        return 0, None


@router.message(Command("login"))
async def login_entry(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    is_admin = user_id in get_settings().admin_ids

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await state.clear()
    await state.set_state(LoginState.waiting_for_phone)
    await answer_with_thread(message, "Введите номер телефона в формате +7...")


@router.message(LoginState.waiting_for_phone)
async def login_receive_phone(message: types.Message, state: FSMContext) -> None:
    raw_phone = ""
    if message.contact and message.contact.phone_number:
        raw_phone = message.contact.phone_number
    else:
        raw_phone = (message.text or "").strip()

    if not raw_phone:
        await answer_with_thread(message, "Не вижу номер телефона. Отправьте его текстом или контактом.")
        return

    phone = _normalize_phone(raw_phone)
    telegram_user = message.from_user
    payload = {
        "phone": phone,
        "telegram_id": telegram_user.id if telegram_user else None,
        "telegram_username": telegram_user.username if telegram_user else None,
    }

    status, response = await _request_login_code(payload)
    await state.clear()

    if status == 200 and response:
        code = response.get("code")
        expires_in_seconds = response.get("expires_in_seconds")

        if code:
            minutes = _format_minutes(expires_in_seconds)
            await answer_with_thread(message,
                f"Код для входа: {code}. Действует {minutes} минут."
            )
            return

        logger.error("Create-code API returned 200 without code: %s", response)

    if status == 404:
        logger.error("Create-code endpoint not found: %s", CREATE_CODE_ENDPOINT)
        await answer_with_thread(message,
            "Не удалось получить код, попробуйте позже. "
            "Похоже, endpoint /api/bot/auth/create-code ещё не подключён — сообщите администратору."
        )
        return

    if status == 0:
        logger.error("Create-code API is unavailable")
    elif status >= 400:
        logger.error("Create-code API error status=%s response=%s", status, response)
    else:
        logger.error("Create-code API unexpected response status=%s response=%s", status, response)

    await answer_with_thread(message, "Не удалось получить код, попробуйте позже")
