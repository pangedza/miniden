from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from admin_panel.dependencies import get_db_session, require_admin
from models import AdminSiteCategory, AdminSiteItem, AdminSiteWebAppSettings
from models.admin_user import AdminRole

router = APIRouter(prefix="/api/adminsite", tags=["AdminSite"])

ALLOWED_TYPES = {"product", "course"}
ALLOWED_ROLES: Iterable[AdminRole] = (AdminRole.superadmin, AdminRole.admin_site)


class CategoryPayload(BaseModel):
    type: str = Field(..., regex="^(product|course)$")
    title: str
    slug: str | None = None
    parent_id: int | None = None
    is_active: bool = True
    sort: int = 0


class CategoryUpdatePayload(BaseModel):
    type: str | None = Field(None, regex="^(product|course)$")
    title: str | None = None
    slug: str | None = None
    parent_id: int | None = None
    is_active: bool | None = None
    sort: int | None = None

    class Config:
        extra = "ignore"


class CategoryResponse(BaseModel):
    id: int
    type: str
    title: str
    slug: str
    parent_id: int | None
    is_active: bool
    sort: int
    created_at: datetime

    class Config:
        orm_mode = True


class ItemPayload(BaseModel):
    type: str = Field(..., regex="^(product|course)$")
    category_id: int
    title: str
    slug: str | None = None
    price: Decimal = Field(ge=0)
    image_url: str | None = None
    short_text: str | None = None
    description: str | None = None
    is_active: bool = True
    sort: int = 0

    @validator("price", pre=True)
    def _coerce_price(cls, value: Decimal | str | int) -> Decimal:
        return Decimal(value)


class ItemUpdatePayload(BaseModel):
    type: str | None = Field(None, regex="^(product|course)$")
    category_id: int | None = None
    title: str | None = None
    slug: str | None = None
    price: Decimal | None = Field(None, ge=0)
    image_url: str | None = None
    short_text: str | None = None
    description: str | None = None
    is_active: bool | None = None
    sort: int | None = None

    class Config:
        extra = "ignore"

    @validator("price", pre=True)
    def _coerce_price(cls, value: Decimal | str | int | None) -> Decimal | None:
        if value is None:
            return None
        return Decimal(value)


class ItemResponse(BaseModel):
    id: int
    type: str
    category_id: int
    title: str
    slug: str
    price: Decimal
    image_url: str | None
    short_text: str | None
    description: str | None
    is_active: bool
    sort: int
    created_at: datetime

    class Config:
        orm_mode = True


class WebAppSettingsPayload(BaseModel):
    scope: str = Field(..., regex="^(global|category)$")
    type: str = Field(..., regex="^(product|course)$")
    category_id: int | None = None
    action_enabled: bool = True
    action_label: str | None = None
    min_selected: int = Field(1, ge=0)

    @validator("category_id")
    def _validate_category_scope(
        cls, value: int | None, values: dict
    ) -> int | None:
        scope = values.get("scope")
        if scope == "category" and value is None:
            raise ValueError("category_id is required when scope=category")
        if scope == "global" and value is not None:
            raise ValueError("category_id must be null when scope=global")
        return value


class WebAppSettingsResponse(BaseModel):
    id: int
    scope: str
    type: str
    category_id: int | None
    action_enabled: bool
    action_label: str | None
    min_selected: int

    class Config:
        orm_mode = True


def _ensure_admin(request: Request, db: Session) -> None:
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        raise HTTPException(status_code=401, detail="Admin authentication required")


def _validate_type(value: str) -> None:
    if value not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported type value")


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug


def _generate_unique_slug(
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


def _normalize_slug(value: str | None, *, title: str) -> str:
    base = (value or "").strip() or title
    slug = _slugify(base)
    if not slug:
        raise HTTPException(status_code=400, detail="Slug cannot be empty")
    return slug


def _get_category(db: Session, category_id: int) -> AdminSiteCategory:
    category = db.get(AdminSiteCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    request: Request,
    type: str = Query(..., regex="^(product|course)$"),
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    _validate_type(type)
    categories = (
        db.query(AdminSiteCategory)
        .filter(AdminSiteCategory.type == type)
        .order_by(AdminSiteCategory.sort, AdminSiteCategory.id)
        .all()
    )
    return categories


@router.post("/categories", response_model=CategoryResponse)
def create_category(
    payload: CategoryPayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    _validate_type(payload.type)
    parent_id = payload.parent_id
    if parent_id is not None:
        parent = _get_category(db, parent_id)
        if parent.type != payload.type:
            raise HTTPException(
                status_code=400,
                detail="Parent category type does not match",
            )

    slug_base = _normalize_slug(payload.slug, title=payload.title)
    slug = _generate_unique_slug(
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


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdatePayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    category = _get_category(db, category_id)

    new_type = payload.type or category.type
    _validate_type(new_type)

    if payload.parent_id is not None:
        parent = _get_category(db, payload.parent_id)
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
        slug_base = _normalize_slug(payload.slug, title=category.title)
    elif "title" in payload.__fields_set__:
        slug_base = _normalize_slug(None, title=category.title)

    if slug_base:
        category.slug = _generate_unique_slug(
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


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    category = _get_category(db, category_id)
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


@router.get("/items", response_model=list[ItemResponse])
def list_items(
    request: Request,
    type: str = Query(..., regex="^(product|course)$"),
    category_id: int | None = Query(None),
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    _validate_type(type)
    query = db.query(AdminSiteItem).filter(AdminSiteItem.type == type)
    if category_id is not None:
        query = query.filter(AdminSiteItem.category_id == category_id)
    items = query.order_by(AdminSiteItem.sort, AdminSiteItem.id).all()
    return items


@router.post("/items", response_model=ItemResponse)
def create_item(
    payload: ItemPayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    _validate_type(payload.type)
    category = _get_category(db, payload.category_id)
    if category.type != payload.type:
        raise HTTPException(
            status_code=400,
            detail="Item type does not match category",
        )

    slug_base = _normalize_slug(payload.slug, title=payload.title)
    slug = _generate_unique_slug(
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


@router.put("/items/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: int,
    payload: ItemUpdatePayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    item = db.get(AdminSiteItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    new_type = payload.type or item.type
    _validate_type(new_type)

    new_category_id = payload.category_id if payload.category_id is not None else item.category_id
    category = _get_category(db, new_category_id)
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
        slug_base = _normalize_slug(payload.slug, title=item.title)
    elif "title" in payload.__fields_set__:
        slug_base = _normalize_slug(None, title=item.title)

    if slug_base:
        item.slug = _generate_unique_slug(
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


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    item = db.get(AdminSiteItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"status": "ok"}


@router.get("/webapp-settings", response_model=WebAppSettingsResponse)
def get_webapp_settings(
    request: Request,
    type: str = Query(..., regex="^(product|course)$"),
    category_id: int | None = Query(None),
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    _validate_type(type)

    settings: AdminSiteWebAppSettings | None = None
    if category_id is not None:
        _get_category(db, category_id)
        settings = (
            db.query(AdminSiteWebAppSettings)
            .filter(
                AdminSiteWebAppSettings.scope == "category",
                AdminSiteWebAppSettings.type == type,
                AdminSiteWebAppSettings.category_id == category_id,
            )
            .first()
        )

    if settings is None:
        settings = (
            db.query(AdminSiteWebAppSettings)
            .filter(
                AdminSiteWebAppSettings.scope == "global",
                AdminSiteWebAppSettings.type == type,
            )
            .first()
        )

    if settings is None:
        raise HTTPException(status_code=404, detail="Settings not found")

    return settings


@router.put("/webapp-settings", response_model=WebAppSettingsResponse)
def upsert_webapp_settings(
    payload: WebAppSettingsPayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    _ensure_admin(request, db)
    _validate_type(payload.type)

    category_id = payload.category_id
    if payload.scope == "category":
        category = _get_category(db, payload.category_id or 0)
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
