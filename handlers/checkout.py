from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import get_settings
from services.subscription import ensure_subscribed

router = Router()


class CheckoutState(StatesGroup):
    waiting_for_promocode = State()
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_comment = State()


WEBAPP_CHECKOUT_MESSAGE = (
    "Оформление заказа теперь происходит в WebApp.\n"
    "Проверьте корзину и оформите заказ на сайте через кнопки WebApp в главном меню."
)


async def _answer_checkout_redirect(target_message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await target_message.answer(WEBAPP_CHECKOUT_MESSAGE)


@router.message(Command(commands=["checkout", "order"]))
async def start_checkout(message: types.Message, state: FSMContext) -> None:
    """Перенаправление оформления заказа в WebApp."""
    user_id = message.from_user.id
    is_admin = user_id in get_settings().admin_ids

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await _answer_checkout_redirect(message, state)


@router.callback_query(F.data == "checkout:promo_skip")
async def promo_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    is_admin = user_id in get_settings().admin_ids

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    await _answer_checkout_redirect(callback.message, state)
    await callback.answer()


@router.message(CheckoutState.waiting_for_promocode)
async def process_promocode(message: types.Message, state: FSMContext) -> None:
    await _answer_checkout_redirect(message, state)


@router.message(CheckoutState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext) -> None:
    await _answer_checkout_redirect(message, state)


@router.message(CheckoutState.waiting_for_contact)
async def process_contact(message: types.Message, state: FSMContext) -> None:
    await _answer_checkout_redirect(message, state)


@router.message(CheckoutState.waiting_for_comment)
async def process_comment(message: types.Message, state: FSMContext) -> None:
    await _answer_checkout_redirect(message, state)
