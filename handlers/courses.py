from aiogram import Router, types, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from services.products import (
    get_courses,
    get_course_by_id,
    get_free_courses,
    get_paid_courses,
)
from services.cart import add_to_cart
from services import orders as orders_service
from services.favorites import is_favorite
from keyboards.catalog_keyboards import build_pagination_kb, build_product_card_kb
from config import ADMIN_IDS, get_settings
from services.subscription import ensure_subscribed
from utils.texts import format_course_card

router = Router()

USER_COURSES_PER_PAGE = 5


async def _send_courses_page(
    message: types.Message,
    user_id: int,
    payment_type: str,
    page: int = 1,
) -> None:
    """
    Показать одну страницу курсов указанного типа пользователю.

    payment_type:
        - "free"  — только бесплатные
        - "paid"  — только платные
    """
    if payment_type == "free":
        courses = get_free_courses()
    elif payment_type == "paid":
        courses = get_paid_courses()
    else:
        courses = get_courses()
    courses_with_access = orders_service.get_user_courses_with_access(user_id)
    access_ids = {c["id"] for c in courses_with_access}

    if not courses:
        text = (
            "Пока здесь пусто 🙈\n\n"
            "Для выбранного типа курсов ничего нет.\n"
            "Попробуйте позже или выберите другой тип."
        )
        await message.answer(text)
        return

    total = len(courses)
    if page < 1:
        page = 1

    max_page = (total + USER_COURSES_PER_PAGE - 1) // USER_COURSES_PER_PAGE
    if page > max_page:
        page = max_page

    start = (page - 1) * USER_COURSES_PER_PAGE
    end = start + USER_COURSES_PER_PAGE
    page_items = courses[start:end]

    title_map = {
        "free": "💸 Бесплатные курсы",
        "paid": "💰 Платные курсы",
    }
    title = title_map.get(payment_type, "🎓 Курсы")

    await message.answer(f"{title}\nСтраница {page}/{max_page}\n")

    for item in page_items:
        item_id = item["id"]
        photo = item.get("image_file_id")
        is_fav = is_favorite(user_id, item_id, "course")

        has_access = item_id in access_ids
        card_text = format_course_card(item, has_access=has_access)
        keyboard = build_product_card_kb(
            product=item, has_access=has_access, is_favorite=is_fav
        )

        if photo:
            await message.answer_photo(
                photo=photo, caption=card_text, reply_markup=keyboard
            )
        else:
            await message.answer(card_text, reply_markup=keyboard)

    has_prev = page > 1
    has_next = page < max_page

    if has_prev or has_next:
        pagination_kb = build_pagination_kb(
            section=f"courses:{payment_type}",
            page=page,
            has_prev=has_prev,
            has_next=has_next,
        )
        await message.answer(
            f"{title} — страница {page}/{max_page}", reply_markup=pagination_kb
        )


# ===================== ВХОД В РАЗДЕЛ КУРСОВ =====================


@router.message(F.text == "🎓 Курсы")
async def courses_entry(message: types.Message) -> None:
    """
    При нажатии на кнопку в главном меню
    показываем выбор: платные или бесплатные курсы.
    """
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    banner = get_settings().banner_courses
    if banner:
        await message.answer_photo(photo=banner, caption="🎓 Наши курсы")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💸 Бесплатные курсы",
                    callback_data="courses:list:free:1",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Платные курсы",
                    callback_data="courses:list:paid:1",
                )
            ],
        ]
    )

    text = (
        "🎓 <b>Курсы MiniDeN</b>\n\n"
        "Выберите, какие курсы показать:\n"
        "• 💸 бесплатные — с нулевой ценой;\n"
        "• 💰 платные — с ценой больше 0.\n\n"
        "Добавляйте нужные курсы в корзину и оформляйте заказ — "
        "после этого менеджер выдаст вам доступ."
    )

    await message.answer(text, reply_markup=kb)


# ===================== СПИСОК КУРСОВ (ПАГИНАЦИЯ) =====================


@router.callback_query(F.data.startswith("courses:list:"))
async def courses_list_callback(callback: CallbackQuery) -> None:
    """
    Формат callback_data:
        courses:list:<payment_type>:<page>

    payment_type: free | paid
    """
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    data = callback.data or ""
    try:
        _, _, payment_type, raw_page = data.split(":")
        page = int(raw_page)
    except Exception:
        await callback.answer("Некорректные данные запроса 😕", show_alert=True)
        return

    try:
        await callback.message.delete()
    except Exception:
        pass

    await _send_courses_page(
        callback.message, user_id=user_id, payment_type=payment_type, page=page
    )
    await callback.answer()


@router.callback_query(F.data.startswith("catalog:"))
async def courses_catalog_callback(callback: CallbackQuery) -> None:
    """Перелистывание страниц каталога курсов."""

    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    data = callback.data or ""
    try:
        parts = data.split(":")
        if len(parts) < 4:
            raise ValueError
        _, _action, section, *tail = parts
        if section != "courses":
            return
        if not tail:
            raise ValueError
        if len(tail) == 1:
            payment_type = "all"
            raw_page = tail[0]
        else:
            payment_type = tail[0]
            raw_page = tail[-1]
        page = int(raw_page)
    except Exception:
        await callback.answer("Некорректные данные запроса 😕", show_alert=True)
        return

    try:
        await callback.message.delete()
    except Exception:
        pass

    await _send_courses_page(
        callback.message, user_id=user_id, payment_type=payment_type, page=page
    )
    await callback.answer()


# ===================== ДОБАВЛЕНИЕ КУРСА В КОРЗИНУ =====================


@router.callback_query(F.data.startswith("cart:add:course:"))
async def add_course_to_cart(callback: CallbackQuery) -> None:
    """Добавить курс в корзину пользователя."""
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    data = callback.data or ""
    # ожидаем формат: cart:add:course:<id>
    try:
        _, _, product_type, raw_id = data.split(":")
        item_id = int(raw_id)
    except Exception:
        await callback.answer("Не удалось понять курс 🤔", show_alert=True)
        return

    item = get_course_by_id(item_id)
    if not item:
        await callback.answer("Курс не найден 😢", show_alert=True)
        return

    user_id = callback.from_user.id
    name = item.get("name", "Курс")
    price = int(item.get("price", 0))

    add_to_cart(
        user_id=user_id,
        product_id=str(item_id),
        name=name,
        price=price,
        qty=1,
    )

    await callback.answer("Курс добавлен в корзину 🛒")
