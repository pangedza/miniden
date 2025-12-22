from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from admin_panel.dependencies import require_admin
from models import AdminSiteCategory, AdminSiteItem, AdminSiteWebAppSettings
from models.admin_user import AdminRole
from .schemas import (
    CategoryPayload,
    CategoryUpdatePayload,
    ItemPayload,
    ItemUpdatePayload,
    WebAppSettingsPayload,
)

ALLOWED_TYPES = {"product", "course"}
ALLOWED_ROLES: Iterable[AdminRole] = (AdminRole.superadmin, AdminRole.admin_site)


def ensure_admin(request: Request, db: Session) -> None:
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        raise HTTPException(status_code=401, detail="Admin authentication required")


def validate_type(value: str) -> None:
    if value not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported type value")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug


def generate_unique_slug(
    db: Session,
    model,
    slug_base: str,
    filters: list,
    exclude_id: int | None = None,
) -> str:
    slug = slug_base
    counter = 2
    while True:
        query = db.query(model.id).filter(model.slug == slug, *filters)
        if exclude_id:
            query = query.filter(model.id != exclude_id)
        exists = db.query(query.exists()).scalar()
        if not exists:
            return slug
        slug = f"{slug_base}-{counter}"
        counter += 1


def normalize_slug(value: str | None, *, title: str) -> str:
    base = (value or "").strip() or title
    slug = slugify(base)
    if not slug:
        raise HTTPException(status_code=400, detail="Slug cannot be empty")
    return slug


def get_category(db: Session, category_id: int) -> AdminSiteCategory:
    category = db.get(AdminSiteCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def list_categories(db: Session, type_value: str) -> list[AdminSiteCategory]:
    validate_type(type_value)
    categories = (
        db.query(AdminSiteCategory)
        .filter(AdminSiteCategory.type == type_value)
        .order_by(AdminSiteCategory.sort, AdminSiteCategory.id)
        .all()
    )
    return categories


def create_category(db: Session, payload: CategoryPayload) -> AdminSiteCategory:
    validate_type(payload.type)
    if payload.parent_id is not None:
        parent = get_category(db, payload.parent_id)
        if parent.type != payload.type:
            raise HTTPException(
                status_code=400,
                detail="Parent category type does not match",
            )

    slug_base = normalize_slug(payload.slug, title=payload.title)
    slug = generate_unique_slug(
        db,
        AdminSiteCategory,
        slug_base,
        [AdminSiteCategory.type == payload.type],
    )

    category = AdminSiteCategory(
        type=payload.type,
        title=payload.title,
        slug=slug,
        parent_id=payload.parent_id,
        is_active=payload.is_active,
        sort=payload.sort,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session, category_id: int, payload: CategoryUpdatePayload
) -> AdminSiteCategory:
    category = get_category(db, category_id)

    new_type = payload.type or category.type
    validate_type(new_type)

    if payload.parent_id is not None:
        parent = get_category(db, payload.parent_id)
        if parent.type != new_type:
            raise HTTPException(
                status_code=400,
                detail="Parent category type does not match",
            )
        category.parent_id = payload.parent_id
    elif "parent_id" in payload.__fields_set__:
        category.parent_id = None

    if payload.title is not None:
        category.title = payload.title

    slug_base = None
    if "slug" in payload.__fields_set__:
        slug_base = normalize_slug(payload.slug, title=category.title)
    elif "title" in payload.__fields_set__:
        slug_base = normalize_slug(None, title=category.title)

    if slug_base:
        category.slug = generate_unique_slug(
            db,
            AdminSiteCategory,
            slug_base,
            [AdminSiteCategory.type == new_type],
            exclude_id=category.id,
        )

    category.type = new_type
    if payload.is_active is not None:
        category.is_active = payload.is_active
    if payload.sort is not None:
        category.sort = payload.sort

    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: int) -> dict[str, str]:
    category = get_category(db, category_id)
    has_items = (
        db.query(AdminSiteItem.id)
        .filter(AdminSiteItem.category_id == category_id)
        .first()
    )
    if has_items:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category with items",
        )
    db.delete(category)
    db.commit()
    return {"status": "ok"}


def list_items(
    db: Session, type_value: str, category_id: int | None
) -> list[AdminSiteItem]:
    validate_type(type_value)
    query = db.query(AdminSiteItem).filter(AdminSiteItem.type == type_value)
    if category_id is not None:
        query = query.filter(AdminSiteItem.category_id == category_id)
    items = query.order_by(AdminSiteItem.sort, AdminSiteItem.id).all()
    return items


def create_item(db: Session, payload: ItemPayload) -> AdminSiteItem:
    validate_type(payload.type)
    category = get_category(db, payload.category_id)
    if category.type != payload.type:
        raise HTTPException(
            status_code=400,
            detail="Item type does not match category",
        )

    slug_base = normalize_slug(payload.slug, title=payload.title)
    slug = generate_unique_slug(
        db,
        AdminSiteItem,
        slug_base,
        [
            AdminSiteItem.type == payload.type,
            AdminSiteItem.category_id == payload.category_id,
        ],
    )

    item = AdminSiteItem(
        type=payload.type,
        category_id=payload.category_id,
        title=payload.title,
        slug=slug,
        price=payload.price,
        image_url=payload.image_url,
        short_text=payload.short_text,
        description=payload.description,
        is_active=payload.is_active,
        sort=payload.sort,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, payload: ItemUpdatePayload) -> AdminSiteItem:
    item = db.get(AdminSiteItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    new_type = payload.type or item.type
    validate_type(new_type)

    new_category_id = payload.category_id if payload.category_id is not None else item.category_id
    category = get_category(db, new_category_id)
    if category.type != new_type:
        raise HTTPException(
            status_code=400,
            detail="Item type does not match category",
        )

    if payload.title is not None:
        item.title = payload.title
    if payload.price is not None:
        item.price = payload.price
    if payload.image_url is not None:
        item.image_url = payload.image_url
    if payload.short_text is not None:
        item.short_text = payload.short_text
    if payload.description is not None:
        item.description = payload.description
    if payload.is_active is not None:
        item.is_active = payload.is_active
    if payload.sort is not None:
        item.sort = payload.sort

    slug_base = None
    if "slug" in payload.__fields_set__:
        slug_base = normalize_slug(payload.slug, title=item.title)
    elif "title" in payload.__fields_set__:
        slug_base = normalize_slug(None, title=item.title)

    if slug_base:
        item.slug = generate_unique_slug(
            db,
            AdminSiteItem,
            slug_base,
            [
                AdminSiteItem.type == new_type,
                AdminSiteItem.category_id == category.id,
            ],
            exclude_id=item.id,
        )

    item.type = new_type
    item.category_id = category.id

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: int) -> dict[str, str]:
    item = db.get(AdminSiteItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"status": "ok"}


def get_webapp_settings(
    db: Session, type_value: str, category_id: int | None
) -> AdminSiteWebAppSettings:
    validate_type(type_value)

    settings: AdminSiteWebAppSettings | None = None
    if category_id is not None:
        get_category(db, category_id)
        settings = (
            db.query(AdminSiteWebAppSettings)
            .filter(
                AdminSiteWebAppSettings.scope == "category",
                AdminSiteWebAppSettings.type == type_value,
                AdminSiteWebAppSettings.category_id == category_id,
            )
            .first()
        )

    if settings is None:
        settings = (
            db.query(AdminSiteWebAppSettings)
            .filter(
                AdminSiteWebAppSettings.scope == "global",
                AdminSiteWebAppSettings.type == type_value,
            )
            .first()
        )

    if settings is None:
        raise HTTPException(status_code=404, detail="Settings not found")

    return settings


def upsert_webapp_settings(
    db: Session, payload: WebAppSettingsPayload
) -> AdminSiteWebAppSettings:
    validate_type(payload.type)

    category_id = payload.category_id
    if payload.scope == "category":
        category = get_category(db, payload.category_id or 0)
        if category.type != payload.type:
            raise HTTPException(
                status_code=400,
                detail="Settings type does not match category",
            )
    else:
        category_id = None

    settings = (
        db.query(AdminSiteWebAppSettings)
        .filter(
            AdminSiteWebAppSettings.scope == payload.scope,
            AdminSiteWebAppSettings.type == payload.type,
            AdminSiteWebAppSettings.category_id == category_id,
        )
        .first()
    )

    if settings is None:
        settings = AdminSiteWebAppSettings(
            scope=payload.scope,
            type=payload.type,
            category_id=category_id,
        )

    settings.action_enabled = payload.action_enabled
    settings.action_label = payload.action_label
    settings.min_selected = payload.min_selected

    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
