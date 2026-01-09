from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_session
from models import MenuCategory, MenuItem, SiteBlock, SiteSettings

MENU_ITEM_TYPES = {"product", "course", "service", "masterclass"}
BLOCK_PAGES = {"home", "category", "footer", "custom"}
BLOCK_TYPES = {"banner", "text", "cta", "gallery", "features"}


def normalize_menu_type(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip().lower()
    if candidate and candidate not in MENU_ITEM_TYPES:
        raise ValueError("Unsupported menu item type")
    if candidate == "masterclass":
        return "masterclass"
    return candidate or None


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug


def generate_unique_slug(
    session: Session,
    model,
    slug_base: str,
    filters: list,
    exclude_id: int | None = None,
) -> str:
    slug = slug_base
    counter = 2
    while True:
        query = session.query(model.id).filter(model.slug == slug, *filters)
        if exclude_id:
            query = query.filter(model.id != exclude_id)
        exists = session.query(query.exists()).scalar()
        if not exists:
            return slug
        slug = f"{slug_base}-{counter}"
        counter += 1


def normalize_slug(value: str | None, *, title: str) -> str:
    base = (value or "").strip() or title
    slug = slugify(base)
    if not slug:
        raise ValueError("Slug cannot be empty")
    return slug


def normalize_media_path(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.startswith("/media/"):
        return raw
    if raw.startswith("media/"):
        return f"/{raw}"
    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.path.startswith("/media/"):
            return parsed.path
    return raw


def _category_query(session: Session, *, include_inactive: bool) -> Any:
    query = session.query(MenuCategory)
    if not include_inactive:
        query = query.filter(MenuCategory.is_active.is_(True))
    return query.order_by(MenuCategory.order_index, MenuCategory.id)


def _item_query(
    session: Session,
    *,
    include_inactive: bool,
    category_id: int | None = None,
    item_type: str | None = None,
) -> Any:
    query = session.query(MenuItem, MenuCategory).join(MenuCategory)
    if not include_inactive:
        query = query.filter(
            MenuItem.is_active.is_(True),
            MenuCategory.is_active.is_(True),
        )
    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)
    if item_type:
        query = query.filter(MenuItem.type == item_type)
    return query.order_by(MenuItem.order_index, MenuItem.id)


def _serialize_category(category: MenuCategory) -> dict[str, Any]:
    return {
        "id": int(category.id),
        "title": category.title,
        "slug": category.slug,
        "description": category.description,
        "image_url": category.image_url,
        "order_index": int(category.order_index or 0),
        "is_active": bool(category.is_active),
        "created_at": category.created_at.isoformat() if category.created_at else None,
        "updated_at": category.updated_at.isoformat() if category.updated_at else None,
    }


def _serialize_item(item: MenuItem, category: MenuCategory | None = None) -> dict[str, Any]:
    linked_category = category or item.category  # type: ignore[assignment]
    images = list(item.images or [])
    image_url = item.image_url
    if not image_url and images:
        image_url = images[0]
    return {
        "id": int(item.id),
        "category_id": int(item.category_id),
        "category_title": getattr(linked_category, "title", None),
        "category_slug": getattr(linked_category, "slug", None),
        "title": item.title,
        "subtitle": item.subtitle,
        "slug": item.slug,
        "description": item.description,
        "price": float(item.price or 0) if item.price is not None else None,
        "currency": item.currency,
        "images": images,
        "image_url": image_url,
        "legacy_link": item.legacy_link,
        "order_index": int(item.order_index or 0),
        "is_active": bool(item.is_active),
        "type": item.type,
        "meta": item.meta or {},
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def list_categories(*, include_inactive: bool = False) -> list[dict[str, Any]]:
    with get_session() as session:
        categories = _category_query(session, include_inactive=include_inactive).all()
    return [_serialize_category(category) for category in categories]


def list_items(
    *,
    include_inactive: bool = False,
    category_id: int | None = None,
    item_type: str | None = None,
) -> list[dict[str, Any]]:
    normalized_type = normalize_menu_type(item_type)
    with get_session() as session:
        rows = _item_query(
            session,
            include_inactive=include_inactive,
            category_id=category_id,
            item_type=normalized_type,
        ).all()
    return [_serialize_item(item, category) for item, category in rows]


def get_category_by_slug(slug: str, *, include_inactive: bool = False) -> MenuCategory | None:
    normalized_slug = (slug or "").strip().lower()
    if not normalized_slug:
        return None
    with get_session() as session:
        query = _category_query(session, include_inactive=include_inactive).filter(
            func.lower(MenuCategory.slug) == normalized_slug
        )
        return query.first()


def get_category_details(slug: str, *, include_inactive: bool = False) -> dict[str, Any] | None:
    category = get_category_by_slug(slug, include_inactive=include_inactive)
    if not category:
        return None
    payload = _serialize_category(category)
    payload["items"] = list_items(
        include_inactive=include_inactive,
        category_id=int(category.id),
    )
    return payload


def get_category_by_id(category_id: int) -> MenuCategory | None:
    with get_session() as session:
        return session.get(MenuCategory, category_id)


def get_item_by_slug(
    slug: str, *, include_inactive: bool = False
) -> dict[str, Any] | None:
    normalized_slug = (slug or "").strip().lower()
    if not normalized_slug:
        return None
    with get_session() as session:
        query = _item_query(
            session, include_inactive=include_inactive, category_id=None, item_type=None
        ).filter(func.lower(MenuItem.slug) == normalized_slug)
        result = query.first()
        if not result:
            return None
        item, category = result
        return _serialize_item(item, category)


def get_item_by_id(
    item_id: int, *, include_inactive: bool = False, item_type: str | None = None
) -> dict[str, Any] | None:
    normalized_type = normalize_menu_type(item_type)
    with get_session() as session:
        query = _item_query(
            session,
            include_inactive=include_inactive,
            category_id=None,
            item_type=normalized_type,
        ).filter(MenuItem.id == item_id)
        result = query.first()
        if not result:
            return None
        item, category = result
        return _serialize_item(item, category)


def build_public_menu() -> dict[str, Any]:
    with get_session() as session:
        categories = _category_query(session, include_inactive=False).all()
        rows = _item_query(session, include_inactive=False).all()

    items_by_category: dict[int, list[dict[str, Any]]] = {}
    for item, category in rows:
        items_by_category.setdefault(category.id, []).append(
            _serialize_item(item, category)
        )

    serialized_categories = []
    updated_at = None
    for category in categories:
        serialized = _serialize_category(category)
        serialized["items"] = items_by_category.get(category.id, [])
        serialized_categories.append(serialized)
        if category.updated_at and (updated_at is None or category.updated_at > updated_at):
            updated_at = category.updated_at

    updated_at = updated_at or datetime.utcnow()
    return {
        "categories": serialized_categories,
        "updated_at": updated_at.isoformat(),
    }


def get_or_create_site_settings(session: Session) -> SiteSettings:
    settings = session.execute(select(SiteSettings)).scalars().first()
    if settings:
        return settings
    settings = SiteSettings()
    session.add(settings)
    session.flush()
    return settings


def _serialize_settings(settings: SiteSettings) -> dict[str, Any]:
    return {
        "id": int(settings.id),
        "brand_name": settings.brand_name,
        "logo_url": settings.logo_url,
        "primary_color": settings.primary_color,
        "secondary_color": settings.secondary_color,
        "background_color": settings.background_color,
        "contacts": settings.contacts or {},
        "social_links": settings.social_links or {},
        "hero_enabled": bool(settings.hero_enabled),
        "hero_title": settings.hero_title,
        "hero_subtitle": settings.hero_subtitle,
        "hero_image_url": settings.hero_image_url,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }


def get_site_settings() -> dict[str, Any]:
    with get_session() as session:
        settings = get_or_create_site_settings(session)
        return _serialize_settings(settings)


def update_site_settings(payload: dict[str, Any]) -> dict[str, Any]:
    with get_session() as session:
        settings = get_or_create_site_settings(session)
        settings.brand_name = (payload.get("brand_name") or "").strip() or None
        settings.logo_url = normalize_media_path(payload.get("logo_url"))
        settings.primary_color = (payload.get("primary_color") or "").strip() or None
        settings.secondary_color = (payload.get("secondary_color") or "").strip() or None
        settings.background_color = (payload.get("background_color") or "").strip() or None
        settings.contacts = payload.get("contacts") or {}
        settings.social_links = payload.get("social_links") or {}
        if payload.get("hero_enabled") is not None:
            settings.hero_enabled = bool(payload.get("hero_enabled"))
        settings.hero_title = (payload.get("hero_title") or "").strip() or None
        settings.hero_subtitle = (payload.get("hero_subtitle") or "").strip() or None
        settings.hero_image_url = normalize_media_path(payload.get("hero_image_url"))
        settings.updated_at = datetime.utcnow()
        session.add(settings)
        session.commit()
        session.refresh(settings)
        return _serialize_settings(settings)


def create_category(payload: dict[str, Any]) -> dict[str, Any]:
    with get_session() as session:
        title = (payload.get("title") or "").strip()
        if not title:
            raise ValueError("Title is required")
        slug_base = normalize_slug(payload.get("slug"), title=title)
        slug = generate_unique_slug(session, MenuCategory, slug_base, [])
        category = MenuCategory(
            title=title,
            slug=slug,
            description=payload.get("description"),
            image_url=normalize_media_path(payload.get("image_url")),
            order_index=int(payload.get("order_index") or 0),
            is_active=bool(payload.get("is_active", True)),
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        return _serialize_category(category)


def update_category(category_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with get_session() as session:
        category = session.get(MenuCategory, category_id)
        if not category:
            raise KeyError("Category not found")

        if "title" in payload:
            next_title = (payload.get("title") or "").strip()
            if not next_title:
                raise ValueError("Title is required")
            category.title = next_title
        if "description" in payload:
            category.description = payload.get("description")
        if "image_url" in payload:
            category.image_url = normalize_media_path(payload.get("image_url"))
        if "is_active" in payload:
            category.is_active = bool(payload.get("is_active"))
        if "order_index" in payload:
            category.order_index = int(payload.get("order_index") or 0)

        if "slug" in payload or "title" in payload:
            slug_base = normalize_slug(payload.get("slug"), title=category.title)
            category.slug = generate_unique_slug(
                session,
                MenuCategory,
                slug_base,
                [],
                exclude_id=category.id,
            )

        category.updated_at = datetime.utcnow()
        session.add(category)
        session.commit()
        session.refresh(category)
        return _serialize_category(category)


def delete_category(category_id: int) -> None:
    with get_session() as session:
        category = session.get(MenuCategory, category_id)
        if not category:
            raise KeyError("Category not found")
        items_count = (
            session.query(MenuItem.id)
            .filter(MenuItem.category_id == category_id)
            .count()
        )
        if items_count:
            raise ValueError("Category has items")
        session.delete(category)
        session.commit()


def create_item(payload: dict[str, Any]) -> dict[str, Any]:
    with get_session() as session:
        category = session.get(MenuCategory, int(payload.get("category_id") or 0))
        if not category:
            raise KeyError("Category not found")

        title = (payload.get("title") or "").strip()
        if not title:
            raise ValueError("Title is required")
        normalized_type = normalize_menu_type(payload.get("type")) or "product"
        slug_base = normalize_slug(payload.get("slug"), title=title)
        slug = generate_unique_slug(
            session,
            MenuItem,
            slug_base,
            [MenuItem.category_id == category.id],
        )
        images = [normalize_media_path(item) for item in (payload.get("images") or [])]
        item = MenuItem(
            category_id=category.id,
            title=title,
            subtitle=payload.get("subtitle"),
            slug=slug,
            description=payload.get("description"),
            price=payload.get("price"),
            currency=payload.get("currency"),
            images=[item for item in images if item],
            image_url=normalize_media_path(payload.get("image_url")),
            legacy_link=payload.get("legacy_link"),
            order_index=int(payload.get("order_index") or 0),
            is_active=bool(payload.get("is_active", True)),
            type=normalized_type,
            meta=payload.get("meta") or {},
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return _serialize_item(item, category)


def update_item(item_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with get_session() as session:
        item = session.get(MenuItem, item_id)
        if not item:
            raise KeyError("Item not found")

        if "category_id" in payload:
            category = session.get(MenuCategory, int(payload.get("category_id") or 0))
            if not category:
                raise KeyError("Category not found")
            item.category_id = category.id
        else:
            category = item.category

        if "title" in payload:
            next_title = (payload.get("title") or "").strip()
            if not next_title:
                raise ValueError("Title is required")
            item.title = next_title
        if "subtitle" in payload:
            item.subtitle = payload.get("subtitle")
        if "description" in payload:
            item.description = payload.get("description")
        if "price" in payload:
            item.price = payload.get("price")
        if "currency" in payload:
            item.currency = payload.get("currency")
        if "images" in payload:
            images = [normalize_media_path(entry) for entry in (payload.get("images") or [])]
            item.images = [entry for entry in images if entry]
        if "image_url" in payload:
            item.image_url = normalize_media_path(payload.get("image_url"))
        if "legacy_link" in payload:
            item.legacy_link = payload.get("legacy_link")
        if "order_index" in payload:
            item.order_index = int(payload.get("order_index") or 0)
        if "is_active" in payload:
            item.is_active = bool(payload.get("is_active"))
        if "type" in payload:
            item.type = normalize_menu_type(payload.get("type")) or item.type
        if "meta" in payload:
            item.meta = payload.get("meta") or {}

        if "slug" in payload or "title" in payload or "category_id" in payload:
            slug_base = normalize_slug(payload.get("slug"), title=item.title)
            item.slug = generate_unique_slug(
                session,
                MenuItem,
                slug_base,
                [MenuItem.category_id == item.category_id],
                exclude_id=item.id,
            )

        item.updated_at = datetime.utcnow()
        session.add(item)
        session.commit()
        session.refresh(item)
        return _serialize_item(item, category)


def _block_query(session: Session, *, include_inactive: bool) -> Any:
    query = session.query(SiteBlock)
    if not include_inactive:
        query = query.filter(SiteBlock.is_active.is_(True))
    return query.order_by(SiteBlock.order_index, SiteBlock.id)


def _serialize_block(block: SiteBlock) -> dict[str, Any]:
    return {
        "id": int(block.id),
        "page": block.page,
        "type": block.type,
        "title": block.title,
        "subtitle": block.subtitle,
        "image_url": block.image_url,
        "payload": block.payload or {},
        "order_index": int(block.order_index or 0),
        "is_active": bool(block.is_active),
        "created_at": block.created_at.isoformat() if block.created_at else None,
        "updated_at": block.updated_at.isoformat() if block.updated_at else None,
    }


def list_blocks(
    *, include_inactive: bool = False, page: str | None = None
) -> list[dict[str, Any]]:
    with get_session() as session:
        query = _block_query(session, include_inactive=include_inactive)
        if page:
            query = query.filter(SiteBlock.page == page)
        blocks = query.all()
    return [_serialize_block(block) for block in blocks]


def create_block(payload: dict[str, Any]) -> dict[str, Any]:
    with get_session() as session:
        page = (payload.get("page") or "").strip().lower()
        if not page or page not in BLOCK_PAGES:
            raise ValueError("Invalid page")
        block_type = (payload.get("type") or "").strip().lower()
        if not block_type or block_type not in BLOCK_TYPES:
            raise ValueError("Invalid block type")
        block = SiteBlock(
            page=page,
            type=block_type,
            title=(payload.get("title") or "").strip() or None,
            subtitle=payload.get("subtitle"),
            image_url=normalize_media_path(payload.get("image_url")),
            payload=payload.get("payload") or {},
            order_index=int(payload.get("order_index") or 0),
            is_active=bool(payload.get("is_active", True)),
        )
        session.add(block)
        session.commit()
        session.refresh(block)
        return _serialize_block(block)


def update_block(block_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with get_session() as session:
        block = session.get(SiteBlock, block_id)
        if not block:
            raise KeyError("Block not found")
        if "page" in payload:
            page = (payload.get("page") or "").strip().lower()
            if not page or page not in BLOCK_PAGES:
                raise ValueError("Invalid page")
            block.page = page
        if "type" in payload:
            block_type = (payload.get("type") or "").strip().lower()
            if not block_type or block_type not in BLOCK_TYPES:
                raise ValueError("Invalid block type")
            block.type = block_type
        if "title" in payload:
            block.title = (payload.get("title") or "").strip() or None
        if "subtitle" in payload:
            block.subtitle = payload.get("subtitle")
        if "image_url" in payload:
            block.image_url = normalize_media_path(payload.get("image_url"))
        if "payload" in payload:
            block.payload = payload.get("payload") or {}
        if "order_index" in payload:
            block.order_index = int(payload.get("order_index") or 0)
        if "is_active" in payload:
            block.is_active = bool(payload.get("is_active"))
        block.updated_at = datetime.utcnow()
        session.add(block)
        session.commit()
        session.refresh(block)
        return _serialize_block(block)


def delete_block(block_id: int) -> None:
    with get_session() as session:
        block = session.get(SiteBlock, block_id)
        if not block:
            raise KeyError("Block not found")
        session.delete(block)
        session.commit()


def reorder_blocks(payload: dict[str, Any]) -> None:
    with get_session() as session:
        blocks = payload.get("blocks") or []
        for entry in blocks:
            block_id = entry.get("id")
            order_index = entry.get("order_index")
            if block_id is None or order_index is None:
                continue
            session.query(SiteBlock).filter(SiteBlock.id == block_id).update(
                {"order_index": int(order_index), "updated_at": datetime.utcnow()}
            )
        session.commit()


def delete_item(item_id: int) -> None:
    with get_session() as session:
        item = session.get(MenuItem, item_id)
        if not item:
            raise KeyError("Item not found")
        session.delete(item)
        session.commit()


def reorder_entities(payload: dict[str, Any]) -> None:
    with get_session() as session:
        categories = payload.get("categories") or []
        items = payload.get("items") or []

        for entry in categories:
            category_id = entry.get("id")
            order_index = entry.get("order_index")
            if category_id is None or order_index is None:
                continue
            session.query(MenuCategory).filter(MenuCategory.id == category_id).update(
                {"order_index": int(order_index), "updated_at": datetime.utcnow()}
            )

        for entry in items:
            item_id = entry.get("id")
            order_index = entry.get("order_index")
            if item_id is None or order_index is None:
                continue
            session.query(MenuItem).filter(MenuItem.id == item_id).update(
                {"order_index": int(order_index), "updated_at": datetime.utcnow()}
            )

        session.commit()
