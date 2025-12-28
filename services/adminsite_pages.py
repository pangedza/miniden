from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_session
from models import AdminSitePage
from schemas.adminsite_page import PageConfig

DEFAULT_TEMPLATE_ID = "services"
DEFAULT_SLUG = "home"
logger = logging.getLogger(__name__)


def _default_blocks() -> list[dict[str, Any]]:
    return []


def _safe_page_config(
    *, template_id: str | None = None, blocks: list[dict[str, Any]] | None = None, theme: dict | None = None
) -> PageConfig:
    try:
        return PageConfig(
            template_id=template_id or DEFAULT_TEMPLATE_ID,
            blocks=blocks or [],
            theme=theme or {},
        )
    except ValidationError:
        logger.exception("Failed to normalize AdminSite page config, returning minimal state")
        return PageConfig(template_id=DEFAULT_TEMPLATE_ID, blocks=[], theme={})


def _normalize_page(page: AdminSitePage | None) -> PageConfig:
    if not page:
        return _safe_page_config()

    template_id = page.template_id or DEFAULT_TEMPLATE_ID
    raw_blocks = page.blocks or []
    theme = page.theme or {}

    return _safe_page_config(template_id=template_id, blocks=raw_blocks, theme=theme)


def _serialize(page: AdminSitePage | None, slug: str = DEFAULT_SLUG) -> dict[str, Any]:
    config = _normalize_page(page)
    payload = config.model_dump(by_alias=True)

    if page:
        payload["version"] = (page.updated_at or page.created_at).isoformat()
        payload["updatedAt"] = (page.updated_at or page.created_at).isoformat()
        payload["slug"] = page.slug or slug
    else:
        payload["version"] = datetime.utcnow().isoformat()
        payload["updatedAt"] = payload["version"]
        payload["slug"] = slug

    return payload


def get_page(slug: str = DEFAULT_SLUG) -> dict[str, Any]:
    try:
        with get_session() as session:
            return _get_page(session, slug)
    except Exception:
        safe_slug = slug or DEFAULT_SLUG
        logger.exception("Failed to load AdminSite page %s, returning minimal state", safe_slug)
        return _serialize(None, safe_slug)


def _get_page(session: Session, slug: str) -> dict[str, Any]:
    safe_slug = slug or DEFAULT_SLUG
    page = (
        session.execute(select(AdminSitePage).where(AdminSitePage.slug == safe_slug))
        .scalars()
        .first()
    )

    if not page:
        page = AdminSitePage(
            slug=safe_slug,
            template_id=DEFAULT_TEMPLATE_ID,
            blocks=_default_blocks(),
        )
        session.add(page)
        session.commit()
        session.refresh(page)

    return _serialize(page, safe_slug)


def update_page(payload: dict[str, Any], slug: str = DEFAULT_SLUG) -> dict[str, Any]:
    safe_slug = slug or DEFAULT_SLUG
    try:
        data = PageConfig.model_validate(payload)
    except ValidationError:
        logger.exception("Invalid AdminSite payload, returning minimal state for %s", safe_slug)
        return _serialize(None, safe_slug)

    theme_payload = payload.get("theme") if isinstance(payload, dict) else None

    try:
        with get_session() as session:
            page = (
                session.execute(select(AdminSitePage).where(AdminSitePage.slug == safe_slug))
                .scalars()
                .first()
            )

            if not page:
                page = AdminSitePage(
                    slug=safe_slug,
                    template_id=data.template_id or DEFAULT_TEMPLATE_ID,
                    blocks=data.model_dump(by_alias=True).get("blocks", _default_blocks()),
                    theme=(data.theme if theme_payload is not None else {}),
                )
                session.add(page)
            else:
                page.template_id = data.template_id or DEFAULT_TEMPLATE_ID
                page.blocks = data.model_dump(by_alias=True).get("blocks", _default_blocks())
                if theme_payload is not None:
                    page.theme = data.theme
                page.updated_at = datetime.utcnow()

            session.commit()
            session.refresh(page)
            return _serialize(page, safe_slug)
    except Exception:
        logger.exception("Failed to update AdminSite page %s, returning minimal state", safe_slug)
        return _serialize(None, safe_slug)


__all__ = ["get_page", "update_page", "DEFAULT_TEMPLATE_ID"]
