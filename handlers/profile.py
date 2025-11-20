from aiogram import Router, types, F
from aiogram.filters import Command

from keyboards.main_menu import PROFILE_BUTTON_TEXT
from services.orders import get_orders_by_user, STATUS_SENT, STATUS_TITLES

router = Router()


def _format_profile_text(user: types.User, orders: list[dict]) -> str:
    """
    Формируем красивый текст профиля и заказов.
    """
    full_name = user.full_name or "Без имени"
    username = f"@{user.username}" if user.username else "—"
    user_id = user.id

    lines: list[str] = [
        "👤 <b>Ваш профиль</b>",
        "",
        f"Имя: <b>{full_name}</b>",
        f"Ник: <b>{username}</b>",
        f"ID: <code>{user_id}</code>",
        "",
    ]

    if not orders:
        lines.append("Пока нет оформленных заказов.")
        return "\n".join(lines)

    active: list[dict] = []
    finished: list[dict] = []

    for o in orders:
        status = o.get("status")
        if status == STATUS_SENT:
            finished.append(o)
        else:
            active.append(o)

    # Актуальные заказы
    lines.append("📦 <b>Актуальные заказы</b>")
    if not active:
        lines.append("— нет активных заказов.")
    else:
        for o in active:
            status = o.get("status")
            status_title = STATUS_TITLES.get(status, status or "")
            lines.append(
                f"\nЗаказ №{o['id']} — <b>{status_title}</b>"
                f"\nСумма: <b>{o['total']} ₽</b>"
                f"\nОформлен: {o['created_at']}"
            )

    # История
    lines.append("\n🗂 <b>История заказов</b>")
    if not finished:
        lines.append("— пока ещё нет завершённых заказов.")
    else:
        for o in finished:
            status = o.get("status")
            status_title = STATUS_TITLES.get(status, status or "")
            lines.append(
                f"\nЗаказ №{o['id']} — <b>{status_title}</b>"
                f"\nСумма: <b>{o['total']} ₽</b>"
                f"\nДата: {o['created_at']}"
            )

    lines.append(
        "\nЕсли хотите уточнить статус или получить доступ к курсам — "
        "просто напишите менеджеру в ответ на сообщение с заказом."
    )

    return "\n".join(lines).strip()


@router.message(Command("profile"))
@router.message(F.text == PROFILE_BUTTON_TEXT)
async def show_profile(message: types.Message) -> None:
    """
    Профиль пользователя:
    - основная информация;
    - активные заказы;
    - история заказов.
    """
    user = message.from_user
    orders = get_orders_by_user(user.id, limit=30)

    text = _format_profile_text(user, orders)
    await message.answer(text)
