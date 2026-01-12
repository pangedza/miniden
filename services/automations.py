from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models import BotAutomationRule, BotButtonPreset

TRIGGER_WEBAPP_ORDER = "WEBAPP_ORDER_RECEIVED"

ACTION_SAVE_ORDER = "SAVE_ORDER"
ACTION_SEND_USER_MESSAGE = "SEND_USER_MESSAGE"
ACTION_SEND_ADMIN_MESSAGE = "SEND_ADMIN_MESSAGE"
ACTION_ATTACH_BUTTONS = "ATTACH_BUTTONS"

TRIGGER_LABELS = {
    TRIGGER_WEBAPP_ORDER: "Пришёл заказ из WebApp",
}

ACTION_LABELS = {
    ACTION_SAVE_ORDER: "Сохранить заказ",
    ACTION_SEND_USER_MESSAGE: "Отправить сообщение пользователю",
    ACTION_SEND_ADMIN_MESSAGE: "Отправить сообщение админу",
    ACTION_ATTACH_BUTTONS: "Прикрепить набор кнопок",
}

BUTTON_SCOPES = {
    "user": "Пользователь",
    "admin": "Админ",
}

TEMPLATE_VARIABLES = [
    {"key": "order_id", "label": "Номер заказа", "sample": "1024"},
    {"key": "total", "label": "Сумма заказа", "sample": "3250"},
    {"key": "items", "label": "Список товаров", "sample": "• Букет x1 = 1200 ₽"},
    {"key": "user_name", "label": "Имя пользователя", "sample": "Анна"},
    {"key": "user_id", "label": "ID пользователя", "sample": "123456789"},
    {"key": "phone", "label": "Телефон", "sample": "+7 999 123-45-67"},
    {"key": "comment", "label": "Комментарий", "sample": "Позвонить за час"},
]

ITEM_FIELDS = [
    {"key": "title", "label": "Название"},
    {"key": "qty", "label": "Кол-во"},
    {"key": "price", "label": "Цена"},
    {"key": "sum", "label": "Итого"},
]


def list_active_rules(
    session: Session, *, trigger_type: str
) -> list[BotAutomationRule]:
    return (
        session.query(BotAutomationRule)
        .filter(BotAutomationRule.trigger_type == trigger_type)
        .filter(BotAutomationRule.is_enabled.is_(True))
        .order_by(BotAutomationRule.id.asc())
        .all()
    )


def list_active_presets(session: Session) -> list[BotButtonPreset]:
    return (
        session.query(BotButtonPreset)
        .filter(BotButtonPreset.is_enabled.is_(True))
        .order_by(BotButtonPreset.scope.asc(), BotButtonPreset.id.asc())
        .all()
    )


def build_keyboard_from_buttons(
    buttons: list[dict[str, Any]] | None,
    *,
    webapp_url: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not buttons:
        return None

    rows: dict[int, list[dict[str, str]]] = {}
    for button in buttons:
        title = str(button.get("title") or "").strip()
        if not title:
            continue
        button_type = (button.get("type") or "").strip().lower()
        value = str(button.get("value") or "").strip()
        value = value.replace("{webapp_url}", webapp_url)
        if context:
            for key, raw_value in context.items():
                value = value.replace(f"{{{key}}}", str(raw_value or ""))
        if not value:
            continue
        row_index = int(button.get("row") or 0)
        payload: dict[str, str]
        if button_type == "url":
            payload = {"text": title, "url": value}
        else:
            payload = {"text": title, "callback_data": value}
        rows.setdefault(row_index, []).append(payload)

    inline_keyboard = [rows[row] for row in sorted(rows.keys()) if rows[row]]
    if not inline_keyboard:
        return None
    return {"inline_keyboard": inline_keyboard}


def build_items_text(
    items: list[dict[str, Any]], currency: str, fields: list[str]
) -> str:
    lines: list[str] = []
    selected = set(fields or [])
    for item in items:
        title = str(item.get("title") or item.get("name") or "Позиция")
        qty = int(item.get("qty") or 0)
        price = int(item.get("price") or 0)
        line_total = price * qty
        parts: list[str] = []
        if "title" in selected:
            parts.append(title)
        if "qty" in selected:
            parts.append(f"x{qty}")
        if "price" in selected:
            parts.append(f"{price} {currency}")
        if "sum" in selected:
            parts.append(f"= {line_total} {currency}")
        if parts:
            lines.append(f"• {' '.join(parts)}")
    return "\n".join(lines)


def _safe_format(template: str, context: dict[str, Any]) -> str:
    result = template or ""
    for key, value in context.items():
        result = result.replace(f"{{{key}}}", str(value or ""))
    return result


def render_message(
    template: dict[str, Any] | None,
    *,
    context: dict[str, Any],
    items: list[dict[str, Any]],
    currency: str,
) -> str:
    payload = template or {}
    title = _safe_format(str(payload.get("title") or ""), context).strip()
    body = _safe_format(str(payload.get("body") or ""), context).strip()
    items_enabled = bool(payload.get("items_enabled"))
    items_fields = payload.get("items_fields") or []
    items_title = str(payload.get("items_title") or "Состав заказа").strip()

    parts: list[str] = []
    if title:
        parts.append(title)
    if body:
        parts.append(body)
    if items_enabled and items_fields:
        items_text = build_items_text(items, currency, list(items_fields))
        if items_text:
            if items_title:
                parts.append(f"{items_title}:\n{items_text}")
            else:
                parts.append(items_text)

    return "\n\n".join(part for part in parts if part).strip()
