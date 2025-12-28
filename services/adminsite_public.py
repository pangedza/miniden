from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_session
from models import AdminSiteCategory, AdminSiteItem
from services import adminsite_pages, theme_service

ALLOWED_TYPES = {"product", "course"}


def normalize_type(value: str | None) -> str | None:
    """Return validated type value or None.

    Raises ValueError for unsupported values to allow API layer to map
    validation errors to HTTP responses without coupling to FastAPI.
    """

    if value is None:
        return None

    candidate = value.strip().lower()
    if candidate and candidate not in ALLOWED_TYPES:
        raise ValueError("Unsupported type value")
    return candidate or None


def _category_query(session: Session, type_value: str | None = None):
    query = select(AdminSiteCategory).where(AdminSiteCategory.is_active.is_(True))
    if type_value:
        query = query.where(AdminSiteCategory.type == type_value)
    return query.order_by(AdminSiteCategory.sort, AdminSiteCategory.id)


def _item_query(
    session: Session, *, type_value: str | None = None, category_id: int | None = None
):
    query = (
        select(AdminSiteItem, AdminSiteCategory)
        .join(AdminSiteCategory, AdminSiteItem.category_id == AdminSiteCategory.id)
        .where(AdminSiteItem.is_active.is_(True))
        .where(AdminSiteCategory.is_active.is_(True))
    )

    if type_value:
        query = query.where(AdminSiteItem.type == type_value)
    if category_id:
        query = query.where(AdminSiteItem.category_id == category_id)

    return query.order_by(AdminSiteItem.sort, AdminSiteItem.id)


def _serialize_category(category: AdminSiteCategory) -> dict[str, Any]:
    return {
        "id": int(category.id),
        "type": category.type,
        "title": category.title,
        "slug": category.slug,
        "parent_id": category.parent_id,
        "is_active": bool(category.is_active),
        "sort": category.sort or 0,
        "created_at": category.created_at,
        "url": f"/c/{category.slug}",
    }


def _serialize_item(
    item: AdminSiteItem, *, category: AdminSiteCategory | None = None
) -> dict[str, Any]:
    target_category = category
    if target_category is None:
        target_category = item.category  # type: ignore[attr-defined]

    item_url = f"/p/{item.slug}" if item.type == "product" else f"/m/{item.slug}"

    return {
        "id": int(item.id),
        "type": item.type,
        "category_id": item.category_id,
        "category_slug": getattr(target_category, "slug", None),
        "category_title": getattr(target_category, "title", None),
        "title": item.title,
        "slug": item.slug,
        "price": float(item.price or 0),
        "image_url": item.image_url,
        "short_text": item.short_text,
        "description": item.description,
        "is_active": bool(item.is_active),
        "sort": item.sort or 0,
        "created_at": item.created_at,
        "url": item_url,
    }


def list_menu(type_value: str | None = "product") -> list[dict[str, Any]]:
    normalized = normalize_type(type_value) or "product"
    with get_session() as session:
        categories = session.execute(_category_query(session, normalized)).scalars().all()
    return [_serialize_category(item) for item in categories]


def list_categories(type_value: str | None = None) -> list[dict[str, Any]]:
    normalized = normalize_type(type_value)
    with get_session() as session:
        categories = session.execute(_category_query(session, normalized)).scalars().all()
    return [_serialize_category(item) for item in categories]


def _load_category(
    session: Session, slug: str, *, type_value: str | None
) -> AdminSiteCategory | None:
    normalized_slug = (slug or "").strip().lower()
    if not normalized_slug:
        return None

    query = _category_query(session, type_value).where(
        func.lower(AdminSiteCategory.slug) == normalized_slug
    )
    categories = session.execute(query).scalars().all()

    if not categories:
        return None

    if type_value is None and len({item.type for item in categories}) > 1:
        raise ValueError("Slug is not unique across types, specify type")

    return categories[0]


def get_category_with_items(
    slug: str, *, type_value: str | None = None
) -> dict[str, Any] | None:
    normalized_type = normalize_type(type_value)
    with get_session() as session:
        category = _load_category(session, slug, type_value=normalized_type)
        if not category:
            return None

        items = (
            session.execute(
                _item_query(session, type_value=normalized_type, category_id=category.id)
            )
            .all()
        )

    serialized_items: list[dict[str, Any]] = []
    for item, linked_category in items:
        serialized_items.append(_serialize_item(item, category=linked_category))

    return {"category": _serialize_category(category), "items": serialized_items}


def list_items(
    *, type_value: str | None = None, category_id: int | None = None
) -> list[dict[str, Any]]:
    normalized_type = normalize_type(type_value)
    with get_session() as session:
        rows = (
            session.execute(
                _item_query(
                    session, type_value=normalized_type, category_id=category_id
                )
            )
            .all()
        )

    return [_serialize_item(item, category=category) for item, category in rows]


def get_item_by_slug(slug: str, *, type_value: str) -> dict[str, Any] | None:
    normalized_type = normalize_type(type_value)
    if not normalized_type:
        raise ValueError("type is required")

    normalized_slug = (slug or "").strip()
    if not normalized_slug:
        return None

    with get_session() as session:
        query = _item_query(session, type_value=normalized_type).where(
            AdminSiteItem.slug == normalized_slug
        )
        result = session.execute(query.limit(1)).first()
        if not result:
            return None

        item, category = result
        return _serialize_item(item, category=category)


def _load_items(session: Session, *, type_value: str, limit: int = 6):
    return (
        session.execute(_item_query(session, type_value=type_value).limit(limit)).all()
    )


def _extract_page_meta(page: dict[str, Any]) -> dict[str, Any]:
    blocks = page.get("blocks") or []
    template_id = (
        page.get("templateId")
        or page.get("template_id")
        or adminsite_pages.DEFAULT_TEMPLATE_ID
    )
    version = page.get("version") or page.get("updatedAt") or page.get("updated_at")
    if not version:
        version = datetime.utcnow().isoformat()

    updated_at = page.get("updatedAt") or page.get("updated_at") or version
    block_types = [block.get("type", "unknown") for block in blocks if isinstance(block, dict)]

    return {
        "template_id": template_id,
        "version": version,
        "updated_at": updated_at,
        "blocks": blocks,
        "blocks_count": len(blocks),
        "block_types": block_types,
    }


def get_home_summary(limit: int = 6) -> dict[str, Any]:
    page = adminsite_pages.get_page()
    meta = _extract_page_meta(page)
    theme_meta = theme_service.get_theme_metadata()
    with get_session() as session:
        categories_product = session.execute(
            _category_query(session, "product")
        ).scalars().all()
        categories_course = session.execute(
            _category_query(session, "course")
        ).scalars().all()

        products = _load_items(session, type_value="product", limit=limit)
        masterclasses = _load_items(session, type_value="course", limit=limit)

    return {
        "page": page,
        "templateId": meta["template_id"],
        "template_id": meta["template_id"],
        "version": meta["version"],
        "updatedAt": meta["updated_at"],
        "updated_at": meta["updated_at"],
        "blocksCount": meta["blocks_count"],
        "blockTypes": meta["block_types"],
        "product_categories": [_serialize_category(item) for item in categories_product],
        "course_categories": [_serialize_category(item) for item in categories_course],
        "featured_products": [_serialize_item(item, category=category) for item, category in products],
        "featured_masterclasses": [
            _serialize_item(item, category=category) for item, category in masterclasses
        ],
        "theme": theme_meta,
        "themeVersion": theme_meta.get("timestamp"),
    }
