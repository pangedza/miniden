from aiogram import Router, types, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.products import get_baskets, get_basket_by_id
from services.cart import add_to_cart
from keyboards.catalog_keyboards import catalog_product_actions_kb
from config import get_settings
from utils.texts import format_basket_card

router = Router()

# Сколько товаров показываем на одной странице каталога для пользователя
USER_BASKETS_PER_PAGE = 5


async def _send_baskets_page(
    message: types.Message, page: int = 1, with_banner: bool = False
) -> None:
    """
    Показать одну страницу корзинок пользователю.
    """
    if with_banner:
        banner = get_settings().banner_baskets
        if banner:
            await message.answer_photo(photo=banner, caption="🧺 Наши корзинки")

    baskets = get_baskets()
    if not baskets:
        await message.answer("Список корзинок пока пуст. Попробуйте позже 🙈")
        return

    total = len(baskets)
    if page < 1:
        page = 1

    max_page = (total + USER_BASKETS_PER_PAGE - 1) // USER_BASKETS_PER_PAGE
    if page > max_page:
        page = max_page

    start = (page - 1) * USER_BASKETS_PER_PAGE
    end = start + USER_BASKETS_PER_PAGE
    page_items = baskets[start:end]

    # Заголовок страницы
    await message.answer(f"🧺 Корзинки\nСтраница {page}/{max_page}\n")

    # Карточки товаров
    for item in page_items:
        item_id = item["id"]
        photo = item.get("image_file_id")
        url = item.get("detail_url")

        card_text = format_basket_card(item)

        if photo:
            await message.answer_photo(
                photo=photo,
                caption=card_text,
                reply_markup=catalog_product_actions_kb("basket", item_id, url),
            )
        else:
            await message.answer(
                card_text,
                reply_markup=catalog_product_actions_kb("basket", item_id, url),
            )

    # Навигация по страницам
    buttons = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅ Назад",
                callback_data=f"baskets:page:{page - 1}",
            )
        )
    if page < max_page:
        buttons.append(
            InlineKeyboardButton(
                text="Вперёд ➡",
                callback_data=f"baskets:page:{page + 1}",
            )
        )

    if buttons:
        nav_kb = InlineKeyboardMarkup(inline_keyboard=[buttons])
        await message.answer("Листайте страницы каталога:", reply_markup=nav_kb)


@router.message(F.text == "🧺 Корзинки")
async def show_baskets(message: types.Message) -> None:
    """Показать список корзинок с пагинацией."""
    await _send_baskets_page(message, page=1, with_banner=True)


@router.callback_query(F.data.startswith("baskets:page:"))
async def baskets_page_callback(callback: CallbackQuery) -> None:
    """Перелистывание страниц каталога корзинок."""
    data = callback.data or ""
    try:
        _, _, raw_page = data.split(":")
        page = int(raw_page)
    except Exception:
        await callback.answer("Некорректный номер страницы", show_alert=True)
        return

    # Удаляем старое сообщение с навигацией,
    # чтобы не плодить много "Листайте страницы каталога:"
    try:
        await callback.message.delete()
    except Exception:
        pass

    await _send_baskets_page(callback.message, page=page)
    await callback.answer()


# ------------------- Добавление корзинки в корзину -------------------


@router.callback_query(F.data.startswith("cart:add:basket:"))
async def add_basket_to_cart(callback: CallbackQuery) -> None:
    """Добавить корзинку в корзину пользователя."""
    data = callback.data or ""
    # ожидаем формат: cart:add:basket:<id>
    try:
        _, action, product_type, raw_id = data.split(":")
        item_id = int(raw_id)
    except Exception:
        await callback.answer("Не удалось понять товар 🤔", show_alert=True)
        return

    item = get_basket_by_id(item_id)
    if not item:
        await callback.answer("Товар не найден 😢", show_alert=True)
        return

    user_id = callback.from_user.id
    name = item.get("name", "Корзинка")
    price = int(item.get("price", 0))

    add_to_cart(
        user_id=user_id,
        product_id=str(item_id),
        name=name,
        price=price,
        qty=1,
    )

    await callback.answer("Добавлено в корзину 🛒")
