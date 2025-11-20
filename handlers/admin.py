from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from services import products as products_service
from services import orders as orders_service
from services import user_admin as user_admin_service
from services import user_stats as user_stats_service
from keyboards.admin_inline import (
    products_list_kb,
    admin_product_actions_kb,
    course_access_list_kb,
    course_access_actions_kb,
)
from keyboards.main_menu import get_main_menu
from utils.texts import (
    format_admin_client_profile,
    format_orders_list_text,
    format_user_notes,
)

router = Router()


def _is_admin(user_id: int | None) -> bool:
    return bool(user_id) and user_id in ADMIN_IDS


def _build_orders_menu_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🆕 Новые", callback_data="admin:orders:status:new"
                ),
                types.InlineKeyboardButton(
                    text="🕒 В работе", callback_data="admin:orders:status:in_progress"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="✅ Оплаченные", callback_data="admin:orders:status:paid"
                ),
                types.InlineKeyboardButton(
                    text="📤 Отправленные", callback_data="admin:orders:status:sent"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="📁 Архив", callback_data="admin:orders:status:archived"
                ),
                types.InlineKeyboardButton(
                    text="📦 Все", callback_data="admin:orders:status:all"
                ),
            ],
        ]
    )


async def _send_orders_menu(message: types.Message) -> None:
    await message.answer(
        "📦 <b>Раздел заказов</b>\nВыберите, какие заказы показать:",
        reply_markup=_build_orders_menu_kb(),
    )


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


class CourseAccessState(StatesGroup):
    waiting_grant_user_id = State()
    waiting_revoke_user_id = State()


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
            [types.KeyboardButton(text="🎓 Доступ к курсам")],
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
            [types.KeyboardButton(text="🎓 Доступ к курсам")],
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
#                 УПРАВЛЕНИЕ ДОСТУПОМ К КУРСАМ (АДМИН)
# =====================================================================


async def _send_course_access_list(target_message: types.Message) -> None:
    courses = products_service.get_courses()
    text = "🎓 Выберите курс для управления доступом:" if courses else "Пока нет курсов для управления доступом."

    await target_message.answer(
        text,
        reply_markup=course_access_list_kb(courses),
    )


async def _send_course_access_info(target_message: types.Message, course_id: int) -> None:
    course = products_service.get_product_by_id(course_id)
    if not course or course.get("type") != "course":
        await target_message.answer("Курс не найден или недоступен.")
        return

    users = orders_service.get_course_users(course_id)

    lines: list[str] = [
        f"🎓 <b>{course['name']}</b> (ID: <code>{course_id}</code>)",
        f"Пользователей с доступом: <b>{len(users)}</b>",
    ]

    if users:
        lines.append("\nСписок (первые 10):")
        for u in users[:10]:
            base = f"• {u['user_id']}"
            extra_parts: list[str] = []
            if u.get("granted_at"):
                extra_parts.append(u["granted_at"])
            if u.get("comment"):
                extra_parts.append(u["comment"])

            if extra_parts:
                base += " — " + "; ".join(extra_parts)

            lines.append(base)

        if len(users) > 10:
            lines.append(f"… и ещё {len(users) - 10} пользователей")

    await target_message.answer(
        "\n".join(lines).strip(),
        reply_markup=course_access_actions_kb(course_id),
    )


@router.message(F.text == "🎓 Доступ к курсам")
async def admin_course_access_entry(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.clear()
    await _send_course_access_list(message)


@router.callback_query(F.data == "admin:course_access:list")
async def admin_course_access_list(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()
    await _send_course_access_list(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:course_access:grant:"))
async def admin_course_access_grant(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        course_id = int(parts[3])
    except ValueError:
        await callback.answer("Некорректный ID курса", show_alert=True)
        return

    course = products_service.get_product_by_id(course_id)
    if not course or course.get("type") != "course":
        await callback.answer("Курс не найден", show_alert=True)
        return

    await state.clear()
    await state.update_data(course_id=course_id)
    await state.set_state(CourseAccessState.waiting_grant_user_id)

    await callback.message.answer(
        f"Введите user_id для выдачи доступа к курсу <b>{course['name']}</b> (ID: <code>{course_id}</code>):"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:course_access:revoke:"))
async def admin_course_access_revoke(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        course_id = int(parts[3])
    except ValueError:
        await callback.answer("Некорректный ID курса", show_alert=True)
        return

    course = products_service.get_product_by_id(course_id)
    if not course or course.get("type") != "course":
        await callback.answer("Курс не найден", show_alert=True)
        return

    await state.clear()
    await state.update_data(course_id=course_id)
    await state.set_state(CourseAccessState.waiting_revoke_user_id)

    await callback.message.answer(
        f"Введите user_id для отзыва доступа к курсу <b>{course['name']}</b> (ID: <code>{course_id}</code>):"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:course_access:"))
async def admin_course_access_choose(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        return

    raw_course_id = parts[2]
    if not raw_course_id.isdigit():
        await callback.answer()
        return

    course_id = int(raw_course_id)

    await _send_course_access_info(callback.message, course_id)
    await callback.answer()


@router.message(CourseAccessState.waiting_grant_user_id)
async def admin_course_access_grant_user(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    course_id = data.get("course_id")

    if not course_id:
        await state.clear()
        await message.answer("Курс не найден в состоянии. Попробуйте снова.")
        return

    try:
        user_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Нужно ввести числовой user_id. Попробуйте ещё раз:")
        return

    success = orders_service.grant_course_access(
        user_id=user_id,
        course_id=course_id,
        granted_by=message.from_user.id,
        source_order_id=None,
        comment=None,
    )

    await state.clear()

    if success:
        await message.answer(
            f"Доступ к курсу ID {course_id} выдан пользователю <code>{user_id}</code>."
        )
        await _send_course_access_info(message, course_id)
    else:
        await message.answer("Не удалось выдать доступ. Попробуйте позже.")


@router.message(CourseAccessState.waiting_revoke_user_id)
async def admin_course_access_revoke_user(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    course_id = data.get("course_id")

    if not course_id:
        await state.clear()
        await message.answer("Курс не найден в состоянии. Попробуйте снова.")
        return

    try:
        user_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Нужно ввести числовой user_id. Попробуйте ещё раз:")
        return

    success = orders_service.revoke_course_access(user_id=user_id, course_id=course_id)

    await state.clear()

    if success:
        await message.answer(
            f"Доступ к курсу ID {course_id} отозван у пользователя <code>{user_id}</code>."
        )
        await _send_course_access_info(message, course_id)
    else:
        await message.answer("Не удалось отозвать доступ. Возможно, его и так не было.")


# =====================================================================
#                    БАН/РАЗБАН И ЗАМЕТКИ ПО ПОЛЬЗОВАТЕЛЯМ
# =====================================================================


@router.message(Command("ban"))
async def admin_ban_user(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Использование: /ban <user_id> [причина]")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Использование: /ban <user_id> [причина]")
        return

    reason = parts[2].strip() if len(parts) == 3 else None

    user_admin_service.set_user_ban_status(
        target_user_id, True, admin_id=message.from_user.id, reason=reason
    )

    response = f"Пользователь {target_user_id} забанен."
    if reason:
        response += f" Причина: {reason}"

    await message.answer(response)


@router.message(Command("unban"))
async def admin_unban_user(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /unban <user_id>")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Использование: /unban <user_id>")
        return

    user_admin_service.set_user_ban_status(
        target_user_id, False, admin_id=message.from_user.id, reason=None
    )

    await message.answer(f"Пользователь {target_user_id} разбанен.")


@router.message(Command("note"))
async def admin_add_note(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /note <user_id> <текст заметки>")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Использование: /note <user_id> <текст заметки>")
        return

    note_text = parts[2].strip()
    if not note_text:
        await message.answer("Текст заметки не может быть пустым.")
        return

    user_admin_service.add_user_note(
        user_id=target_user_id, admin_id=message.from_user.id, note=note_text
    )

    await message.answer("Заметка добавлена.")


@router.message(Command("notes"))
async def admin_show_notes(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /notes <user_id>")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Использование: /notes <user_id>")
        return

    notes = user_admin_service.get_user_notes(target_user_id)
    if not notes:
        await message.answer("Заметок для этого пользователя пока нет.")
        return

    notes_text = format_user_notes(notes)
    await message.answer(
        "\n".join(
            [f"📝 Заметки для клиента <code>{target_user_id}</code>", "", notes_text]
        ).strip()
    )


# =====================================================================
#                           ПРОФИЛЬ КЛИЕНТА (CRM)
# =====================================================================


@router.message(Command("client"))
async def admin_client_profile(message: types.Message) -> None:
    """Показать CRM-профиль клиента по Telegram ID."""

    if not _is_admin(message.from_user.id):
        return

    usage_text = "Использование: /client <telegram_id_пользователя>"
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(usage_text)
        return

    try:
        target_user_id = int(parts[1].strip())
    except ValueError:
        await message.answer(usage_text)
        return

    user_stats = user_stats_service.get_user_order_stats(target_user_id)
    courses_summary = user_stats_service.get_user_courses_summary(target_user_id)
    ban_status = user_admin_service.get_user_ban_status(target_user_id)
    notes = user_admin_service.get_user_notes(target_user_id, limit=5)

    has_data = any(
        [
            user_stats.get("total_orders", 0) > 0,
            courses_summary.get("count", 0) > 0,
            ban_status.get("is_banned"),
            len(notes) > 0,
        ]
    )

    if not has_data:
        await message.answer(
            "По этому пользователю пока нет данных (заказов и курсов не найдено)."
        )
        return

    text = format_admin_client_profile(
        target_user_id,
        user_stats=user_stats,
        courses_summary=courses_summary,
        ban_status=ban_status,
        notes=notes,
        notes_limit=5,
    )
    await message.answer(text)


# =====================================================================
#                           СПИСОК ЗАКАЗОВ
# =====================================================================


@router.message(Command("orders"))
@router.message(F.text == "📦 Заказы")
async def admin_orders_menu(message: types.Message):
    """
    Открытие меню заказов в админке.
    """
    if not _is_admin(message.from_user.id):
        return

    await _send_orders_menu(message)


@router.callback_query(F.data.startswith("admin:orders:status:"))
async def admin_orders_filter(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    status = parts[-1]
    orders = orders_service.get_orders_for_admin(status, limit=30)

    if status == orders_service.STATUS_NEW:
        title = "🆕 Новые заказы"
    elif status == orders_service.STATUS_IN_PROGRESS:
        title = "🕒 Заказы в работе"
    elif status == orders_service.STATUS_PAID:
        title = "✅ Оплаченные заказы"
    elif status == orders_service.STATUS_SENT:
        title = "📤 Отправленные заказы"
    elif status == orders_service.STATUS_ARCHIVED:
        title = "📁 Заказы в архиве"
    else:
        title = "📦 Все заказы"

    if not orders:
        text = "Заказов с таким статусом пока нет."
    else:
        text = f"{title}\n\n{format_orders_list_text(orders, show_client_hint=True)}"

    try:
        await callback.message.edit_text(text, reply_markup=_build_orders_menu_kb())
    except Exception:
        await callback.message.answer(text, reply_markup=_build_orders_menu_kb())

    await callback.answer()


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
