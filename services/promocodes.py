from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from database import get_session, init_db
from models import PromoCode


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _serialize(promo: PromoCode) -> dict[str, Any]:
    return {
        "id": promo.id,
        "code": promo.code,
        "discount_type": promo.discount_type,
        "value": promo.value,
        "min_order_total": promo.min_order_total,
        "max_uses": promo.max_uses,
        "used_count": promo.used_count,
        "active": bool(promo.active),
        "expires_at": promo.expires_at.isoformat() if promo.expires_at else None,
        "created_at": promo.created_at.isoformat() if promo.created_at else None,
    }


def _apply_updates(promo: PromoCode, data: dict[str, Any]) -> PromoCode:
    if "code" in data:
        promo.code = _normalize_code(str(data["code"]))
    if "discount_type" in data and data["discount_type"]:
        promo.discount_type = str(data["discount_type"]).lower()
    if "value" in data and data["value"] is not None:
        promo.value = int(data["value"])
    if "min_order_total" in data:
        promo.min_order_total = (
            int(data["min_order_total"]) if data["min_order_total"] is not None else None
        )
    if "max_uses" in data:
        promo.max_uses = int(data["max_uses"]) if data["max_uses"] is not None else None
    if "active" in data and data["active"] is not None:
        promo.active = bool(data["active"])
    if "expires_at" in data:
        promo.expires_at = data["expires_at"]
    return promo


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    discount_type = str(data.get("discount_type", "")).lower()
    if discount_type not in {"percent", "fixed"}:
        raise ValueError("discount_type must be 'percent' or 'fixed'")

    try:
        value = int(data.get("value"))
    except (TypeError, ValueError):
        raise ValueError("value must be a positive integer")
    if value <= 0:
        raise ValueError("value must be a positive integer")

    payload: dict[str, Any] = {
        "code": _normalize_code(data.get("code", "")),
        "discount_type": discount_type,
        "value": value,
        "min_order_total": (
            int(data.get("min_order_total")) if data.get("min_order_total") is not None else None
        ),
        "max_uses": int(data.get("max_uses")) if data.get("max_uses") is not None else None,
        "active": bool(data.get("active", True)),
        "expires_at": data.get("expires_at"),
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

        updates = data.copy()
        if any(key in updates for key in {"discount_type", "value", "code", "min_order_total", "max_uses", "active"}):
            validated = _validate_payload({**_serialize(promo), **updates})
            updates.update(validated)
        _apply_updates(promo, updates)
        session.flush()
        session.refresh(promo)
        return _serialize(promo)


def get_promocode(code: str) -> dict | None:
    normalized = _normalize_code(code)
    if not normalized:
        return None

    init_db()
    with get_session() as session:
        promo = session.scalar(select(PromoCode).where(PromoCode.code == normalized))
        return _serialize(promo) if promo else None


def list_promocodes() -> list[dict]:
    init_db()
    with get_session() as session:
        promos = session.scalars(select(PromoCode).order_by(PromoCode.id.desc())).all()
        return [_serialize(promo) for promo in promos]


def _calculate_discount(promo: dict[str, Any], cart_total: int) -> int:
    discount_type = promo.get("discount_type")
    value = int(promo.get("value", 0) or 0)

    amount = 0
    if discount_type == "percent":
        amount = cart_total * value // 100
    elif discount_type == "fixed":
        amount = value

    if amount < 0:
        return 0
    if amount > cart_total:
        return cart_total
    return amount


def validate_promocode(code: str, user_id: int, cart_total: int) -> dict | None:
    promo = get_promocode(code)
    if not promo:
        return None

    if not promo.get("active"):
        return None

    expires_at = promo.get("expires_at")
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(expires_at)
            if datetime.utcnow() > expires_dt:
                return None
        except ValueError:
            return None

    max_uses = promo.get("max_uses")
    if max_uses is not None and max_uses > 0:
        if int(promo.get("used_count") or 0) >= max_uses:
            return None

    min_total = promo.get("min_order_total") or 0
    if min_total and cart_total < min_total:
        return None

    discount_amount = _calculate_discount(promo, cart_total)
    final_total = max(cart_total - discount_amount, 0)

    return {
        "code": promo.get("code"),
        "discount_type": promo.get("discount_type"),
        "value": promo.get("value"),
        "discount_amount": discount_amount,
        "final_total": final_total,
    }


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

