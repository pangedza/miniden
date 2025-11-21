from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from services import products as products_service
from services import stats as stats_service
from services import orders as orders_service
from services import promocodes as promocodes_service
from services import user_admin as user_admin_service
from services import user_stats as user_stats_service
from keyboards.admin_inline import (
    products_list_kb,
    admin_product_actions_kb,
    course_access_list_kb,
    course_access_actions_kb,
)
from keyboards.main_menu import get_admin_menu, get_main_menu
from utils.commands_map import get_admin_commands, get_user_commands
from utils.texts import (
    format_admin_client_profile,
    format_order_detail_text,
    format_orders_list_text,
    format_order_status_changed_for_user,
    format_stats_by_day,
    format_stats_summary,
    format_top_products,
    format_user_courses_access_granted,
    format_user_notes,
    format_price,
)

router = Router()


def _is_admin(user_id: int | None) -> bool:
    return bool(user_id) and user_id in ADMIN_IDS


def _build_order_actions_kb(order_id: int, user_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="👁 Открыть", callback_data=f"admin:order:open:{order_id}"
                ),
                types.InlineKeyboardButton(
                    text="✅ Оплачен", callback_data=f"admin:order:paid:{order_id}"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="📁 В архив", callback_data=f"admin:order:archive:{order_id}"
                ),
                types.InlineKeyboardButton(
                    text="👤 CRM", callback_data=f"admin:order:client:{user_id}"
                ),
            ],
        ]
    )


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


def _build_stats_period_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="📅 Сегодня", callback_data="admin:stats:today"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="7 дней", callback_data="admin:stats:7d"
                ),
                types.InlineKeyboardButton(
                    text="30 дней", callback_data="admin:stats:30d"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="Все время", callback_data="admin:stats:all"
                )
            ],
        ]
    )


def _build_promocodes_menu_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="➕ Создать промокод", callback_data="admin:promo:create"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📋 Список промокодов", callback_data="admin:promo:list"
                )
            ],
        ]
    )


def _build_promocode_type_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Процент", callback_data="admin:promo:type:percent"
                ),
                types.InlineKeyboardButton(
                    text="Фиксированная", callback_data="admin:promo:type:fixed"
                ),
            ]
        ]
    )


def _format_promocode_line(promo: dict) -> str:
    code = promo.get("code") or "—"
    discount_type = promo.get("discount_type")
    discount_value = int(promo.get("discount_value", 0) or 0)
    is_active = int(promo.get("is_active", 0) or 0) == 1

    if discount_type == "percent":
        discount_text = f"{discount_value}%"
    else:
        discount_text = f"{format_price(discount_value)}"

    status_text = "активен" if is_active else "выключен"
    return f"{code} — {discount_text} [{status_text}]"


async def _send_orders_menu(message: types.Message) -> None:
    await message.answer(
        "📦 <b>Раздел заказов</b>\nВыберите, какие заказы показать:",
        reply_markup=_build_orders_menu_kb(),
    )


async def _send_stats_menu(target_message: types.Message) -> None:
    await target_message.answer(
        "Выберите период для статистики:", reply_markup=_build_stats_period_kb()
    )


# --------- FSM для добавления товара ---------


class CreateState(StatesGroup):
    waiting_name = State()
    waiting_payment_type = State()
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


class PromoCreateState(StatesGroup):
    waiting_code = State()
    waiting_type = State()
    waiting_value = State()
    waiting_min_total = State()
    waiting_max_uses = State()


# ---------------- ВХОД В АДМИНКУ ----------------


@router.message(F.text == "⚙️ Админка")
async def open_admin_panel(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.clear()

    await message.answer(
        "⚙️ Админ-панель.\nВыберите категорию:", reply_markup=get_admin_menu()
    )


@router.message(F.text == "👤 Клиент (CRM)")
async def admin_client_menu_hint(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await message.answer(
        "Отправьте команду <code>/client &lt;telegram_id&gt;</code>, "
        "чтобы открыть профиль нужного клиента."
    )


@router.message(F.text == "🚫 Бан / ✅ Разбан")
async def admin_ban_menu_hint(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await message.answer(
        "Используйте команды:\n"
        "• <code>/ban &lt;user_id&gt; [причина]</code>\n"
        "• <code>/unban &lt;user_id&gt;</code>"
    )


@router.message(Command("stats"))
async def admin_stats_command(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await _send_stats_menu(message)


@router.message(Command("promo_stats"))
async def admin_promo_stats_command(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    promos = promocodes_service.get_promocodes_usage_summary()
    lines: list[str] = ["🎟 <b>Статистика промокодов</b>", ""]

    if not promos:
        lines.append("Промокоды ещё не созданы.")
    else:
        for promo in promos:
            code = promo.get("code") or "—"
            discount_type = promo.get("discount_type")
            value = int(promo.get("discount_value", 0) or 0)
            used = int(promo.get("used_count", 0) or 0)
            max_uses = int(promo.get("max_uses", 0) or 0)
            limit_text = "∞" if max_uses == 0 else str(max_uses)
            discount_text = f"{value}%" if discount_type == "percent" else f"{format_price(value)}"
            lines.append(
                f"{code} — {discount_text}, использований: {used} / {limit_text}"
            )

    await message.answer("\n".join(lines).strip())


@router.message(F.text == "📊 Статистика")
async def admin_stats_button(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await _send_stats_menu(message)


@router.message(F.text == "🎟 Промокоды")
async def admin_promocodes_menu(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await message.answer(
        "🎟 <b>Управление промокодами</b>", reply_markup=_build_promocodes_menu_kb()
    )


@router.callback_query(F.data.startswith("admin:stats:"))
async def admin_stats_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    period = parts[-1]
    today = datetime.now().date()
    date_from: str | None = None
    date_to: str | None = None
    days_limit: int | None = None
    title = "Статистика"

    if period == "today":
        date_iso = today.isoformat()
        date_from = f"{date_iso}T00:00:00"
        date_to = f"{date_iso}T23:59:59"
        days_limit = 1
        title = "Статистика за сегодня"
    elif period == "7d":
        start_date = today - timedelta(days=6)
        date_from = f"{start_date.isoformat()}T00:00:00"
        date_to = f"{today.isoformat()}T23:59:59"
        days_limit = 7
        title = "Статистика за 7 дней"
    elif period == "30d":
        start_date = today - timedelta(days=29)
        date_from = f"{start_date.isoformat()}T00:00:00"
        date_to = f"{today.isoformat()}T23:59:59"
        days_limit = 30
        title = "Статистика за 30 дней"
    elif period == "all":
        title = "Статистика за все время"
    else:
        await callback.answer("Неизвестный период", show_alert=True)
        return

    summary = stats_service.get_orders_stats_summary(date_from, date_to)
    by_day: list[dict] = []
    if days_limit:
        by_day = stats_service.get_orders_stats_by_day(days_limit)

    top_products = stats_service.get_top_products(5)
    top_courses = stats_service.get_top_courses(5)

    text_parts = [format_stats_summary(title, summary)]
    if days_limit:
        text_parts.append(format_stats_by_day(by_day))
    text_parts.append(format_top_products("Топ товаров", top_products))
    text_parts.append(format_top_products("Топ курсов", top_courses))

    text = "\n\n".join(text_parts).strip()

    try:
        await callback.message.edit_text(text, reply_markup=_build_stats_period_kb())
    except Exception:
        await callback.message.answer(text, reply_markup=_build_stats_period_kb())

    await callback.answer()


@router.callback_query(F.data == "admin:promo:list")
async def admin_promocode_list(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    promos = promocodes_service.list_promocodes(limit=30)
    lines: list[str] = ["🎟 <b>Промокоды</b>", ""]

    if not promos:
        lines.append("Промокоды ещё не созданы.")
    else:
        for promo in promos:
            lines.append(_format_promocode_line(promo))

    keyboard_rows: list[list[types.InlineKeyboardButton]] = []
    for promo in promos:
        code = promo.get("code")
        if not code:
            continue
        is_active = int(promo.get("is_active", 0) or 0) == 1
        toggle_text = "ON" if not is_active else "OFF"
        keyboard_rows.append(
            [
                types.InlineKeyboardButton(
                    text=f"{code}: {toggle_text}",
                    callback_data=f"admin:promo:toggle:{code}",
                )
            ]
        )

    reply_markup = (
        types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        if keyboard_rows
        else None
    )
    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines).strip(), reply_markup=reply_markup
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo:toggle:"))
async def admin_promocode_toggle(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":", 3)
    if len(parts) < 3:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    code = parts[-1]
    promo = promocodes_service.get_promocode_by_code(code)
    if not promo:
        await callback.answer("Промокод не найден", show_alert=True)
        return

    current_status = int(promo.get("is_active", 0) or 0) == 1
    promocodes_service.set_promocode_active(code, not current_status)
    new_status = "активен" if not current_status else "отключён"
    await callback.answer(f"Промокод {code} теперь {new_status}")
    await admin_promocode_list(callback)


@router.callback_query(F.data == "admin:promo:create")
async def admin_promocode_create_start(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await state.set_state(PromoCreateState.waiting_code)
    await callback.message.edit_text(
        "Введите код промокода (можно с пробелами, мы его нормализуем):"
    )
    await callback.answer()


@router.message(PromoCreateState.waiting_code)
async def admin_promocode_enter_code(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    await state.update_data(promo_code=(message.text or "").strip())
    await message.answer(
        "Выберите тип скидки:", reply_markup=_build_promocode_type_kb()
    )
    await state.set_state(PromoCreateState.waiting_type)


@router.callback_query(F.data.startswith("admin:promo:type:"))
async def admin_promocode_choose_type(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    promo_type = parts[-1]
    if promo_type not in {"percent", "fixed"}:
        await callback.answer("Неизвестный тип", show_alert=True)
        return

    await state.update_data(promo_type=promo_type)
    await callback.message.edit_text(
        "Введите значение скидки (число). Например: 10 или 500"
    )
    await state.set_state(PromoCreateState.waiting_value)
    await callback.answer()


@router.message(PromoCreateState.waiting_value)
async def admin_promocode_enter_value(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    try:
        value = int((message.text or "").strip())
        if value <= 0:
            raise ValueError
    except Exception:
        await message.answer("Введите положительное число для скидки")
        return

    await state.update_data(promo_value=value)
    await message.answer("Минимальная сумма заказа для применения (0 — без ограничений):")
    await state.set_state(PromoCreateState.waiting_min_total)


@router.message(PromoCreateState.waiting_min_total)
async def admin_promocode_enter_min_total(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    try:
        min_total = int((message.text or "").strip() or 0)
    except Exception:
        await message.answer("Введите число (0 — без ограничения)")
        return

    await state.update_data(min_total=min_total)
    await message.answer("Максимальное количество использований (0 — без лимита):")
    await state.set_state(PromoCreateState.waiting_max_uses)


@router.message(PromoCreateState.waiting_max_uses)
async def admin_promocode_enter_max_uses(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    try:
        max_uses = int((message.text or "").strip() or 0)
        if max_uses < 0:
            max_uses = 0
    except Exception:
        await message.answer("Введите число (0 — без ограничения)")
        return

    data = await state.get_data()
    code = data.get("promo_code", "")
    promo_type = data.get("promo_type", "")
    value = int(data.get("promo_value", 0) or 0)
    min_total = int(data.get("min_total", 0) or 0)

    try:
        new_id = promocodes_service.create_promocode(
            code=code,
            discount_type=promo_type,
            discount_value=value,
            min_order_total=min_total,
            max_uses=max_uses,
        )
    except Exception as exc:  # noqa: BLE001
        await message.answer(f"Не удалось создать промокод: {exc}")
        await state.clear()
        return

    if new_id == -1:
        await message.answer("Такой промокод уже существует. Попробуйте другой код.")
        await state.clear()
        return

    code_normalized = promocodes_service.normalize_code(code)
    limit_text = "без лимита" if max_uses == 0 else f"{max_uses} раз"
    min_total_text = "без ограничений" if min_total == 0 else f"от {min_total} ₽"
    discount_text = f"{value}%" if promo_type == "percent" else f"{format_price(value)}"

    await message.answer(
        "Создан промокод: \n"
        f"{code_normalized} — {discount_text}, {min_total_text}, {limit_text}"
    )
    await state.clear()


@router.message(F.text == "📝 Заметки")
async def admin_notes_menu_hint(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    await message.answer(
        "Работа с заметками:\n"
        "• <code>/note &lt;user_id&gt; &lt;текст&gt;</code> — добавить заметку\n"
        "• <code>/notes &lt;user_id&gt;</code> — посмотреть заметки"
    )


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
    data = await state.get_data()
    product_type = data.get("product_type")

    if product_type == "course":
        await state.set_state(CreateState.waiting_payment_type)

        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="💸 Бесплатный", callback_data="admin:course:new:free"
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="💰 Платный", callback_data="admin:course:new:paid"
                    )
                ],
            ]
        )

        await message.answer(
            "Курс платный или бесплатный?",
            reply_markup=kb,
        )
        return

    await state.set_state(CreateState.waiting_price)
    await message.answer(f"Название: <b>{name}</b>\nТеперь введите цену (число):")


@router.callback_query(F.data == "admin:course:new:free")
async def admin_course_new_free(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    current_state = await state.get_state()
    if current_state != CreateState.waiting_payment_type.state:
        await callback.answer("Сейчас не ожидается выбор типа оплаты", show_alert=True)
        return

    await state.update_data(price=0)
    await state.set_state(CreateState.waiting_desc)

    await callback.message.answer(
        "Вы выбрали бесплатный курс.\nВведите описание товара (или '-' чтобы оставить пустым):"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:course:new:paid")
async def admin_course_new_paid(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    current_state = await state.get_state()
    if current_state != CreateState.waiting_payment_type.state:
        await callback.answer("Сейчас не ожидается выбор типа оплаты", show_alert=True)
        return

    await state.set_state(CreateState.waiting_price)
    await callback.message.answer("Введите стоимость курса в рублях:")
    await callback.answer()


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
    price = int(data.get("price") or 0)
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
        f"Цена: <b>{format_price(price)}</b>"
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
#                          ДЕБАГ СПИСКА КОМАНД
# =====================================================================


@router.message(Command("debug_commands"))
async def admin_debug_commands(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    user_cmds = get_user_commands()
    admin_cmds = get_admin_commands()

    lines: list[str] = ["🧩 <b>Команды бота</b>", "", "👥 Пользовательские:"]

    if user_cmds:
        for name, desc in sorted(user_cmds.items()):
            lines.append(f"/{name} — {desc}")
    else:
        lines.append("(нет пользовательских команд)")

    lines.append("")
    lines.append("🛠 Админские:")

    if admin_cmds:
        for name, desc in sorted(admin_cmds.items()):
            lines.append(f"/{name} — {desc}")
    else:
        lines.append("(нет админских команд)")

    await message.answer("\n".join(lines))


# =====================================================================
#                    БАН/РАЗБАН И ЗАМЕТКИ ПО ПОЛЬЗОВАТЕЛЯМ
# =====================================================================


@router.message(Command("ban"))
async def admin_ban_user(message: types.Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(
            "Использование: <code>/ban &lt;user_id&gt; [причина]</code>"
        )
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "Использование: <code>/ban &lt;user_id&gt; [причина]</code>"
        )
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
        await message.answer("Использование: <code>/unban &lt;user_id&gt;</code>")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Использование: <code>/unban &lt;user_id&gt;</code>")
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
        await message.answer(
            "Использование: <code>/note &lt;user_id&gt; &lt;текст заметки&gt;</code>"
        )
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "Использование: <code>/note &lt;user_id&gt; &lt;текст заметки&gt;</code>"
        )
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
        await message.answer("Использование: <code>/notes &lt;user_id&gt;</code>")
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Использование: <code>/notes &lt;user_id&gt;</code>")
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

    usage_text = "Использование: <code>/client &lt;telegram_id_пользователя&gt;</code>"
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

    for order in orders:
        status = order.get("status", orders_service.STATUS_NEW)
        status_title = orders_service.STATUS_TITLES.get(status, status)
        user_id = int(order.get("user_id") or 0)
        order_id = int(order.get("id") or 0)
        header_lines = [
            f"Заказ №{order_id} — {status_title}",
            f"user_id=<code>{user_id}</code>",
        ]

        await callback.message.answer(
            "\n".join(header_lines),
            reply_markup=_build_order_actions_kb(order_id, user_id),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:open:"))
async def admin_order_open(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный номер заказа", show_alert=True)
        return

    order = orders_service.get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="👤 Профиль клиента",
                    callback_data=f"admin:order:client:{order.get('user_id')}",
                )
            ]
        ]
    )

    await callback.message.answer(format_order_detail_text(order), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:paid:"))
async def admin_order_paid(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный номер заказа", show_alert=True)
        return

    success = orders_service.set_order_status(order_id, orders_service.STATUS_PAID)
    granted_count = 0
    order = orders_service.get_order_by_id(order_id)

    if success:
        granted_count = orders_service.grant_courses_from_order(
            order_id, admin_id=callback.from_user.id
        )

        admin_text = f"Заказ №{order_id} переведён в статус: Оплачен"
        if granted_count > 0:
            admin_text += f"\nОткрыт доступ к {granted_count} курсам пользователю."

        await callback.message.answer(admin_text)

        # Уведомляем пользователя о статусе/доступе
        try:
            user_id = int(order.get("user_id")) if order else None
        except Exception:
            user_id = None

        if user_id:
            user_text: str | None = None
            if granted_count > 0:
                courses = orders_service.get_courses_from_order(order_id)
                if courses:
                    user_text = format_user_courses_access_granted(order_id, courses)

            if not user_text:
                user_text = format_order_status_changed_for_user(
                    order_id, orders_service.STATUS_PAID
                )

            if user_text:
                try:
                    await callback.message.bot.send_message(
                        chat_id=user_id, text=user_text
                    )
                except Exception as e:
                    print(
                        f"Failed to notify user {user_id} about order {order_id}: {e}"
                    )
    else:
        await callback.message.answer("Не удалось изменить статус заказа.")

    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:archive:"))
async def admin_order_archive(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        order_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный номер заказа", show_alert=True)
        return

    success = orders_service.set_order_status(
        order_id, orders_service.STATUS_ARCHIVED
    )
    if success:
        await callback.message.answer(f"Заказ №{order_id} отправлен в архив.")

        order = orders_service.get_order_by_id(order_id)
        try:
            user_id = int(order.get("user_id")) if order else None
        except Exception:
            user_id = None

        if user_id:
            try:
                await callback.message.bot.send_message(
                    chat_id=user_id,
                    text=format_order_status_changed_for_user(
                        order_id, orders_service.STATUS_ARCHIVED
                    ),
                )
            except Exception as e:
                print(
                    f"Failed to notify user {user_id} about order {order_id}: {e}"
                )
    else:
        await callback.message.answer("Не удалось изменить статус заказа.")

    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:client:"))
async def admin_order_client_profile(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    try:
        target_user_id = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный user_id", show_alert=True)
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
        await callback.message.answer(
            "По этому пользователю пока нет данных (заказов и курсов не найдено)."
        )
        await callback.answer()
        return

    text = format_admin_client_profile(
        target_user_id,
        user_stats=user_stats,
        courses_summary=courses_summary,
        ban_status=ban_status,
        notes=notes,
        notes_limit=5,
    )
    await callback.message.answer(text)
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
