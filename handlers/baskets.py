from aiogram import Router, types, F
from aiogram.types import CallbackQuery

from services.products import get_baskets, get_basket_by_id, get_product_by_id
from services import orders as orders_service
from services.cart import add_to_cart
from services.favorites import add_favorite, is_favorite, remove_favorite
from keyboards.catalog_keyboards import build_pagination_kb, build_product_card_kb
from config import ADMIN_IDS, get_settings
from services.subscription import ensure_subscribed
from utils.texts import format_basket_card

router = Router()

# Сколько товаров показываем на одной странице каталога для пользователя
USER_BASKETS_PER_PAGE = 5


async def _send_baskets_page(
    message: types.Message, user_id: int, page: int = 1, with_banner: bool = False
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

    # Карточки товаров
    for item in page_items:
        item_id = item["id"]
        photo = item.get("image_file_id")

        is_fav = is_favorite(user_id, item_id)

        card_text = format_basket_card(item)
        keyboard = build_product_card_kb(
            product=item, has_access=False, is_favorite=is_fav
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
            section="baskets", page=page, has_prev=has_prev, has_next=has_next
        )
        await message.answer(
            f"🧺 Корзинки — страница {page}/{max_page}",
            reply_markup=pagination_kb,
        )


@router.message(F.text == "🧺 Корзинки")
async def show_baskets(message: types.Message) -> None:
    """Показать список корзинок с пагинацией."""
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    await _send_baskets_page(message, user_id=user_id, page=1, with_banner=True)


@router.callback_query(F.data.startswith("catalog:"))
async def baskets_page_callback(callback: CallbackQuery) -> None:
    """Перелистывание страниц каталога корзинок."""
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    data = callback.data or ""
    try:
        parts = data.split(":")
        if len(parts) < 4:
            raise ValueError
        _, _action, section, raw_page = parts[:4]
        if section != "baskets":
            return
        page = int(raw_page)
    except Exception:
        await callback.answer("Некорректный номер страницы", show_alert=True)
        return

    try:
        await callback.message.delete()
    except Exception:
        pass

    await _send_baskets_page(callback.message, user_id=user_id, page=page)
    await callback.answer()


# ------------------- Добавление корзинки в корзину -------------------


@router.callback_query(F.data.startswith("cart:add:basket:"))
async def add_basket_to_cart(callback: CallbackQuery) -> None:
    """Добавить корзинку в корзину пользователя."""
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

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


@router.callback_query(F.data.startswith("fav:add:"))
async def add_to_favorites(callback: CallbackQuery) -> None:
    """Добавить товар или курс в избранное."""

    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    data = callback.data or ""
    try:
        _, _, raw_id = data.split(":")
        product_id = int(raw_id)
    except Exception:
        await callback.answer("Не удалось понять товар 🤔", show_alert=True)
        return

    product = get_product_by_id(product_id)
    if product is None:
        await callback.answer("Товар не найден 😢", show_alert=True)
        return

    add_favorite(user_id, product_id)

    await callback.answer("Добавлено в избранное ❤️")

    try:
        access_ids = {
            c["id"] for c in orders_service.get_user_courses_with_access(user_id)
        }
        has_access = product.get("type") == "course" and product_id in access_ids
        await callback.message.edit_reply_markup(
            reply_markup=build_product_card_kb(
                product=product, has_access=has_access, is_favorite=True
            )
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("fav:remove:"))
async def remove_from_favorites(callback: CallbackQuery) -> None:
    """Убрать товар или курс из избранного."""

    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    data = callback.data or ""
    try:
        _, _, raw_id = data.split(":")
        product_id = int(raw_id)
    except Exception:
        await callback.answer("Не удалось понять товар 🤔", show_alert=True)
        return

    product = get_product_by_id(product_id)
    if product is None:
        await callback.answer("Товар не найден 😢", show_alert=True)
        return

    remove_favorite(user_id, product_id)

    await callback.answer("Удалено из избранного 💔")

    try:
        access_ids = {
            c["id"] for c in orders_service.get_user_courses_with_access(user_id)
        }
        has_access = product.get("type") == "course" and product_id in access_ids
        await callback.message.edit_reply_markup(
            reply_markup=build_product_card_kb(
                product=product, has_access=has_access, is_favorite=False
            )
        )
    except Exception:
        pass
