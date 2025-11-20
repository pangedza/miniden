from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.main_menu import PROFILE_BUTTON_TEXT
from services import orders as orders_service
from utils.texts import format_orders_list_text

router = Router()

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


def _format_profile_text(user: types.User, orders: list[dict], courses_cnt: int) -> str:
    full_name = user.full_name or "—"
    username = f"@{user.username}" if user.username else "—"
    user_id = user.id

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
        f"Всего заказов: <b>{total_orders}</b>",
        f"Активные: <b>{active_cnt}</b>",
        f"Завершённые: <b>{finished_cnt}</b>",
        f"Курсов с доступом: <b>{courses_cnt}</b>",
    ]

    return "\n".join(lines)


@router.message(Command("profile"))
@router.message(F.text == PROFILE_BUTTON_TEXT)
async def show_profile(message: types.Message) -> None:
    user = message.from_user
    orders = orders_service.get_orders_by_user(user.id, limit=50)
    courses = orders_service.get_user_courses_with_access(user.id)

    active_cnt = len([o for o in orders if o.get("status") in ACTIVE_STATUSES])
    finished_cnt = len([o for o in orders if o.get("status") in FINISHED_STATUSES])
    courses_cnt = len(courses)

    text = _format_profile_text(user, orders, courses_cnt)
    await message.answer(
        text,
        reply_markup=_build_profile_keyboard(active_cnt, finished_cnt, courses_cnt),
    )


@router.callback_query(F.data == "profile:orders:active")
async def profile_orders_active(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    orders = orders_service.get_orders_by_user(user_id, limit=50)
    active_orders = [o for o in orders if o.get("status") in ACTIVE_STATUSES]

    text = format_orders_list_text(active_orders)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "profile:orders:finished")
async def profile_orders_finished(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    orders = orders_service.get_orders_by_user(user_id, limit=50)
    finished_orders = [o for o in orders if o.get("status") in FINISHED_STATUSES]

    text = format_orders_list_text(finished_orders)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "profile:courses")
async def profile_courses(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    courses = orders_service.get_user_courses_with_access(user_id)

    if not courses:
        await callback.message.answer("Пока нет доступных курсов. Оплатите заказ с курсом, чтобы открыть доступ.")
        await callback.answer()
        return

    lines: list[str] = ["🎓 <b>Мои курсы</b>:\n"]
    for idx, course in enumerate(courses, start=1):
        name = course.get("name", "Курс")
        desc = (course.get("description") or "").strip()
        url = course.get("detail_url")

        lines.append(f"{idx}. <b>{name}</b>")
        if desc:
            lines.append(desc)
        if url:
            lines.append(f"Ссылка: {url}")
        lines.append("")

    await callback.message.answer("\n".join(lines).strip())
    await callback.answer()
