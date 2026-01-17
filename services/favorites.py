from __future__ import annotations

from datetime import datetime
from typing import Any, List

from sqlalchemy import delete, select

from database import get_session
from initdb import init_db
from models import Favorite
from services import menu_catalog


ALLOWED_TYPES = {"basket", "course", "product", "service", "masterclass"}


def _validate_type(product_type: str) -> str:
    if product_type not in ALLOWED_TYPES:
        raise ValueError("product_type must be 'basket', 'course', 'product', or 'service'")
    return product_type


def add_favorite(user_id: int, product_id: int, product_type: str) -> bool:
    init_db()
    _validate_type(product_type)
    with get_session() as session:
        exists = session.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.product_id == product_id,
                Favorite.type == product_type,
            )
        )
        if exists:
            return False

        favorite = Favorite(
            user_id=user_id,
            product_id=product_id,
            type=product_type,
            created_at=datetime.utcnow(),
        )
        session.add(favorite)
        return True


def remove_favorite(user_id: int, product_id: int, product_type: str) -> bool:
    _validate_type(product_type)
    init_db()
    with get_session() as session:
        result = session.execute(
            delete(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.product_id == product_id,
                Favorite.type == product_type,
            )
        )
        return result.rowcount > 0


def _serialize_favorite(row: Favorite) -> dict[str, Any]:
    resolved_type = menu_catalog.map_legacy_item_type(row.type) or "product"
    product = menu_catalog.get_item_by_id(
        int(row.product_id),
        include_inactive=True,
        item_type=resolved_type,
    )

    name = (product or {}).get("title") if isinstance(product, dict) else None
    if not name and isinstance(product, dict):
        name = product.get("name")

    return {
        "product_id": int(row.product_id),
        "type": resolved_type,
        "name": name,
        "price": int((product or {}).get("price") or 0),
        "is_active": bool((product or {}).get("is_active", 0)),
    }


def list_favorites(user_id: int) -> List[dict[str, Any]]:
    init_db()
    with get_session() as session:
        rows = session.scalars(
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        ).all()
        return [_serialize_favorite(row) for row in rows]


def is_favorite(user_id: int, product_id: int, product_type: str) -> bool:
    _validate_type(product_type)
    init_db()
    with get_session() as session:
        row = session.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.product_id == product_id,
                Favorite.type == product_type,
            )
        )
        return row is not None
