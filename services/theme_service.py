from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from database import get_session
from models import AdminSitePage
from services import adminsite_pages
from services.theme_templates import (
    DEFAULT_TEMPLATE_ID,
    TEMPLATES,
    ThemeTemplate,
    get_template_by_id,
)

DEFAULT_VARS: dict[str, str] = {
    "bg": "#f5f6fb",
    "text": "#1f2937",
    "muted": "#6b7280",
    "card-bg": "#ffffff",
    "accent": "#2563eb",
    "radius": "16px",
    "shadow": "0 16px 40px rgba(15, 23, 42, 0.12)",
    "font": '"Inter", system-ui, sans-serif',
}


class ThemeApplyError(RuntimeError):
    """Raised when theme cannot be applied."""


def _normalize_template(template_id: str | None) -> ThemeTemplate:
    resolved = get_template_by_id(template_id)
    if resolved:
        return resolved
    fallback = get_template_by_id(DEFAULT_TEMPLATE_ID)
    if fallback:
        return fallback
    return TEMPLATES[0]


def _build_css_vars(template: ThemeTemplate, *, existing: dict[str, Any] | None = None) -> dict[str, str]:
    css_vars = {**DEFAULT_VARS, **(template.css_vars or {})}
    if existing:
        css_vars.update({k: v for k, v in (existing.get("cssVars") or {}).items() if v is not None})

    card_border_color = (
        "rgba(0,0,0,0.08)"
        if (template.style_preset or {}).get("cardBorder")
        else "transparent"
    )

    css_vars["card-border-color"] = card_border_color
    css_vars.update(
        {
            "color-bg": "var(--bg)",
            "color-bg-card": "var(--card-bg)",
            "color-bg-card-elevated": "var(--card-bg)",
            "color-text-main": "var(--text)",
            "color-text-muted": "var(--muted)",
            "color-border-subtle": "var(--card-border-color)",
            "nav-surface": "var(--card-bg)",
            "nav-border": "var(--card-border-color)",
            "shadow-strong": "var(--shadow)",
            "radius-card": "var(--radius)",
            "radius-tile": "calc(var(--radius) + 6px)",
            "radius-button": "calc(var(--radius) - 4px)",
            "tile-gradient": "linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0))",
            "surface-primary": "var(--card-bg)",
            "surface-secondary": "var(--card-bg)",
            "color-accent-primary": "var(--accent)",
            "color-accent-primary-strong": "var(--accent)",
            "color-accent-secondary": "var(--accent)",
            "color-accent-secondary-strong": "var(--accent)",
            "color-accent-success": "#3bb273",
            "color-btn-on-accent": "#0b0c10",
        }
    )
    return css_vars


def _ensure_home_page(session) -> AdminSitePage:
    page = (
        session.execute(
            select(AdminSitePage).where(AdminSitePage.slug == adminsite_pages.DEFAULT_SLUG)
        )
        .scalars()
        .first()
    )
    if page:
        return page

    adminsite_pages.get_page(adminsite_pages.DEFAULT_SLUG)
    return (
        session.execute(
            select(AdminSitePage).where(AdminSitePage.slug == adminsite_pages.DEFAULT_SLUG)
        )
        .scalars()
        .first()
    )


def _persist_theme_state(template: ThemeTemplate, theme_state: dict[str, Any]) -> None:
    with get_session() as session:
        page = _ensure_home_page(session)
        page.template_id = template.id
        page.theme = {
            "appliedTemplateId": template.id,
            "timestamp": theme_state.get("timestamp"),
            "updatedAt": theme_state.get("updatedAt"),
            "cssVars": theme_state.get("cssVars", {}),
            "stylePreset": theme_state.get("stylePreset", {}),
        }
        page.updated_at = datetime.utcnow()
        session.add(page)


def _build_theme_state(template: ThemeTemplate, *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    css_vars = _build_css_vars(template, existing=existing)
    updated_at = datetime.utcnow().isoformat()
    timestamp = int(datetime.utcnow().timestamp())
    return {
        "appliedTemplateId": template.id,
        "timestamp": timestamp,
        "updatedAt": updated_at,
        "cssVars": css_vars,
        "stylePreset": template.style_preset or {},
    }


def apply_theme(template_id: str | None) -> dict[str, Any]:
    template = _normalize_template(template_id)
    try:
        theme_state = _build_theme_state(template)
        _persist_theme_state(template, theme_state)
    except Exception as exc:  # pragma: no cover - defensive
        raise ThemeApplyError(str(exc)) from exc

    return theme_state


def get_theme_metadata() -> dict[str, Any]:
    with get_session() as session:
        page = _ensure_home_page(session)
        theme_data = page.theme or {}

    template_id = (
        theme_data.get("appliedTemplateId")
        or theme_data.get("templateId")
        or theme_data.get("template_id")
        or page.template_id
        or DEFAULT_TEMPLATE_ID
    )
    template = _normalize_template(template_id)

    merged = {
        "appliedTemplateId": template.id,
        "timestamp": theme_data.get("timestamp"),
        "updatedAt": theme_data.get("updatedAt"),
        "stylePreset": theme_data.get("stylePreset") or template.style_preset or {},
    }
    merged["cssVars"] = _build_css_vars(template, existing=theme_data)

    if not merged.get("timestamp"):
        merged["timestamp"] = int(datetime.utcnow().timestamp())
    if not merged.get("updatedAt"):
        merged["updatedAt"] = datetime.utcnow().isoformat()

    return merged


__all__ = [
    "apply_theme",
    "get_theme_metadata",
    "DEFAULT_TEMPLATE_ID",
    "ThemeApplyError",
]
