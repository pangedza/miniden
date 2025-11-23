from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from database import get_session, init_db
from models import Promocode


def normalize_code(code: str) -> str:
    """Привести код к единообразному виду: обрезать и сделать верхний регистр."""

    normalized = " ".join((code or "").strip().split())
    return normalized.upper()


def _serialize(promo: Promocode | None) -> dict[str, Any]:
    if not promo:
        return {}
    return {
        "id": promo.id,
        "code": promo.code,
        "discount_type": promo.discount_type,
        "discount_value": int(promo.discount_value or 0),
        "min_order_total": int(promo.min_order_total or 0),
        "max_uses": int(promo.max_uses or 0),
        "used_count": int(promo.used_count or 0),
        "is_active": int(promo.is_active or 0),
        "valid_from": promo.valid_from,
        "valid_to": promo.valid_to,
        "description": promo.description,
    }


def create_promocode(
    code: str,
    discount_type: str,
    discount_value: int,
    min_order_total: int = 0,
    max_uses: int = 0,
    valid_from: str | None = None,
    valid_to: str | None = None,
    description: str | None = None,
) -> int:
    """Создать промокод и вернуть его id. Возвращает -1 при дублировании кода."""

    discount_type = (discount_type or "").strip().lower()
    if discount_type not in {"percent", "fixed"}:
        raise ValueError("discount_type должен быть 'percent' или 'fixed'")

    if discount_value is None or int(discount_value) <= 0:
        raise ValueError("discount_value должен быть больше 0")

    code_norm = normalize_code(code)

    init_db()
    with get_session() as session:
        existing = session.scalar(select(Promocode).where(Promocode.code == code_norm))
        if existing:
            return -1

        promo = Promocode(
            code=code_norm,
            discount_type=discount_type,
            discount_value=int(discount_value),
            min_order_total=int(min_order_total or 0),
            max_uses=int(max_uses or 0),
            valid_from=valid_from,
            valid_to=valid_to,
            description=description,
        )
        session.add(promo)
        session.flush()
        return int(promo.id)


def update_promocode(
    promo_id: int,
    *,
    discount_type: str | None = None,
    discount_value: int | None = None,
    min_order_total: int | None = None,
    max_uses: int | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    description: str | None = None,
    is_active: int | None = None,
) -> bool:
    init_db()
    with get_session() as session:
        promo = session.get(Promocode, promo_id)
        if not promo:
            return False

        if discount_type:
            promo.discount_type = discount_type
        if discount_value is not None:
            promo.discount_value = int(discount_value)
        if min_order_total is not None:
            promo.min_order_total = int(min_order_total)
        if max_uses is not None:
            promo.max_uses = int(max_uses)
        if valid_from is not None:
            promo.valid_from = valid_from
        if valid_to is not None:
            promo.valid_to = valid_to
        if description is not None:
            promo.description = description
        if is_active is not None:
            promo.is_active = 1 if is_active else 0
        return True


def get_promocode_by_code(code: str) -> dict | None:
    code_norm = normalize_code(code)
    if not code_norm:
        return None

    init_db()
    with get_session() as session:
        promo = session.scalar(select(Promocode).where(Promocode.code == code_norm))
        return _serialize(promo) if promo else None


def get_promocode_by_id(promo_id: int) -> dict | None:
    init_db()
    with get_session() as session:
        promo = session.get(Promocode, promo_id)
        return _serialize(promo) if promo else None


def list_promocodes(limit: int = 50) -> list[dict]:
    if limit <= 0:
        return []

    init_db()
    with get_session() as session:
        rows = session.scalars(select(Promocode).order_by(Promocode.id.desc()).limit(limit)).all()
        return [_serialize(row) for row in rows]


def set_promocode_active(code: str, is_active: bool) -> bool:
    code_norm = normalize_code(code)
    init_db()
    with get_session() as session:
        promo = session.scalar(select(Promocode).where(Promocode.code == code_norm))
        if not promo:
            return False
        promo.is_active = 1 if is_active else 0
        return True


def increment_promocode_usage(code: str) -> None:
    code_norm = normalize_code(code)
    init_db()
    with get_session() as session:
        promo = session.scalar(select(Promocode).where(Promocode.code == code_norm))
        if promo:
            promo.used_count = int(promo.used_count or 0) + 1


def validate_promocode_for_order(
    promo: dict, order_total: int, now: datetime | None = None
) -> tuple[bool, str | None]:
    now = now or datetime.now()

    if not promo:
        return False, "Промокод не найден"

    if int(promo.get("is_active", 0)) != 1:
        return False, "Промокод неактивен"

    valid_from = promo.get("valid_from")
    if valid_from:
        try:
            starts_at = datetime.fromisoformat(valid_from)
            if now < starts_at:
                return False, "Промокод ещё не активен"
        except ValueError:
            pass

    valid_to = promo.get("valid_to")
    if valid_to:
        try:
            ends_at = datetime.fromisoformat(valid_to)
            if now > ends_at:
                return False, "Промокод истёк"
        except ValueError:
            pass

    max_uses = int(promo.get("max_uses", 0) or 0)
    used_count = int(promo.get("used_count", 0) or 0)
    if max_uses > 0 and used_count >= max_uses:
        return False, "Лимит использований исчерпан"

    min_order_total = int(promo.get("min_order_total", 0) or 0)
    if min_order_total > 0 and order_total < min_order_total:
        return False, f"Минимальная сумма заказа {min_order_total} ₽"

    return True, None


def calculate_discount_amount(promo: dict, order_total: int) -> int:
    if not promo:
        return 0

    discount_type = promo.get("discount_type")
    discount_value = int(promo.get("discount_value", 0) or 0)
    amount = 0

    if discount_type == "percent":
        amount = order_total * discount_value // 100
    elif discount_type == "fixed":
        amount = discount_value

    if amount < 0:
        amount = 0

    if amount > order_total:
        amount = order_total

    return amount


def get_promocodes_usage_summary(limit: int = 50) -> list[dict]:
    if limit <= 0:
        return []

    init_db()
    with get_session() as session:
        result = session.execute(
            select(
                Promocode.code,
                Promocode.discount_type,
                Promocode.discount_value,
                Promocode.used_count,
                Promocode.max_uses,
                Promocode.is_active,
            ).order_by(Promocode.id.desc()).limit(limit)
        )

        summary: list[dict[str, Any]] = []
        for row in result.all():
            summary.append(
                {
                    "code": row[0],
                    "discount_type": row[1],
                    "discount_value": int(row[2] or 0),
                    "used_count": int(row[3] or 0),
                    "max_uses": int(row[4] or 0),
                    "is_active": int(row[5] or 0),
                }
            )
        return summary
