from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import get_settings
from services.cart import (
    get_cart_items,
    get_cart_total,
    clear_cart,
)
from services.orders import add_order
from utils.texts import format_cart, format_order_for_admin

router = Router()


class CheckoutState(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_comment = State()


@router.message(Command(commands=["checkout", "order"]))
async def start_checkout(message: types.Message, state: FSMContext) -> None:
    """Старт оформления заказа."""
    user_id = message.from_user.id
    items = get_cart_items(user_id)   # NEW

    if not items:
        await message.answer("🛒 Ваша корзина пуста. Сначала добавьте товары.")
        return

    cart_text = format_cart(items)

    await message.answer(
        cart_text
        + "\n\nДавайте оформим заказ. Как вас зовут? 🙂"
    )

    await state.set_state(CheckoutState.waiting_for_name)


@router.message(CheckoutState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(customer_name=message.text.strip())
    await message.answer(
        "Спасибо! Как с вами лучше связаться? Напишите телефон, @username или другой контакт."
    )
    await state.set_state(CheckoutState.waiting_for_contact)


@router.message(CheckoutState.waiting_for_contact)
async def process_contact(message: types.Message, state: FSMContext) -> None:
    await state.update_data(contact=message.text.strip())
    await message.answer(
        "Если хотите, можете оставить комментарий к заказу "
        "(или напишите «-», если без комментария)."
    )
    await state.set_state(CheckoutState.waiting_for_comment)


@router.message(CheckoutState.waiting_for_comment)
async def process_comment(message: types.Message, state: FSMContext) -> None:
    comment_raw = message.text.strip()
    comment = "" if comment_raw == "-" else comment_raw

    user = message.from_user
    user_id = user.id
    user_name = user.full_name or ""

    items = get_cart_items(user_id)   # NEW

    if not items:
        await message.answer(
            "Похоже, корзина опустела. Попробуйте оформить заказ заново."
        )
        await state.clear()
        return

    total = get_cart_total(user_id)   # NEW
    data = await state.get_data()

    customer_name = data.get("customer_name", "")
    contact = data.get("contact", "")

    # Формируем текст заказа (без номера)
    base_order_text = format_order_for_admin(
        user_id=user_id,
        user_name=user_name,
        items=items,
        total=total,
        customer_name=customer_name,
        contact=contact,
        comment=comment,
    )

    # Сохраняем заказ в БД
    order_id = add_order(
        user_id=user_id,
        user_name=user_name,
        items=items,
        total=total,
        customer_name=customer_name,
        contact=contact,
        comment=comment,
        order_text=base_order_text,
    )

    # Добавляем номер заказа
    full_order_text = f"🧾 Заказ №{order_id}\n\n{base_order_text}"

    settings = get_settings()
    admin_chat_id = settings.admin_chat_id

    if admin_chat_id:
        await message.bot.send_message(
            chat_id=admin_chat_id,
            text=full_order_text,
        )

    await message.answer(
        "Ваш заказ отправлен 🧶\n"
        "Мы свяжемся с вами для подтверждения. Спасибо! ❤️"
    )

    # Очищаем корзину после оформления заказа
    clear_cart(user_id)    # NEW
    await state.clear()
