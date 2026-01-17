from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import func, select

from database import get_session
from initdb import init_db
from models import Order, PromoCode


ALLOWED_DISCOUNT_TYPES = {"percent", "fixed"}
ALLOWED_SCOPES = {"all", "basket", "course", "product", "category"}


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError("date_start/date_end must be ISO8601 datetime")


def _parse_expires_at(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
            "%d.%m.%Y %H:%M",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass

        raise ValueError("expires_at has invalid format")

    raise ValueError("expires_at has invalid type")


def _serialize(promo: PromoCode) -> dict[str, Any]:
    return {
        "id": promo.id,
        "code": promo.code,
        "discount_type": promo.discount_type,
        "discount_value": float(promo.discount_value or 0),
        "scope": promo.scope,
        "target_id": promo.target_id,
        "date_start": promo.date_start.isoformat() if promo.date_start else None,
        "date_end": promo.date_end.isoformat() if promo.date_end else None,
        "expires_at": promo.expires_at.isoformat() if promo.expires_at else None,
        "active": bool(promo.active),
        "max_uses": promo.max_uses,
        "used_count": promo.used_count,
        "one_per_user": bool(promo.one_per_user),
        "created_at": promo.created_at.isoformat() if promo.created_at else None,
    }


def _apply_updates(promo: PromoCode, data: dict[str, Any]) -> PromoCode:
    if "code" in data:
        promo.code = _normalize_code(str(data["code"]))
    if "discount_type" in data and data["discount_type"]:
        promo.discount_type = str(data["discount_type"]).lower()
    if "discount_value" in data and data["discount_value"] is not None:
        promo.discount_value = Decimal(str(data["discount_value"]))
    if "scope" in data and data["scope"]:
        promo.scope = str(data["scope"])
    if "target_id" in data:
        promo.target_id = int(data["target_id"]) if data["target_id"] is not None else None
    if "date_start" in data:
        promo.date_start = _parse_date(data.get("date_start"))
    if "date_end" in data:
        promo.date_end = _parse_date(data.get("date_end"))
    if "expires_at" in data:
        promo.expires_at = _parse_expires_at(data["expires_at"])
    if "active" in data and data["active"] is not None:
        promo.active = bool(data["active"])
    if "max_uses" in data:
        promo.max_uses = int(data["max_uses"]) if data["max_uses"] is not None else None
    if "used_count" in data and data["used_count"] is not None:
        promo.used_count = int(data["used_count"])
    if "one_per_user" in data and data["one_per_user"] is not None:
        promo.one_per_user = bool(data["one_per_user"])
    return promo


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    discount_type = str(data.get("discount_type", "")).lower()
    if discount_type not in ALLOWED_DISCOUNT_TYPES:
        raise ValueError("discount_type must be 'percent' or 'fixed'")

    try:
        value = Decimal(str(data.get("discount_value")))
    except (TypeError, ValueError, ArithmeticError):
        raise ValueError("discount_value must be a positive number")
    if value <= 0:
        raise ValueError("discount_value must be a positive number")

    scope = str(data.get("scope", "all")) or "all"
    if scope not in ALLOWED_SCOPES:
        raise ValueError("scope must be one of: all, basket, course, product, category")

    target_id = data.get("target_id")
    if scope in {"product", "category"}:
        if target_id is None:
            raise ValueError("target_id is required for product/category scope")
        try:
            target_id = int(target_id)
        except (TypeError, ValueError):
            raise ValueError("target_id must be integer")
    else:
        target_id = int(target_id) if target_id is not None else None

    date_start = _parse_date(data.get("date_start"))
    date_end = _parse_date(data.get("date_end"))
    expires_at = _parse_expires_at(data.get("expires_at"))
    if date_start and date_end and date_start > date_end:
        raise ValueError("date_start must be before date_end")

    payload: dict[str, Any] = {
        "code": _normalize_code(data.get("code", "")),
        "discount_type": discount_type,
        "discount_value": value,
        "scope": scope,
        "target_id": target_id,
        "date_start": date_start,
        "date_end": date_end,
        "expires_at": expires_at,
        "active": bool(data.get("active", True)),
        "max_uses": int(data.get("max_uses")) if data.get("max_uses") is not None else None,
        "used_count": int(data.get("used_count", 0) or 0),
        "one_per_user": bool(data.get("one_per_user", False)),
    }

    if not payload["code"]:
        raise ValueError("code is required")

    return payload


def create_promocode(data: dict[str, Any]) -> dict:
    payload = _validate_payload(data)
    init_db()
    with get_session() as session:
        existing = session.scalar(select(PromoCode).where(PromoCode.code == payload["code"]))
        if existing:
            raise ValueError("Duplicate promocode")

        promo = PromoCode(**payload)
        session.add(promo)
        session.flush()
        session.refresh(promo)
        return _serialize(promo)


def update_promocode(promo_id: int, data: dict[str, Any]) -> dict | None:
    init_db()
    with get_session() as session:
        promo = session.get(PromoCode, promo_id)
        if not promo:
            return None

        validated = _validate_payload({**_serialize(promo), **data})
        _apply_updates(promo, validated)
        session.flush()
        session.refresh(promo)
        return _serialize(promo)


def delete_promocode(promo_id: int) -> bool:
    init_db()
    with get_session() as session:
        promo = session.get(PromoCode, promo_id)
        if not promo:
            return False
        session.delete(promo)
        return True


def list_promocodes() -> list[dict[str, Any]]:
    init_db()
    with get_session() as session:
        promos = session.scalars(select(PromoCode).order_by(PromoCode.id.desc())).all()
        return [_serialize(promo) for promo in promos]


def _eligible_items(items: Iterable[dict[str, Any]], scope: str, target_id: int | None) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for item in items:
        product_type = item.get("type")
        product_id = item.get("product_id")
        category_id = item.get("category_id")

        if scope == "all":
            eligible.append(item)
        elif scope == "basket" and product_type == "basket":
            eligible.append(item)
        elif scope == "course" and product_type == "course":
            eligible.append(item)
        elif scope == "product" and target_id is not None and int(product_id) == int(target_id):
            eligible.append(item)
        elif scope == "category" and target_id is not None:
            try:
                if int(category_id) == int(target_id) and product_type == "basket":
                    eligible.append(item)
            except (TypeError, ValueError):
                continue
    return eligible


def _calculate_total(items: Iterable[dict[str, Any]]) -> int:
    total = 0
    for item in items:
        total += int(item.get("price", 0)) * int(item.get("qty", 0))
    return total


def _calculate_discount(promo: PromoCode, eligible_items: list[dict[str, Any]]) -> int:
    eligible_total = _calculate_total(eligible_items)
    if eligible_total <= 0:
        return 0

    if promo.discount_type == "percent":
        percent = min(max(int(promo.discount_value), 0), 100)
        amount = eligible_total * percent // 100
    else:
        amount = int(promo.discount_value)

    if amount < 0:
        return 0
    if amount > eligible_total:
        return eligible_total
    return amount


def _check_usage_limits(session, promo: PromoCode, user_id: int | None) -> bool:
    if promo.max_uses is not None and promo.max_uses > 0:
        if int(promo.used_count or 0) >= promo.max_uses:
            return False

    if promo.one_per_user and user_id is not None:
        used_by_user = session.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.user_id == int(user_id), Order.promocode_code == promo.code)
        )
        if used_by_user and int(used_by_user) > 0:
            return False
    return True


def validate_promocode(code: str, user_id: int | None, cart_items: list[dict[str, Any]]) -> dict | None:
    normalized = _normalize_code(code)
    if not normalized or not cart_items:
        return None

    init_db()
    with get_session() as session:
        promo = session.scalar(select(PromoCode).where(PromoCode.code == normalized))
        if not promo or not promo.active:
            return None

        now = datetime.utcnow()
        if promo.date_start and now < promo.date_start:
            return None
        if promo.date_end and now > promo.date_end:
            return None

        if not _check_usage_limits(session, promo, user_id):
            return None

        eligible_items = _eligible_items(cart_items, promo.scope, promo.target_id)
        if not eligible_items:
            return None

        discount_amount = _calculate_discount(promo, eligible_items)
        cart_total = _calculate_total(cart_items)
        final_total = max(cart_total - discount_amount, 0)

        return {
            **_serialize(promo),
            "discount_amount": discount_amount,
            "final_total": final_total,
            "eligible_items": [
                {"product_id": item.get("product_id"), "type": item.get("type")}
                for item in eligible_items
            ],
        }


def apply_promocode_to_cart(cart: list[dict[str, Any]], user_id: int | None, code: str | None = None) -> dict | None:
    resolved_code = code or (cart[0].get("promocode") if cart else None)
    if not resolved_code:
        return None
    return validate_promocode(resolved_code, user_id, cart)


def increment_usage(code: str) -> None:
    normalized = _normalize_code(code)
    if not normalized:
        return
    init_db()
    with get_session() as session:
        promo = session.scalar(select(PromoCode).where(PromoCode.code == normalized))
        if promo:
            promo.used_count = (promo.used_count or 0) + 1


def set_promocode_active(code: str, is_active: bool) -> bool:
    normalized = _normalize_code(code)
    if not normalized:
        return False

    init_db()
    with get_session() as session:
        promo = session.scalar(select(PromoCode).where(PromoCode.code == normalized))
        if not promo:
            return False
        promo.active = bool(is_active)
        return True


def get_promocodes_usage_summary(limit: int = 50) -> list[dict[str, Any]]:
    promos = list_promocodes()
    return promos[:limit]
