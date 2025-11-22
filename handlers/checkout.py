from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import get_settings
from services.cart import (
    get_cart_items,
    get_cart_total,
    clear_cart,
)
from services.promocodes import (
    calculate_discount_amount,
    get_promocode_by_code,
    increment_promocode_usage,
    normalize_code,
    validate_promocode_for_order,
)
from services.user_admin import get_user_ban_status
from services.orders import add_order
from services.subscription import ensure_subscribed
from utils.texts import format_cart, format_order_for_admin, format_price

router = Router()


def _promo_skip_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Пропустить", callback_data="checkout:promo_skip")]
        ]
    )


class CheckoutState(StatesGroup):
    waiting_for_promocode = State()
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_comment = State()


PROMO_PROMPT = (
    "Если у вас есть промокод — отправьте его одним сообщением.\n"
    "Если промокода нет, нажмите кнопку «Пропустить»."
)


async def _ask_for_name(message: types.Message, state: FSMContext) -> None:
    await message.answer(
        "Давайте оформим заказ. Как вас зовут? 🙂",
    )
    await state.set_state(CheckoutState.waiting_for_name)


async def start_checkout_flow(
    target_message: types.Message, state: FSMContext, user_id: int
) -> None:
    """Общий старт оформления заказа с шагом ввода промокода для user_id."""

    items, removed = get_cart_items(user_id)
    print(f"[DEBUG] checkout items={len(items)} user={user_id}")

    notice_text = None
    if removed:
        notice_text = "Некоторые товары больше недоступны и были удалены из вашей корзины."

    if not items:
        empty_text = "🛒 Ваша корзина пуста. Сначала добавьте товары."
        if notice_text:
            empty_text = f"{notice_text}\n\n{empty_text}"
        await target_message.answer(empty_text)
        await state.clear()
        return

    order_total = get_cart_total(user_id)
    await state.update_data(
        order_total=order_total,
        promo_code=None,
        discount_amount=0,
        final_total=order_total,
    )
    await state.set_state(CheckoutState.waiting_for_promocode)

    cart_text = format_cart(items)
    if notice_text:
        cart_text = f"{notice_text}\n\n{cart_text}"

    await target_message.answer(
        f"{cart_text}\n\n{PROMO_PROMPT}",
        reply_markup=_promo_skip_kb(),
    )


@router.message(Command(commands=["checkout", "order"]))
async def start_checkout(message: types.Message, state: FSMContext) -> None:
    """Старт оформления заказа."""
    user_id = message.from_user.id
    is_admin = user_id in get_settings().admin_ids

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await start_checkout_flow(message, state, user_id)


@router.callback_query(F.data == "checkout:promo_skip")
async def promo_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        data = await state.get_data()
        order_total = int(data.get("order_total", 0) or get_cart_total(callback.from_user.id))
        await state.update_data(
            promo_code=None,
            discount_amount=0,
            final_total=order_total,
        )
        await callback.answer()
        await callback.message.answer("Хорошо, продолжаем без промокода...")
        await _ask_for_name(callback.message, state)


@router.message(CheckoutState.waiting_for_promocode)
async def process_promocode(message: types.Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    items, removed = get_cart_items(user_id)
    if not items:
        await message.answer("Похоже, корзина пуста. Попробуйте оформить заказ заново.")
        await state.clear()
        return

    if removed:
        await message.answer(
            "Некоторые товары больше недоступны и были удалены из вашей корзины."
        )

    order_total = get_cart_total(user_id)
    raw_code = normalize_code(message.text or "")

    promo = get_promocode_by_code(raw_code)
    if not promo:
        await message.answer(
            "Промокод не найден. Попробуйте ещё раз или нажмите «Пропустить».",
            reply_markup=_promo_skip_kb(),
        )
        return

    is_valid, reason = validate_promocode_for_order(promo, order_total)
    if not is_valid:
        await message.answer(
            (reason or "Промокод не подходит.")
            + " Попробуйте ещё раз или нажмите «Пропустить».",
            reply_markup=_promo_skip_kb(),
        )
        return

    discount_amount = calculate_discount_amount(promo, order_total)
    final_total = order_total - discount_amount
    if final_total < 0:
        final_total = 0

    await state.update_data(
        promo_code=promo.get("code"),
        discount_amount=discount_amount,
        final_total=final_total,
        order_total=order_total,
    )

    await message.answer(
        "Промокод применён ✅\n"
        f"Сумма без скидки: {format_price(order_total)}\n"
        f"Скидка: -{format_price(discount_amount)}\n"
        f"Итого к оплате: {format_price(final_total)}\n\n"
        "Как вас зовут? 🙂",
    )
    await state.set_state(CheckoutState.waiting_for_name)


@router.message(CheckoutState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(customer_name=(message.text or "").strip())
    await message.answer(
        "Спасибо! Как с вами лучше связаться? Напишите телефон, @username или другой контакт."
    )
    await state.set_state(CheckoutState.waiting_for_contact)


@router.message(CheckoutState.waiting_for_contact)
async def process_contact(message: types.Message, state: FSMContext) -> None:
    await state.update_data(contact=(message.text or "").strip())
    await message.answer(
        "Если хотите, можете оставить комментарий к заказу "
        "(или напишите «-», если без комментария)."
    )
    await state.set_state(CheckoutState.waiting_for_comment)


@router.message(CheckoutState.waiting_for_comment)
async def process_comment(message: types.Message, state: FSMContext) -> None:
    comment_raw = (message.text or "").strip()
    comment = "" if comment_raw == "-" else comment_raw

    user = message.from_user
    user_id = user.id
    user_name = user.full_name or ""

    items, removed = get_cart_items(user_id)

    if not items:
        await message.answer(
            "Похоже, корзина опустела. Попробуйте оформить заказ заново."
        )
        await state.clear()
        return

    if removed:
        await message.answer(
            "Некоторые товары больше недоступны и были удалены из вашей корзины."
        )

    order_total = get_cart_total(user_id)
    data = await state.get_data()

    customer_name = data.get("customer_name", "")
    contact = data.get("contact", "")
    promo_code = data.get("promo_code")
    discount_amount = int(data.get("discount_amount", 0) or 0)
    final_total = int(data.get("final_total", order_total) or order_total)

    ban_status = get_user_ban_status(user_id)
    if ban_status.get("is_banned"):
        await message.answer(
            "К сожалению, ваш аккаунт заблокирован. По вопросам обращайтесь к администратору."
        )
        clear_cart(user_id)
        await state.clear()
        return

    recalculated_total = order_total
    if promo_code:
        promo = get_promocode_by_code(promo_code)
        if promo:
            is_valid, reason = validate_promocode_for_order(promo, order_total)
            if is_valid:
                discount_amount = calculate_discount_amount(promo, order_total)
                recalculated_total = order_total - discount_amount
                if recalculated_total < 0:
                    recalculated_total = 0
            else:
                await message.answer(
                    f"Промокод больше не действует: {reason}. Заказ оформлен без скидки."
                )
                promo_code = None
                discount_amount = 0
        else:
            promo_code = None
            discount_amount = 0

    if promo_code:
        final_total = recalculated_total
    else:
        final_total = order_total

    # Формируем текст заказа (без номера)
    base_order_text = format_order_for_admin(
        user_id=user_id,
        user_name=user_name,
        items=items,
        total=final_total,
        customer_name=customer_name,
        contact=contact,
        comment=comment,
        discount_amount=discount_amount,
        original_total=order_total,
    )

    # Сохраняем заказ в БД
    order_id = add_order(
        user_id=user_id,
        user_name=user_name,
        items=items,
        total=final_total,
        customer_name=customer_name,
        contact=contact,
        comment=comment,
        order_text=base_order_text,
        promocode_code=promo_code,
        discount_amount=discount_amount,
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

    if promo_code:
        increment_promocode_usage(promo_code)

    # Очищаем корзину после оформления заказа
    clear_cart(user_id)
    await state.clear()
