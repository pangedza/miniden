from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_session
from models import AdminSitePage
from schemas.adminsite_page import PageConfig

DEFAULT_TEMPLATE_ID = "services"
DEFAULT_SLUG = "home"
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _default_blocks() -> list[dict[str, Any]]:
    return []


def _wrap_state(blocks: list[dict[str, Any]] | None, *, template_id: str) -> dict[str, Any]:
    safe_blocks = blocks or []
    timestamp = _now_iso()
    return {
        "templateId": template_id or DEFAULT_TEMPLATE_ID,
        "blocks": safe_blocks,
        "version": timestamp,
        "updatedAt": timestamp,
    }


def _extract_states(page: AdminSitePage | None, slug: str) -> tuple[dict[str, Any], dict[str, Any]]:
    template_id = (page.template_id if page else None) or DEFAULT_TEMPLATE_ID
    updated_at = (page.updated_at or page.created_at).isoformat() if page else _now_iso()
    raw_blocks = page.blocks if page else None

    if isinstance(raw_blocks, dict):
        draft = raw_blocks.get("draft") or {}
        published = raw_blocks.get("published") or {}
    elif isinstance(raw_blocks, list):
        draft = {"blocks": raw_blocks, "version": updated_at, "updatedAt": updated_at, "templateId": template_id}
        published = draft
    else:
        draft = {}
        published = {}

    def _normalize(entry: dict[str, Any]) -> dict[str, Any]:
        blocks = entry.get("blocks") if isinstance(entry, dict) else None
        version = entry.get("version") if isinstance(entry, dict) else None
        updated = entry.get("updatedAt") if isinstance(entry, dict) else None
        template = (
            entry.get("templateId")
            or entry.get("template_id")
            or template_id
        ) if isinstance(entry, dict) else template_id

        wrapped = _wrap_state(blocks or _default_blocks(), template_id=template)
        if version:
            wrapped["version"] = version
        if updated:
            wrapped["updatedAt"] = updated
        wrapped["slug"] = slug
        wrapped["pageKey"] = slug
        return wrapped

    return _normalize(draft), _normalize(published)


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
    raw_blocks = []
    if isinstance(page.blocks, list):
        raw_blocks = page.blocks
    elif isinstance(page.blocks, dict):
        raw_blocks = page.blocks.get("draft", {}).get("blocks") or _default_blocks()
    theme = page.theme or {}

    return _safe_page_config(template_id=template_id, blocks=raw_blocks, theme=theme)


def _serialize(page: AdminSitePage | None, slug: str = DEFAULT_SLUG) -> dict[str, Any]:
    draft, published = _extract_states(page, slug)
    payload = {
        "pageKey": slug,
        "draft": draft,
        "published": published,
        "templateId": (page.template_id if page else None) or DEFAULT_TEMPLATE_ID,
        "theme": page.theme if page and isinstance(page.theme, dict) else {},
    }
    return payload


def _summarize_state(entry: dict[str, Any] | None, *, fallback_template: str) -> dict[str, Any]:
    blocks = entry.get("blocks") if isinstance(entry, dict) else []
    template_id = (entry or {}).get("templateId") or fallback_template
    version = (entry or {}).get("version") or None
    updated_at = (entry or {}).get("updatedAt") or version
    return {
        "templateId": template_id,
        "version": version,
        "updatedAt": updated_at,
        "blocksCount": len(blocks) if isinstance(blocks, list) else 0,
        "hasContent": bool(blocks),
    }


def get_page(slug: str = DEFAULT_SLUG, *, raise_on_error: bool = False) -> dict[str, Any]:
    try:
        with get_session() as session:
            return _get_page(session, slug)
    except Exception:
        safe_slug = slug or DEFAULT_SLUG
        if raise_on_error:
            raise
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
            blocks={
                "draft": _wrap_state(_default_blocks(), template_id=DEFAULT_TEMPLATE_ID),
                "published": _wrap_state(_default_blocks(), template_id=DEFAULT_TEMPLATE_ID),
            },
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
        raise HTTPException(status_code=422, detail="Invalid page payload")

    theme_payload = payload.get("theme") if isinstance(payload, dict) else None
    theme_data = data.theme.model_dump(by_alias=True) if theme_payload is not None else {}

    try:
        with get_session() as session:
            page = (
                session.execute(select(AdminSitePage).where(AdminSitePage.slug == safe_slug))
                .scalars()
                .first()
            )

            draft_state = _wrap_state(
                data.model_dump(by_alias=True).get("blocks", _default_blocks()),
                template_id=data.template_id or DEFAULT_TEMPLATE_ID,
            )

            if not page:
                page = AdminSitePage(
                    slug=safe_slug,
                    template_id=data.template_id or DEFAULT_TEMPLATE_ID,
                    blocks={
                        "draft": draft_state,
                        "published": draft_state,
                    },
                    theme=theme_data,
                )
                session.add(page)
            else:
                page.template_id = data.template_id or DEFAULT_TEMPLATE_ID
                existing_blocks = page.blocks if isinstance(page.blocks, dict) else {}
                published_state = existing_blocks.get("published") if isinstance(existing_blocks, dict) else None
                page.blocks = {
                    "draft": draft_state,
                    "published": published_state or draft_state,
                }
                if theme_payload is not None:
                    page.theme = theme_data
                page.updated_at = datetime.utcnow()

            session.commit()
            session.refresh(page)
            return _serialize(page, safe_slug)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update AdminSite page %s, returning minimal state", safe_slug)
        raise HTTPException(status_code=500, detail="Failed to save page")


def publish_page(slug: str = DEFAULT_SLUG) -> dict[str, Any]:
    safe_slug = slug or DEFAULT_SLUG
    with get_session() as session:
        page = (
            session.execute(select(AdminSitePage).where(AdminSitePage.slug == safe_slug))
            .scalars()
            .first()
        )

        if not page:
            _get_page(session, safe_slug)
            page = (
                session.execute(select(AdminSitePage).where(AdminSitePage.slug == safe_slug))
                .scalars()
                .first()
            )
            if not page:
                raise HTTPException(status_code=404, detail="Page not found")

        draft, _published = _extract_states(page, safe_slug)
        if not draft.get("blocks"):
            raise HTTPException(status_code=422, detail="Draft is empty")

        page.blocks = {"draft": draft, "published": draft}
        page.updated_at = datetime.utcnow()
        session.add(page)
        session.commit()
        session.refresh(page)
        return _serialize(page, safe_slug)


def get_published_page(slug: str = DEFAULT_SLUG) -> dict[str, Any]:
    safe_slug = slug or DEFAULT_SLUG
    with get_session() as session:
        page = (
            session.execute(select(AdminSitePage).where(AdminSitePage.slug == safe_slug))
            .scalars()
            .first()
        )

        if not page:
            raise HTTPException(status_code=404, detail="Page not found")

        _draft, published = _extract_states(page, safe_slug)
        payload = {
            "pageKey": safe_slug,
            "templateId": published.get("templateId") or page.template_id or DEFAULT_TEMPLATE_ID,
            "version": published.get("version") or page.updated_at.isoformat(),
            "updatedAt": published.get("updatedAt") or published.get("version"),
            "blocks": published.get("blocks") or _default_blocks(),
            "theme": page.theme if isinstance(page.theme, dict) else {},
        }
        return payload


def get_page_health(slug: str = DEFAULT_SLUG) -> dict[str, Any]:
    payload = get_page(slug)
    draft_state = payload.get("draft") or {}
    published_state = payload.get("published") or {}
    template_id = payload.get("templateId") or DEFAULT_TEMPLATE_ID
    draft_summary = _summarize_state(draft_state, fallback_template=template_id)
    published_summary = _summarize_state(published_state, fallback_template=template_id)
    return {
        "pageKey": payload.get("pageKey") or slug or DEFAULT_SLUG,
        "draft": draft_summary,
        "published": published_summary,
        "hasUnpublishedChanges": draft_summary != published_summary,
        "theme": payload.get("theme") or {},
    }


__all__ = [
    "get_page",
    "get_published_page",
    "get_page_health",
    "publish_page",
    "update_page",
    "DEFAULT_TEMPLATE_ID",
]
