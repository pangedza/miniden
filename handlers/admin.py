from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from services import products as products_service
from services import orders as orders_service
from keyboards.admin_inline import products_list_kb, admin_product_actions_kb
from keyboards.main_menu import get_main_menu

router = Router()


def _is_admin(user_id: int | None) -> bool:
    return bool(user_id) and user_id in ADMIN_IDS


# --------- FSM для добавления товара ---------


class CreateState(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_desc = State()
    waiting_url = State()
    waiting_photo = State()


# --------- FSM для редактирования товара ---------


class EditState(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_desc = State()
    waiting_url = State()
    waiting_photo = State()


# ---------------- ВХОД В АДМИНКУ ----------------


@router.message(F.text == "⚙️ Админка")
async def open_admin_panel(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.clear()

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [types.KeyboardButton(text="📋 Товары: корзинки")],
            [types.KeyboardButton(text="📋 Товары: курсы")],
            [types.KeyboardButton(text="📦 Заказы")],
            [types.KeyboardButton(text="⬅️ В главное меню")],
        ],
    )

    await message.answer("⚙️ Админ-панель.\nВыберите категорию:", reply_markup=kb)


# =====================================================================
#            ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: СПИСОК ТОВАРОВ С ФИЛЬТРОМ
# =====================================================================


async def _send_products_list(
    target_message: types.Message,
    state: FSMContext,
    category: str,
    status: str = "all",
) -> None:
    """
    Показ списка товаров в админке с учётом фильтра по статусу.

    category: 'basket' или 'course'
    status:  'all' | 'active' | 'hidden' | 'deleted'
    """
    status = (status or "all").lower()
    if status not in ("all", "active", "hidden", "deleted"):
        status = "all"

    products = products_service.list_products_by_status(
        product_type=category,
        status=status,
        limit=100,
    )

    await state.update_data(category=category, status=status)

    title = "🧺 Корзинки" if category == "basket" else "🎓 Курсы"
    human = {
        "all": "все",
        "active": "только активные",
        "hidden": "только скрытые / «удалённые»",
        "deleted": "только скрытые / «удалённые»",
    }.get(status, "все")

    text = f"{title} (админ)\nФильтр: {human}\n\nВыберите товар:"

    await target_message.answer(
        text,
        reply_markup=products_list_kb(products, category, status),
    )


# =====================================================================
#                           СПИСКИ ТОВАРОВ
# =====================================================================


@router.message(F.text == "📋 Товары: корзинки")
async def show_baskets_admin(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await _send_products_list(message, state, category="basket", status="all")


@router.message(F.text == "📋 Товары: курсы")
async def show_courses_admin(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await _send_products_list(message, state, category="course", status="all")


# ---------------- ВЫБОР КОНКРЕТНОГО ТОВАРА ----------------


@router.callback_query(F.data.startswith("admin:product:"))
async def admin_product_selected(callback: types.CallbackQuery, state: FSMContext):
    """
    Клик по товару → показываем карточку (фото + текст) и меню действий.
    """
    if not _is_admin(callback.from_user.id):
        return

    _, _, raw_id = (callback.data or "").split(":")
    product_id = int(raw_id)

    product = products_service.get_product_by_id(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await state.update_data(product_id=product_id)

    name = product["name"]
    price = product["price"]
    desc = product.get("description") or "(нет описания)"
    photo = product.get("image_file_id")

    caption = (
        f"🛒 <b>{name}</b>\n"
        f"ID: <code>{product_id}</code>\n"
        f"💰 Цена: <b>{price} ₽</b>\n\n"
        f"{desc}"
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    if photo:
        await callback.message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=admin_product_actions_kb(product_id),
        )
    else:
        await callback.message.answer(
            caption,
            reply_markup=admin_product_actions_kb(product_id),
        )


# ---------------- НАЗАД К СПИСКУ ----------------


@router.callback_query(F.data == "admin:back_to_list")
async def admin_back_list(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    category = data.get("category", "basket")
    status = data.get("status", "all")

    try:
        await callback.message.delete()
    except Exception:
        pass

    await _send_products_list(callback.message, state, category=category, status=status)


# ---------------- НАЗАД В АДМИНКУ ----------------


@router.callback_query(F.data == "admin:back")
async def admin_back_panel(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [types.KeyboardButton(text="📋 Товары: корзинки")],
            [types.KeyboardButton(text="📋 Товары: курсы")],
            [types.KeyboardButton(text="📦 Заказы")],
            [types.KeyboardButton(text="⬅️ В главное меню")],
        ],
    )

    await callback.message.answer("⚙️ Админ-панель.\nВыберите категорию:", reply_markup=kb)


# ---------------- ДОМОЙ (в обычное главное меню) ----------------


@router.callback_query(F.data == "admin:home")
async def admin_home_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "Главное меню:",
        reply_markup=get_main_menu(is_admin=True),
    )


# =====================================================================
#                           СОЗДАНИЕ ТОВАРА
# =====================================================================


@router.callback_query(F.data == "admin:add:basket")
async def admin_add_basket(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()
    await state.update_data(product_type="basket")

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.set_state(CreateState.waiting_name)
    await callback.message.answer("➕ Добавление корзинки.\n\nВведите название товара:")


@router.callback_query(F.data == "admin:add:course")
async def admin_add_course(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()
    await state.update_data(product_type="course")

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.set_state(CreateState.waiting_name)
    await callback.message.answer("➕ Добавление курса.\n\nВведите название товара:")


@router.message(CreateState.waiting_name)
async def create_product_name(message: types.Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Введите ещё раз:")
        return

    await state.update_data(name=name)
    await state.set_state(CreateState.waiting_price)

    await message.answer(f"Название: <b>{name}</b>\nТеперь введите цену (число):")


@router.message(CreateState.waiting_price)
async def create_product_price(message: types.Message, state: FSMContext):
    raw = (message.text or "").replace(" ", "")
    if not raw.isdigit():
        await message.answer("Цена должна быть числом. Введите ещё раз:")
        return

    price = int(raw)
    await state.update_data(price=price)
    await state.set_state(CreateState.waiting_desc)

    await message.answer("Введите описание товара (или '-' чтобы оставить пустым):")


@router.message(CreateState.waiting_desc)
async def create_product_desc(message: types.Message, state: FSMContext):
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""

    await state.update_data(description=desc)
    await state.set_state(CreateState.waiting_url)

    await message.answer("Введите ссылку «Подробнее» или '-' если ссылки нет:")


@router.message(CreateState.waiting_url)
async def create_product_url(message: types.Message, state: FSMContext):
    url = (message.text or "").strip()
    if url == "-":
        url = None

    await state.update_data(detail_url=url)
    await state.set_state(CreateState.waiting_photo)

    await message.answer("Отправьте фото товара или '-' если без фото:")


@router.message(CreateState.waiting_photo)
async def create_product_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()

    product_type = data.get("product_type")
    name = data.get("name")
    price = data.get("price")
    description = data.get("description") or ""
    detail_url = data.get("detail_url")

    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    else:
        txt = (message.text or "").strip()
        if txt != "-":
            await message.answer("Отправьте фото или '-' для пропуска.")
            return

    product_id = products_service.create_product(
        product_type=product_type,
        name=name,
        price=price,
        description=description,
        detail_url=detail_url,
        image_file_id=image_file_id,
    )

    await state.clear()

    await message.answer(
        f"✅ Товар добавлен!\n\n"
        f"ID: <code>{product_id}</code>\n"
        f"Тип: <b>{'Корзинка' if product_type == 'basket' else 'Курс'}</b>\n"
        f"Название: <b>{name}</b>\n"
        f"Цена: <b>{price} ₽</b>"
    )


# =====================================================================
#                           РЕДАКТИРОВАНИЕ ТОВАРА
# =====================================================================


@router.callback_query(F.data.startswith("admin:edit:name:"))
async def admin_edit_name_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    _, _, _, raw_id = (callback.data or "").split(":")
    product_id = int(raw_id)

    await state.clear()
    await state.update_data(product_id=product_id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.set_state(EditState.waiting_name)
    await callback.message.answer(
        f"✏ Изменение названия товара ID <code>{product_id}</code>\n\n"
        f"Введите новое название:"
    )


@router.message(EditState.waiting_name)
async def admin_edit_name_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("product_id")

    new_name = (message.text or "").strip()
    if not new_name:
        await message.answer("Название не может быть пустым. Введите ещё раз:")
        return

    products_service.update_product_name(product_id, new_name)
    await state.clear()

    await message.answer(
        f"✅ Название товара ID <code>{product_id}</code> обновлено на:\n<b>{new_name}</b>",
        reply_markup=admin_product_actions_kb(product_id),
    )


@router.callback_query(F.data.startswith("admin:edit:price:"))
async def admin_edit_price_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    _, _, _, raw_id = (callback.data or "").split(":")
    product_id = int(raw_id)

    await state.clear()
    await state.update_data(product_id=product_id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.set_state(EditState.waiting_price)
    await callback.message.answer(
        f"💰 Изменение цены товара ID <code>{product_id}</code>\n\n"
        f"Введите новую цену (число):"
    )


@router.message(EditState.waiting_price)
async def admin_edit_price_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("product_id")

    raw = (message.text or "").replace(" ", "")
    if not raw.isdigit():
        await message.answer("Цена должна быть числом. Введите ещё раз:")
        return

    new_price = int(raw)
    products_service.update_product_price(product_id, new_price)

    await state.clear()

    await message.answer(
        f"✅ Цена товара ID <code>{product_id}</code> обновлена на <b>{new_price} ₽</b>",
        reply_markup=admin_product_actions_kb(product_id),
    )


@router.callback_query(F.data.startswith("admin:edit:desc:"))
async def admin_edit_desc_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    _, _, _, raw_id = (callback.data or "").split(":")
    product_id = int(raw_id)

    await state.clear()
    await state.update_data(product_id=product_id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.set_state(EditState.waiting_desc)
    await callback.message.answer(
        f"📝 Изменение описания товара ID <code>{product_id}</code>\n\n"
        f"Введите новое описание (или '-' чтобы удалить описание):"
    )


@router.message(EditState.waiting_desc)
async def admin_edit_desc_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("product_id")

    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""

    products_service.update_product_description(product_id, desc)

    await state.clear()

    await message.answer(
        "✅ Описание товара обновлено.",
        reply_markup=admin_product_actions_kb(product_id),
    )


@router.callback_query(F.data.startswith("admin:edit:link:"))
async def admin_edit_link_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    _, _, _, raw_id = (callback.data or "").split(":")
    product_id = int(raw_id)

    await state.clear()
    await state.update_data(product_id=product_id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.set_state(EditState.waiting_url)
    await callback.message.answer(
        f"🔗 Изменение ссылки товара ID <code>{product_id}</code>\n\n"
        f"Введите новую ссылку (или '-' чтобы удалить ссылку):"
    )


@router.message(EditState.waiting_url)
async def admin_edit_link_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("product_id")

    url = (message.text or "").strip()
    if url == "-":
        url = None

    products_service.update_product_detail_url(product_id, url)

    await state.clear()

    await message.answer(
        f"✅ Ссылка товара обновлена: {url or '(нет ссылки)'}",
        reply_markup=admin_product_actions_kb(product_id),
    )


@router.callback_query(F.data.startswith("admin:edit:photo:"))
async def admin_edit_photo_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    _, _, _, raw_id = (callback.data or "").split(":")
    product_id = int(raw_id)

    await state.clear()
    await state.update_data(product_id=product_id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.set_state(EditState.waiting_photo)
    await callback.message.answer(
        f"🖼 Изменение фото товара ID <code>{product_id}</code>\n\n"
        f"Отправьте новое фото одним сообщением\n"
        f"или '-' чтобы удалить фото:"
    )


@router.message(EditState.waiting_photo)
async def admin_edit_photo_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("product_id")

    image_file_id = None

    if message.photo:
        image_file_id = message.photo[-1].file_id
    else:
        txt = (message.text or "").strip()
        if txt != "-":
            await message.answer("Отправьте фото или '-' чтобы удалить фото.")
            return

    products_service.update_product_image(product_id, image_file_id)

    await state.clear()

    await message.answer(
        "✅ Фото обновлено." if image_file_id else "✅ Фото удалено.",
        reply_markup=admin_product_actions_kb(product_id),
    )


# ---------------- СКРЫТЬ / ПЕРЕКЛЮЧИТЬ ПОКАЗ ----------------


@router.callback_query(F.data.startswith("admin:hide:"))
async def admin_hide_product(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    _, _, raw_id = (callback.data or "").split(":")
    product_id = int(raw_id)

    products_service.soft_delete_product(product_id)

    await callback.answer()

    await callback.message.answer(
        f"🚫 Товар ID <code>{product_id}</code> скрыт (is_active = 0).",
        reply_markup=admin_product_actions_kb(product_id),
    )


@router.callback_query(F.data.startswith("admin:toggle:"))
async def admin_toggle_product(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    _, _, raw_id = (callback.data or "").split(":")
    product_id = int(raw_id)

    products_service.toggle_product_active(product_id)

    await callback.answer()

    await callback.message.answer(
        f"🔁 Статус показа товара ID <code>{product_id}</code> переключён.",
        reply_markup=admin_product_actions_kb(product_id),
    )


# ---------------- "Удаление" временно = скрытие ----------------


@router.callback_query(F.data.startswith("admin:delete_disabled:"))
async def admin_delete_disabled(callback: types.CallbackQuery):
    """
    Временная заглушка — реального удаления нет, используем «Скрыть».
    """
    if not _is_admin(callback.from_user.id):
        return

    await callback.answer("Удаление товара пока не настроено 🛠", show_alert=True)


# =====================================================================
#                           СПИСОК ЗАКАЗОВ
# =====================================================================


@router.message(Command("orders"))
@router.message(F.text == "📦 Заказы")
async def admin_list_orders(message: types.Message):
    """
    Показывает последние заказы для администратора.
    """
    if not _is_admin(message.from_user.id):
        return

    orders = orders_service.get_last_orders(20)
    if not orders:
        await message.answer("Пока заказов нет.")
        return

    lines = ["📦 <b>Последние заказы:</b>\n"]

    for o in orders:
        lines.append(
            f"Заказ <b>#{o['id']}</b>\n"
            f"👤 {o['customer_name']}\n"
            f"📞 {o['contact']}\n"
            f"💰 {o['total']} ₽\n"
            f"🕒 {o['created_at']}\n"
        )

    await message.answer("\n".join(lines))


# ---------------- ВЫХОД В ГЛАВНОЕ МЕНЮ ----------------


@router.message(F.text == "⬅️ В главное меню")
async def admin_go_main(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu(is_admin=_is_admin(message.from_user.id)),
    )


# ---------------- ФИЛЬТР СПИСКА ТОВАРОВ В АДМИНКЕ ----------------


@router.callback_query(F.data.startswith("admin:flt:"))
async def admin_filter_products(callback: types.CallbackQuery, state: FSMContext):
    """
    admin:flt:<type>:<status>

    type:
        - basket
        - course

    status:
        - all
        - active
        - hidden / deleted (считаем как скрытые)
    """
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Неверный формат фильтра.", show_alert=True)
        return

    _, _, product_type, status_code = parts

    if product_type not in ("basket", "course"):
        await callback.answer("Неизвестная категория.", show_alert=True)
        return

    status_code = (status_code or "all").lower()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await _send_products_list(callback.message, state, category=product_type, status=status_code)
    await callback.answer()


# ---------------- ПУСТАЯ КНОПКА (для строки «пока нет товаров») ----------------


@router.callback_query(F.data == "admin:noop")
async def admin_noop(callback: types.CallbackQuery):
    """
    Ничего не делаем, просто закрываем «кружочек» загрузки.
    """
    if not _is_admin(callback.from_user.id):
        return

    await callback.answer()
