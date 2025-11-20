from typing import Iterable
from services import orders as orders_service


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


def format_orders_list_text(order_list: list[dict]) -> str:
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

        lines.append(
            f"\n<b>Заказ №{order['id']}</b> — {status_title}"
            f"\n👤 {order['customer_name']}"
            f"\n📞 {order['contact']}"
            f"\n💰 Сумма: <b>{order['total']} ₽</b>"
        )

    return "\n".join(lines).strip()


def format_order_detail_text(order: dict) -> str:
    """
    Форматирование одного заказа для команды /order <id>.
    Показываем все позиции.
    """
    status = order.get("status", orders_service.STATUS_NEW)
    status_title = orders_service.STATUS_TITLES.get(status, status)

    lines: list[str] = [
        f"📦 <b>Заказ №{order['id']}</b>",
        f"Статус: <b>{status_title}</b>",
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
