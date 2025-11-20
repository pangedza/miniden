from aiogram import Router, types, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from services.products import get_courses, get_course_by_id
from services.cart import add_to_cart
from keyboards.catalog_keyboards import catalog_product_actions_kb

router = Router()

# сколько курсов показываем на одной странице
USER_COURSES_PER_PAGE = 5


def _split_courses_by_payment_type() -> tuple[list[dict], list[dict]]:
    """
    Делим список курсов на бесплатные и платные.
    Бесплатный курс — цена <= 0.
    """
    all_courses = get_courses()
    free: list[dict] = []
    paid: list[dict] = []

    for c in all_courses:
        price = int(c.get("price", 0) or 0)
        if price <= 0:
            free.append(c)
        else:
            paid.append(c)

    return free, paid


def _get_courses_for_type(payment_type: str) -> list[dict]:
    free, paid = _split_courses_by_payment_type()
    if payment_type == "free":
        return free
    if payment_type == "paid":
        return paid
    return free + paid


async def _send_courses_page(
    message: types.Message,
    payment_type: str,
    page: int = 1,
) -> None:
    """
    Показать одну страницу курсов указанного типа пользователю.

    payment_type:
        - "free"  — только бесплатные
        - "paid"  — только платные
    """
    courses = _get_courses_for_type(payment_type)

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
        "free": "🆓 Бесплатные курсы",
        "paid": "💰 Платные курсы",
    }
    title = title_map.get(payment_type, "🎓 Курсы")

    await message.answer(f"{title}\nСтраница {page}/{max_page}\n")

    for item in page_items:
        item_id = item["id"]
        name = item.get("name", "Курс")
        price = int(item.get("price", 0))
        desc = item.get("description") or ""
        photo = item.get("image_file_id")
        url = item.get("detail_url")

        if price <= 0:
            price_text = "💰 Цена: <b>БЕСПЛАТНО</b>"
        else:
            price_text = f"💰 Цена: <b>{price} ₽</b>"

        caption = f"<b>{name}</b>\n{price_text}"
        if desc:
            caption += f"\n\n{desc}"

        if photo:
            await message.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=catalog_product_actions_kb("course", item_id, url),
            )
        else:
            await message.answer(
                caption,
                reply_markup=catalog_product_actions_kb("course", item_id, url),
            )

    # навигация по страницам
    buttons: list[InlineKeyboardButton] = []

    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅ Назад",
                callback_data=f"courses:list:{payment_type}:{page - 1}",
            )
        )
    if page < max_page:
        buttons.append(
            InlineKeyboardButton(
                text="Вперёд ➡",
                callback_data=f"courses:list:{payment_type}:{page + 1}",
            )
        )

    if buttons:
        kb = InlineKeyboardMarkup(inline_keyboard=[buttons])
        await message.answer("Листайте страницы каталога:", reply_markup=kb)


# ===================== ВХОД В РАЗДЕЛ КУРСОВ =====================


@router.message(F.text == "🎓 Онлайн-курсы")
async def courses_entry(message: types.Message) -> None:
    """
    При нажатии на кнопку в главном меню
    показываем выбор: платные или бесплатные курсы.
    """
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆓 Бесплатные курсы",
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
        "🎓 <b>Онлайн-курсы</b>\n\n"
        "Выберите, какие курсы показать:\n"
        "• 🆓 бесплатные — с нулевой ценой;\n"
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

    await _send_courses_page(callback.message, payment_type=payment_type, page=page)
    await callback.answer()


# ===================== ДОБАВЛЕНИЕ КУРСА В КОРЗИНУ =====================


@router.callback_query(F.data.startswith("cart:add:course:"))
async def add_course_to_cart(callback: CallbackQuery) -> None:
    """Добавить курс в корзину пользователя."""
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
