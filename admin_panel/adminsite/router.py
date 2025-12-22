from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from admin_panel.dependencies import get_db_session
from . import service
from .schemas import (
    CategoryPayload,
    CategoryResponse,
    CategoryUpdatePayload,
    ItemPayload,
    ItemResponse,
    ItemUpdatePayload,
    WebAppSettingsPayload,
    WebAppSettingsResponse,
)

TypeQuery = Annotated[str, Query(pattern="^(product|course)$")]

router = APIRouter(prefix="/api/adminsite", tags=["AdminSite"])


@router.get("/health")
def healthcheck() -> dict[str, bool]:
    return {"ok": True}


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    request: Request,
    type: TypeQuery,
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    categories = service.list_categories(db, type)
    return categories


@router.post("/categories", response_model=CategoryResponse)
def create_category(
    payload: CategoryPayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    category = service.create_category(db, payload)
    return category


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdatePayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    category = service.update_category(db, category_id, payload)
    return category


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    return service.delete_category(db, category_id)


@router.get("/items", response_model=list[ItemResponse])
def list_items(
    request: Request,
    type: TypeQuery,
    category_id: int | None = Query(None),
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    items = service.list_items(db, type, category_id)
    return items


@router.post("/items", response_model=ItemResponse)
def create_item(
    payload: ItemPayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    item = service.create_item(db, payload)
    return item


@router.put("/items/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: int,
    payload: ItemUpdatePayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    item = service.update_item(db, item_id, payload)
    return item


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    return service.delete_item(db, item_id)


@router.get("/webapp-settings", response_model=WebAppSettingsResponse)
def get_webapp_settings(
    request: Request,
    type: TypeQuery,
    category_id: int | None = Query(None),
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    settings = service.get_webapp_settings(db, type, category_id)
    return settings


@router.put("/webapp-settings", response_model=WebAppSettingsResponse)
def upsert_webapp_settings(
    payload: WebAppSettingsPayload,
    request: Request,
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    settings = service.upsert_webapp_settings(db, payload)
    return settings
