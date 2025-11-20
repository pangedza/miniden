from typing import Iterable
from services import orders as orders_service


def format_stats_summary(title: str, summary: dict) -> str:
    lines: list[str] = [f"📊 <b>{title}</b>", ""]

    total_orders = int(summary.get("total_orders", 0) or 0)
    total_amount = int(summary.get("total_amount", 0) or 0)
    lines.append(f"Всего заказов: <b>{total_orders}</b>")
    lines.append(f"Общая сумма: <b>{total_amount} ₽</b>")

    status_order = [
        (orders_service.STATUS_NEW, "🆕 Новые"),
        (orders_service.STATUS_IN_PROGRESS, "🕒 В работе"),
        (orders_service.STATUS_PAID, "✅ Оплаченные"),
        (orders_service.STATUS_SENT, "📤 Отправленные"),
        (orders_service.STATUS_ARCHIVED, "📁 Архив"),
    ]

    by_status = summary.get("by_status", {}) or {}
    lines.append("")
    lines.append("По статусам:")
    for status, title_text in status_order:
        count = int(by_status.get(status, 0) or 0)
        lines.append(f"{title_text}: {count}")

    return "\n".join(lines).strip()


def format_stats_by_day(items: list[dict]) -> str:
    lines: list[str] = ["📅 <b>Статистика по дням</b>", ""]

    if not items:
        lines.append("Нет заказов за выбранный период.")
        return "\n".join(lines).strip()

    for item in items:
        date = item.get("date", "—")
        orders_count = int(item.get("orders_count", 0) or 0)
        total_amount = int(item.get("total_amount", 0) or 0)
        lines.append(f"{date} — заказы: {orders_count}, сумма: {total_amount} ₽")

    return "\n".join(lines).strip()


def format_top_products(title: str, items: list[dict]) -> str:
    lines: list[str] = [f"🏆 <b>{title}</b>", ""]

    if not items:
        lines.append("Нет данных по топу.")
        return "\n".join(lines).strip()

    for idx, item in enumerate(items, start=1):
        name = item.get("name") or "—"
        total_qty = int(item.get("total_qty", 0) or 0)
        total_amount = int(item.get("total_amount", 0) or 0)
        lines.append(f"{idx}) {name} — {total_qty} шт, {total_amount} ₽")

    return "\n".join(lines).strip()


def format_user_notes(notes: list[dict], empty_placeholder: str = "Заметок пока нет.") -> str:
    """Форматировать список заметок по клиенту для админов."""

    lines: list[str] = ["📝 <b>Заметки по клиенту</b>"]
    if not notes:
        lines.append(empty_placeholder)
        return "\n".join(lines).strip()

    for note in notes:
        created_at = note.get("created_at") or "—"
        admin_id = note.get("admin_id")
        text = note.get("note", "")
        lines.append(f"• [{created_at}] (admin_id={admin_id}): {text}")

    return "\n".join(lines).strip()


def format_basket_list(baskets: Iterable[dict]) -> str:
    lines: list[str] = ["🧺 <b>Наши корзинки</b>:\n"]
    for item in baskets:
        lines.append(
            f"• <b>{item.get('name')}</b> — {item.get('price')} ₽\n"
            f"{item.get('description', '').strip()}"
        )
        url = item.get("detail_url")
        if url:
            lines.append(f"Подробнее: {url}")
        lines.append("")

    return "\n".join(lines).strip()


def format_course_list(courses: Iterable[dict]) -> str:
    lines: list[str] = ["🎓 <b>Наши онлайн-курсы</b>:\n"]
    for item in courses:
        lines.append(
            f"• <b>{item.get('name')}</b> — {item.get('price')} ₽\n"
            f"{item.get('description', '').strip()}"
        )
        url = item.get("detail_url")
        if url:
            lines.append(f"Подробнее: {url}")
        lines.append("")

    return "\n".join(lines).strip()


def format_cart(items: Iterable[dict]) -> str:
    """Форматирование корзины для вывода пользователю."""
    items = list(items)
    if not items:
        return "🛒 Ваша корзина пока пуста."

    lines: list[str] = ["🛒 <b>Ваша корзина</b>:\n"]
    total = 0

    for item in items:
        name = item.get("name", "Товар")
        price = int(item.get("price", 0))
        qty = int(item.get("qty", 0))
        subtotal = price * qty
        total += subtotal

        lines.append(
            f"• <b>{name}</b> — {price} ₽ x {qty} = {subtotal} ₽"
        )

    lines.append("")
    lines.append(f"Итого: <b>{total} ₽</b>")
    return "\n".join(lines).strip()


def format_order_for_admin(
    user_id: int,
    user_name: str,
    items: Iterable[dict],
    total: int,
    customer_name: str,
    contact: str,
    comment: str,
) -> str:
    """Сформировать текст заказа для администратора."""
    lines: list[str] = []

    lines.append("🆕 <b>Новый заказ</b>")
    lines.append("")
    lines.append(f"👤 Клиент: {customer_name}")
    lines.append(f"📞 Контакт: {contact}")
    if comment:
        lines.append(f"💬 Комментарий: {comment}")
    lines.append("")
    lines.append(f"🧑‍💻 Telegram: id={user_id}, имя={user_name}")
    lines.append("")

    # Корзина
    lines.append("🛒 <b>Корзина:</b>")
    total_check = 0
    for item in items:
        name = item.get("name", "Товар")
        price = int(item.get("price", 0))
        qty = int(item.get("qty", 0))
        subtotal = price * qty
        total_check += subtotal
        lines.append(f"• {name} — {price} ₽ x {qty} = {subtotal} ₽")

    lines.append("")
    lines.append(f"Итого к оплате: <b>{total} ₽</b>")
    if total_check != total:
        lines.append(f"(пересчёт по позициям: {total_check} ₽)")

    return "\n".join(lines).strip()


def format_orders_list_text(order_list: list[dict], show_client_hint: bool = False) -> str:
    """
    Форматирование списка заказов для команды /orders.
    Показываем: №, статус, сумма, имя, контакт.
    """
    if not order_list:
        return "Пока нет заказов."

    lines: list[str] = ["📦 <b>Последние заказы:</b>"]

    for order in order_list:
        status = order.get("status", orders_service.STATUS_NEW)
        status_title = orders_service.STATUS_TITLES.get(status, status)
        user_name = order.get("user_name") or "—"
        user_id = order.get("user_id") or "—"

        lines.append(
            f"\nЗаказ №{order['id']} — {status_title}"
            f"\n👤 Клиент: {order['customer_name']}"
            f"\n🧑‍💻 Telegram: id=<code>{user_id}</code>, имя={user_name}"
            f"\n📞 Контакт: {order['contact']}"
            f"\n💰 Сумма: <b>{order['total']} ₽</b>"
            f"\n🕒 Время: {order.get('created_at', '—')}"
        )

    if show_client_hint:
        lines.append(
            "\nЧтобы открыть профиль клиента, отправьте:"
            " <code>/client &lt;telegram_id&gt;</code>"
        )

    return "\n".join(lines).strip()


def format_user_courses_list(courses: list[dict]) -> str:
    """Форматированный список курсов пользователя."""
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

    return "\n".join(lines).strip()


def format_order_detail_text(order: dict) -> str:
    """
    Форматирование одного заказа для команды /order <id>.
    Показываем все позиции.
    """
    status = order.get("status", orders_service.STATUS_NEW)
    status_title = orders_service.STATUS_TITLES.get(status, status)
    user_name = order.get("user_name") or "—"
    user_id = order.get("user_id") or "—"

    lines: list[str] = [
        f"📦 <b>Заказ №{order['id']}</b>",
        f"Статус: <b>{status_title}</b>",
        f"🧑‍💻 Telegram: id=<code>{user_id}</code>, имя={user_name}",
        "",
        f"👤 Имя: {order['customer_name']}",
        f"📞 Контакт: {order['contact']}",
    ]

    comment = order.get("comment")
    if comment:
        lines.append(f"💬 Комментарий: {comment}")

    lines.append("\n🧺 <b>Состав заказа:</b>")

    items = order.get("items") or []
    if not items:
        lines.append("— (пусто, похоже что-то пошло не так)")
    else:
        for item in items:
            name = item.get("name", "Товар")
            price = int(item.get("price", 0))
            qty = int(item.get("qty", 0))
            subtotal = price * qty
            lines.append(f"• {name} — {qty} x {price} ₽ = {subtotal} ₽")

    total = order.get("total", 0)
    lines.append(f"\n💰 <b>Итого: {total} ₽</b>")

    return "\n".join(lines).strip()


def format_admin_client_profile(
    user_id: int,
    user_stats: dict,
    courses_summary: dict,
    ban_status: dict | None = None,
    notes: list[dict] | None = None,
    notes_limit: int = 10,
) -> str:
    """Сформировать HTML-профиль клиента для администратора."""

    lines: list[str] = []

    lines.append("👤 <b>Профиль клиента</b>")
    lines.append("")

    ban = ban_status or {}
    if ban.get("is_banned"):
        lines.append("🚫 <b>Пользователь забанен</b>")
        reason = ban.get("ban_reason")
        if reason:
            lines.append(f"Причина: {reason}")
        updated_at = ban.get("updated_at")
        if updated_at:
            lines.append(f"Обновлено: {updated_at}")
    else:
        lines.append("✅ Пользователь активен")

    lines.append("")
    lines.append(f"🧑‍💻 Telegram: id=<code>{user_id}</code>")

    lines.append("")
    lines.append("📊 <b>Статистика заказов</b>")
    total_orders = user_stats.get("total_orders", 0)
    total_amount = user_stats.get("total_amount", 0)
    orders_by_status = user_stats.get("orders_by_status", {}) or {}

    lines.append(f"Всего заказов: <b>{total_orders}</b>")
    lines.append(f"Сумма всех заказов: <b>{total_amount} ₽</b>")

    status_lines = {
        orders_service.STATUS_NEW: "🆕 Новые",
        orders_service.STATUS_IN_PROGRESS: "🕒 В работе",
        orders_service.STATUS_PAID: "✅ Оплаченные",
        orders_service.STATUS_SENT: "📤 Отправленные",
        orders_service.STATUS_ARCHIVED: "📁 Архив",
    }

    for status, title in status_lines.items():
        count = int(orders_by_status.get(status, 0) or 0)
        if count > 0:
            lines.append(f"{title}: {count}")

    last_order_id = user_stats.get("last_order_id")
    last_order_created_at = user_stats.get("last_order_created_at")
    if last_order_id and last_order_created_at:
        lines.append(f"Последний заказ: №{last_order_id} от {last_order_created_at}")

    lines.append("")
    lines.append("🎓 <b>Курсы с доступом</b>")
    courses_count = courses_summary.get("count", 0)
    courses = courses_summary.get("courses") or []
    lines.append(f"Всего: <b>{courses_count}</b>")

    if courses:
        lines.append("")
        for idx, course in enumerate(courses, start=1):
            name = course.get("name", "Курс")
            detail_url = course.get("detail_url")

            lines.append(f"{idx}. <b>{name}</b>")
            if detail_url:
                lines.append(str(detail_url))

    lines.append("")

    limited_notes = (notes or [])[:notes_limit]
    lines.append(format_user_notes(limited_notes))

    return "\n".join(lines).strip()
