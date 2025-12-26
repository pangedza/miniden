from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.orm import Session

from admin_panel.dependencies import get_current_admin, get_db_session
from schemas.adminsite_page import PageConfig
from . import media as media_service, service
from services import adminsite_pages
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

TypeQuery = Annotated[str, Query(min_length=1)]

router = APIRouter(prefix="/api/adminsite", tags=["AdminSite"])


@router.get("/health")
def healthcheck() -> dict[str, bool]:
    return {"ok": True}


@router.get("/debug/env")
def debug_env(request: Request, db: Session = Depends(get_db_session)) -> dict[str, str | bool]:
    user = get_current_admin(request, db)
    return {
        "base_url_detected": str(request.base_url),
        "request_host": request.headers.get("host", ""),
        "auth_required": user is None,
    }


@router.get("/pages/home", response_model=dict)
def adminsite_home_page(request: Request, db: Session = Depends(get_db_session)):
    service.ensure_admin(request, db)
    return adminsite_pages.get_page()


@router.put("/pages/home", response_model=dict)
def adminsite_update_home_page(
    payload: PageConfig, request: Request, db: Session = Depends(get_db_session)
):
    service.ensure_admin(request, db)
    return adminsite_pages.update_page(payload.model_dump(by_alias=True))


@router.get("/media", response_model=list[dict])
def list_media(request: Request, q: str | None = Query(None), db: Session = Depends(get_db_session)):
    service.ensure_admin(request, db)
    return media_service.list_media(q)


@router.post("/media/upload", response_model=dict)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
):
    service.ensure_admin(request, db)
    return await media_service.save_upload(file)


@router.delete("/media/{filename}", response_model=dict)
def delete_media(
    filename: str, request: Request, db: Session = Depends(get_db_session)
):
    service.ensure_admin(request, db)
    return media_service.delete_media(filename)


@router.get("/types", response_model=list[str])
def list_types(request: Request, db: Session = Depends(get_db_session)) -> list[str]:
    service.ensure_admin(request, db)
    return sorted(service.get_allowed_types(db))


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
