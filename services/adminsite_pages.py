from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_session
from models import AdminSitePage
from utils.home_images import HOME_PLACEHOLDER_URL
from schemas.adminsite_page import PageConfig

DEFAULT_TEMPLATE_ID = "services"
DEFAULT_SLUG = "home"


def _default_blocks() -> list[dict[str, Any]]:
    return [
        {
            "type": "hero",
            "title": "Витрина AdminSite",
            "subtitle": "Настройте оформление и блоки под свои задачи.",
            "imageUrl": HOME_PLACEHOLDER_URL,
            "background": {
                "type": "gradient",
                "value": "linear-gradient(135deg, rgba(255,255,255,0.12), rgba(0,0,0,0.04))",
            },
        },
        {
            "type": "cards",
            "title": "Подборка",
            "subtitle": "Карточки можно использовать для товаров, услуг или ссылок.",
            "layout": {"columns": 2},
            "items": [],
        },
        {
            "type": "text",
            "title": "Описание",
            "text": "Добавьте короткое описание компании или продукта.",
        },
        {
            "type": "social",
            "items": [],
        },
    ]


def _normalize_page(page: AdminSitePage | None) -> PageConfig:
    if not page:
        return PageConfig(template_id=DEFAULT_TEMPLATE_ID, blocks=_default_blocks())

    template_id = page.template_id or DEFAULT_TEMPLATE_ID
    raw_blocks = page.blocks or []
    theme = page.theme or {}

    config = PageConfig(template_id=template_id, blocks=raw_blocks, theme=theme)
    return config


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
    with get_session() as session:
        return _get_page(session, slug)


def _get_page(session: Session, slug: str) -> dict[str, Any]:
    page = (
        session.execute(
            select(AdminSitePage).where(AdminSitePage.slug == (slug or DEFAULT_SLUG))
        )
        .scalars()
        .first()
    )

    if not page:
        page = AdminSitePage(
            slug=slug or DEFAULT_SLUG,
            template_id=DEFAULT_TEMPLATE_ID,
            blocks=_default_blocks(),
        )
        session.add(page)
        session.commit()
        session.refresh(page)

    return _serialize(page, slug)


def update_page(payload: dict[str, Any], slug: str = DEFAULT_SLUG) -> dict[str, Any]:
    data = PageConfig.model_validate(payload)
    theme_payload = payload.get("theme") if isinstance(payload, dict) else None

    with get_session() as session:
        page = (
            session.execute(
                select(AdminSitePage).where(AdminSitePage.slug == (slug or DEFAULT_SLUG))
            )
            .scalars()
            .first()
        )

        if not page:
            page = AdminSitePage(
                slug=slug or DEFAULT_SLUG,
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
        return _serialize(page, slug)


__all__ = ["get_page", "update_page", "DEFAULT_TEMPLATE_ID"]
