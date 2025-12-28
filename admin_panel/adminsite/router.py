from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from admin_panel.dependencies import get_current_admin, get_db_session
from schemas.adminsite_page import PageConfig
from . import media as media_service, service
from services import adminsite_pages
from database import DATABASE_URL
from models import AdminSiteItem, AdminSitePage
from sqlalchemy.engine.url import make_url
from services.theme_service import ThemeApplyError, apply_theme
from .schemas import (
    CategoryPayload,
    CategoryResponse,
    CategoryUpdatePayload,
    ItemPayload,
    ItemResponse,
    ItemUpdatePayload,
    ThemeApplyPayload,
    ThemeApplyResponse,
    WebAppSettingsPayload,
    WebAppSettingsResponse,
)

TypeQuery = Annotated[str, Query(min_length=1)]

router = APIRouter(prefix="/api/adminsite", tags=["AdminSite"])
logger = logging.getLogger(__name__)


def _safe_slug(key: str | None) -> str:
    slug = (key or "").strip() or adminsite_pages.DEFAULT_SLUG
    return slug


def _build_error_payload(error_id: str) -> dict[str, str]:
    return {"error": "internal", "error_id": error_id, "message": "см. логи"}


def _build_default_home(slug: str) -> dict[str, str | list]:
    now = datetime.utcnow().isoformat()
    return {
        "key": slug,
        "templateId": adminsite_pages.DEFAULT_TEMPLATE_ID,
        "blocks": [],
        "updatedAt": now,
        "version": now,
        "slug": slug,
    }


def _mask_database_url(raw_url: str) -> str:
    try:
        parsed = make_url(raw_url)
        return parsed.render_as_string(hide_password=True)
    except Exception:
        logger.exception("Failed to mask database URL")
        return "unknown"


def _check_path(path: Path) -> dict[str, str | bool]:
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "exists": resolved.exists(),
        "is_dir": resolved.is_dir(),
        "is_writable": os.access(resolved, os.W_OK),
    }


def _serialize_item(item: AdminSiteItem) -> ItemResponse:
    """Convert ORM item to response with safe defaults.

    Some legacy rows may contain NULL values; normalize them to keep
    serialization stable instead of propagating a 500 to the client.
    """

    payload = {
        "id": item.id,
        "type": item.type or "",
        "category_id": item.category_id,
        "title": item.title or "",
        "slug": item.slug or "",
        "price": Decimal(item.price or 0),
        "stock": int(item.stock or 0),
        "image_url": item.image_url,
        "short_text": item.short_text,
        "description": item.description,
        "is_active": bool(item.is_active),
        "sort": item.sort or 0,
        "created_at": item.created_at,
    }
    try:
        return ItemResponse.model_validate(payload)
    except Exception:
        logger.exception("Failed to serialize AdminSite item id=%s", getattr(item, "id", "?"))
        raise


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


@router.get("/debug/diag")
def debug_diag(request: Request, db: Session = Depends(get_db_session)) -> dict[str, object]:
    service.ensure_admin(request, db)

    project_root = Path(__file__).resolve().parents[2]
    webapp_path = project_root / "webapp"
    static_path = project_root / "static"
    adminsite_static = Path(__file__).resolve().parent / "static"

    db_masked = _mask_database_url(DATABASE_URL)
    db_path_info: dict[str, object] | None = None
    try:
        parsed_url = make_url(DATABASE_URL)
        if parsed_url.drivername.startswith("sqlite") and parsed_url.database:
            db_path_info = _check_path(Path(parsed_url.database))
    except Exception:
        logger.exception("Failed to parse DB URL for diag")

    home_page = (
        db.execute(select(AdminSitePage).where(AdminSitePage.slug == adminsite_pages.DEFAULT_SLUG))
        .scalars()
        .first()
    )

    return {
        "cwd": str(Path.cwd()),
        "paths": {
            "webapp_path": _check_path(webapp_path),
            "static_path": _check_path(static_path),
            "adminsite_static_path": _check_path(adminsite_static),
            "db_path": db_path_info,
        },
        "database": {
            "dsn": db_masked,
        },
        "home": {
            "found": bool(home_page),
            "templateId": (home_page.template_id if home_page else None) or adminsite_pages.DEFAULT_TEMPLATE_ID,
        },
    }


def _get_page_response(page_key: str, request: Request, db: Session) -> JSONResponse | dict:
    service.ensure_admin(request, db)
    slug = _safe_slug(page_key)
    try:
        return adminsite_pages.get_page(slug, raise_on_error=True)
    except HTTPException:
        raise
    except Exception:
        error_id = uuid4().hex[:8]
        logger.exception("Failed to load AdminSite page %s error_id=%s", slug, error_id)
        if slug == adminsite_pages.DEFAULT_SLUG:
            payload = _build_default_home(slug)
            payload["error_id"] = error_id
            payload["fallback"] = True
            return JSONResponse(status_code=200, content=payload)
        return JSONResponse(status_code=500, content=_build_error_payload(error_id))


@router.get("/pages/{page_key}", response_model=dict)
def adminsite_page(page_key: str, request: Request, db: Session = Depends(get_db_session)):
    return _get_page_response(page_key, request, db)


@router.get("/pages/home", response_model=dict)
def adminsite_home_page(request: Request, db: Session = Depends(get_db_session)):
    return _get_page_response(adminsite_pages.DEFAULT_SLUG, request, db)


@router.put("/pages/home", response_model=dict)
def adminsite_update_home_page(
    payload: PageConfig, request: Request, db: Session = Depends(get_db_session)
):
    service.ensure_admin(request, db)
    return adminsite_pages.update_page(payload.model_dump(by_alias=True, exclude_unset=True))


@router.post("/theme/apply", response_model=ThemeApplyResponse)
def adminsite_apply_theme(
    payload: ThemeApplyPayload, request: Request, db: Session = Depends(get_db_session)
):
    service.ensure_admin(request, db)
    try:
        return apply_theme(payload.template_id)
    except ThemeApplyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    try:
        items = service.list_items(db, type, category_id)
        return [_serialize_item(item) for item in items]
    except HTTPException:
        raise
    except Exception:
        error_id = uuid4().hex[:8]
        logger.exception("Failed to list AdminSite items error_id=%s", error_id)
        return JSONResponse(status_code=200, content=[])


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
