import logging
import os

import aiohttp
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import get_settings
from utils.telegram import answer_with_thread
from services import cart as cart_service
from services.subscription import ensure_subscribed

router = Router()


class CheckoutState(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_comment = State()


API_BASE_URL = os.getenv("API_URL") or os.getenv("BASE_URL", "http://localhost:8000")
API_BASE_URL = (API_BASE_URL or "http://localhost:8000").rstrip("/")
if API_BASE_URL.endswith("/api"):
    API_BASE_URL = API_BASE_URL[: -len("/api")]

CHECKOUT_ENDPOINT = f"{API_BASE_URL}/api/checkout"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned == "-":
        return None
    return cleaned


async def _post_checkout(payload: dict) -> tuple[int, dict | None]:
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(CHECKOUT_ENDPOINT, json=payload) as response:
                data = await response.json(content_type=None)
                return response.status, data
    except aiohttp.ClientError:
        logging.exception("Failed to call checkout API")
        return 0, None
    except Exception:  # noqa: BLE001
        logging.exception("Unexpected error during checkout API call")
        return 0, None


async def start_checkout_flow(target_message: types.Message, state: FSMContext) -> None:
    items, _ = cart_service.get_cart_items(target_message.from_user.id)
    if not items:
        await answer_with_thread(target_message, "Корзина пуста. Добавьте товары из каталога.")
        return

    await state.clear()
    await state.set_state(CheckoutState.waiting_for_name)
    await answer_with_thread(target_message, "Введите ваше имя для заказа:")


@router.message(Command(commands=["checkout", "order"]))
async def start_checkout(message: types.Message, state: FSMContext) -> None:
    """Запуск оформления заказа в боте."""
    user_id = message.from_user.id
    is_admin = user_id in get_settings().admin_ids

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await start_checkout_flow(message, state)


@router.message(CheckoutState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await answer_with_thread(message, "Имя не должно быть пустым. Попробуйте снова.")
        return

    await state.update_data(customer_name=name)
    await state.set_state(CheckoutState.waiting_for_contact)
    await answer_with_thread(message, "Введите контакт для связи (телефон, Telegram или email):")


@router.message(CheckoutState.waiting_for_contact)
async def process_contact(message: types.Message, state: FSMContext) -> None:
    contact = message.text.strip()
    if not contact:
        await answer_with_thread(message, "Контакт не должен быть пустым. Попробуйте снова.")
        return

    await state.update_data(contact=contact)
    await state.set_state(CheckoutState.waiting_for_comment)
    await answer_with_thread(message,
        "Добавьте комментарий к заказу (или отправьте '-' если комментарий не нужен):"
    )


@router.message(CheckoutState.waiting_for_comment)
async def process_comment(message: types.Message, state: FSMContext) -> None:
    comment = _normalize_optional_text(message.text)
    data = await state.get_data()
    customer_name = data.get("customer_name")
    contact = data.get("contact")

    payload = {
        "user_id": message.from_user.id,
        "user_name": message.from_user.username,
        "customer_name": customer_name,
        "contact": contact,
        "comment": comment,
    }

    status, response = await _post_checkout(payload)
    await state.clear()

    if status == 200 and response:
        order_id = response.get("order_id")
        total = response.get("total")
        await answer_with_thread(message, f"✅ Заказ создан! Номер: {order_id}. Сумма: {total} ₽.")
        return

    if status == 401:
        await answer_with_thread(message, "Не удалось оформить заказ: требуется авторизация.")
        return

    detail = None
    if isinstance(response, dict):
        detail = response.get("detail")

    await answer_with_thread(message,
        f"Не удалось оформить заказ. {detail or 'Попробуйте позже.'}"
    )


@router.message(Command("cancel"))
async def cancel_checkout(message: types.Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await answer_with_thread(message, "Активное оформление заказа не найдено.")
        return
    await state.clear()
    await answer_with_thread(message, "Оформление заказа отменено.")
