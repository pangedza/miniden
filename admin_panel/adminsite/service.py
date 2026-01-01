from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from admin_panel.dependencies import require_admin
from models import AdminSiteCategory, AdminSiteItem
from models.admin_user import AdminRole
from .schemas import (
    CategoryPayload,
    CategoryUpdatePayload,
    ItemPayload,
    ItemUpdatePayload,
)

DEFAULT_TYPES: set[str] = {"product", "course"}
ALLOWED_ROLES: Iterable[AdminRole] = (AdminRole.superadmin, AdminRole.admin_site)


def ensure_admin(request: Request, db: Session) -> None:
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        raise HTTPException(status_code=401, detail="Admin authentication required")


def _distinct_column(db: Session, column) -> set[str]:
    values = (
        db.query(column)
        .filter(column.isnot(None))
        .distinct()
        .all()
    )
    return {value for value, in values}


def get_allowed_types(db: Session) -> set[str]:
    """Return all known AdminSite types.

    The list is built from existing records to avoid hardcoded values and to
    surface any legacy data that was previously saved.
    """

    db_types = {
        *_distinct_column(db, AdminSiteCategory.type),
        *_distinct_column(db, AdminSiteItem.type),
    }
    return DEFAULT_TYPES | {value for value in db_types if value}


def validate_type(value: str, db: Session) -> None:
    if value not in get_allowed_types(db):
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
    validate_type(type_value, db)
    categories = (
        db.query(AdminSiteCategory)
        .filter(AdminSiteCategory.type == type_value)
        .order_by(AdminSiteCategory.sort, AdminSiteCategory.id)
        .all()
    )
    return categories


def create_category(db: Session, payload: CategoryPayload) -> AdminSiteCategory:
    validate_type(payload.type, db)
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
    validate_type(new_type, db)

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
    child_count = (
        db.query(AdminSiteCategory.id)
        .filter(AdminSiteCategory.parent_id == category_id)
        .count()
    )
    items_count = (
        db.query(AdminSiteItem.id)
        .filter(AdminSiteItem.category_id == category_id)
        .count()
    )

    blockers: list[str] = []
    if child_count:
        blockers.append(f"подкатегории ({child_count})")
    if items_count:
        blockers.append(f"элементы ({items_count})")

    if blockers:
        message = "Нельзя удалить категорию — " + "; ".join(blockers)
        raise HTTPException(status_code=409, detail=message)

    try:
        db.delete(category)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить категорию — есть связанные записи",
        )
    return {"status": "ok"}


def list_items(
    db: Session, type_value: str, category_id: int | None
) -> list[AdminSiteItem]:
    validate_type(type_value, db)
    query = db.query(AdminSiteItem).filter(AdminSiteItem.type == type_value)
    if category_id is not None:
        query = query.filter(AdminSiteItem.category_id == category_id)
    items = query.order_by(AdminSiteItem.sort, AdminSiteItem.id).all()
    return items


def create_item(db: Session, payload: ItemPayload) -> AdminSiteItem:
    validate_type(payload.type, db)
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
        stock=int(payload.stock or 0),
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
    validate_type(new_type, db)

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
    if payload.stock is not None:
        item.stock = int(payload.stock)
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
    slug_provided = "slug" in payload.__fields_set__
    title_provided = "title" in payload.__fields_set__

    if slug_provided and payload.slug is not None:
        slug_base = normalize_slug(payload.slug, title=item.title)
    elif not slug_provided and title_provided:
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
