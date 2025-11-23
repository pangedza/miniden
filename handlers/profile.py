from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_IDS, get_settings
from services import bans as bans_service
from services import orders as orders_service
from services import stats as stats_service
from services import users as users_service
from services.favorites import list_favorites
from services.subscription import ensure_subscribed
from utils.texts import (
    format_favorites_list,
    format_orders_list_text,
    format_user_courses_list,
)

router = Router()

PROFILE_BUTTON_TEXT = "👤 Профиль"

ACTIVE_STATUSES = {orders_service.STATUS_NEW, orders_service.STATUS_IN_PROGRESS}
FINISHED_STATUSES = {orders_service.STATUS_SENT, orders_service.STATUS_PAID}


def _build_profile_keyboard(active_cnt: int, finished_cnt: int, courses_cnt: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📦 Активные заказы ({active_cnt})",
                    callback_data="profile:orders:active",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🗂 Завершённые заказы ({finished_cnt})",
                    callback_data="profile:orders:finished",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🎓 Мои курсы ({courses_cnt})",
                    callback_data="profile:courses",
                )
            ],
        ]
    )


def _format_profile_text(user, orders: list[dict], courses_cnt: int, stats: dict, ban: dict) -> str:
    full_name_parts = [user.first_name, user.last_name]
    full_name = " ".join(part for part in full_name_parts if part).strip() or "—"
    username = f"@{user.username}" if user.username else "—"
    user_id = user.telegram_id

    total_orders = len(orders)
    active_cnt = len([o for o in orders if o.get("status") in ACTIVE_STATUSES])
    finished_cnt = len([o for o in orders if o.get("status") in FINISHED_STATUSES])

    lines = [
        "👤 <b>Ваш профиль</b>",
        "",
        f"ID: <code>{user_id}</code>",
        f"Имя: <b>{full_name}</b>",
        f"Ник: <b>{username}</b>",
        "",
    ]

    if ban.get("is_banned"):
        lines.append("🚫 <b>Ваш аккаунт заблокирован</b>")
        if ban.get("ban_reason"):
            lines.append(f"Причина: {ban.get('ban_reason')}")
        if ban.get("banned_at"):
            lines.append(f"Дата бана: {ban.get('banned_at')}")
        lines.append("")

    lines.extend(
        [
            f"Всего заказов: <b>{total_orders}</b>",
            f"Активные: <b>{active_cnt}</b>",
            f"Завершённые: <b>{finished_cnt}</b>",
            f"Курсов с доступом: <b>{courses_cnt}</b>",
            f"Потрачено: <b>{int(stats.get('total_spent', 0))} ₽</b>",
        ]
    )

    return "\n".join(lines)


@router.message(Command("profile"))
@router.message(F.text == PROFILE_BUTTON_TEXT)
async def show_profile(message: types.Message) -> None:
    tg_user = message.from_user
    telegram_id = tg_user.id
    is_admin = telegram_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    user = users_service.get_user_by_telegram_id(telegram_id)
    if not user:
        user = users_service.get_or_create_user_from_telegram(
            {
                "id": telegram_id,
                "username": tg_user.username,
                "first_name": tg_user.first_name,
                "last_name": tg_user.last_name,
            }
        )

    orders = orders_service.get_orders_by_user(telegram_id, limit=50)
    courses = orders_service.get_user_courses_with_access(telegram_id)
    stats = stats_service.get_user_stats(telegram_id)
    ban_status = bans_service.is_banned(telegram_id)

    if ban_status.get("is_banned"):
        await message.answer(
            "Ваш аккаунт заблокирован. Для уточнения обратитесь к администратору."
        )
        return

    active_cnt = len([o for o in orders if o.get("status") in ACTIVE_STATUSES])
    finished_cnt = len([o for o in orders if o.get("status") in FINISHED_STATUSES])
    courses_cnt = len(courses)

    banner = get_settings().banner_profile
    if banner:
        await message.answer_photo(photo=banner, caption="👤 Ваш профиль")

    text = _format_profile_text(user, orders, courses_cnt, stats, ban_status)
    await message.answer(
        text,
        reply_markup=_build_profile_keyboard(active_cnt, finished_cnt, courses_cnt),
    )

    favorites = list_favorites(user.telegram_id)
    if favorites:
        await message.answer(format_favorites_list(favorites))

    if orders:
        await message.answer(format_orders_list_text(orders[:5]))


@router.message(F.text == "❤️ Избранное")
async def show_favorites(message: types.Message) -> None:
    """Показать список избранных товаров пользователя."""

    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(message, message.bot, is_admin=is_admin):
        return

    products = list_favorites(user_id)
    text = format_favorites_list(products)

    await message.answer(text)


@router.callback_query(F.data == "profile:orders:active")
async def profile_orders_active(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    orders = orders_service.get_orders_by_user(user_id, limit=50)
    active_orders = [o for o in orders if o.get("status") in ACTIVE_STATUSES]

    text = format_orders_list_text(active_orders)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "profile:orders:finished")
async def profile_orders_finished(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    orders = orders_service.get_orders_by_user(user_id, limit=50)
    finished_orders = [o for o in orders if o.get("status") in FINISHED_STATUSES]

    text = format_orders_list_text(finished_orders)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "profile:courses")
async def profile_courses(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if not await ensure_subscribed(callback, callback.message.bot, is_admin=is_admin):
        return

    courses = orders_service.get_user_courses_with_access(user_id)

    if not courses:
        await callback.message.answer(
            "У вас пока нет курсов с открытым доступом. Оформите заказ и дождитесь, пока администратор откроет доступ."
        )
        await callback.answer()
        return

    text = format_user_courses_list(courses)
    await callback.message.answer(text)
    await callback.answer()
