from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

DEFAULT_TEMPLATE_ID = "linen-sage"


@dataclass(frozen=True)
class ThemeTemplate:
    id: str
    name: str
    description: str
    css_vars: Mapping[str, str]
    style_preset: Mapping[str, Any] | None = None


TEMPLATES: tuple[ThemeTemplate, ...] = (
    ThemeTemplate(
        id="linen-sage",
        name="Linen & Sage",
        description="Спокойная натуральная палитра в льняных и шалфейных тонах.",
        css_vars={
            "bg": "linear-gradient(180deg, #f7f3ec 0%, #edf0e6 100%)",
            "text": "#1f2a20",
            "muted": "#5f6b5f",
            "card-bg": "rgba(255, 255, 255, 0.92)",
            "accent": "#7a8c70",
            "radius": "16px",
            "shadow": "0 16px 44px rgba(47, 63, 47, 0.14)",
            "font": '"Inter", system-ui, sans-serif',
        },
        style_preset={"buttonStyle": "solid", "cardBorder": False},
    ),
    ThemeTemplate(
        id="baskets",
        name="Baskets",
        description="Тёплая палитра для хендмейда и домашних товаров.",
        css_vars={
            "bg": "linear-gradient(180deg, #f9f4ec 0%, #f2e5d7 100%)",
            "text": "#3b342b",
            "muted": "#7a6f64",
            "card-bg": "rgba(255, 255, 255, 0.9)",
            "accent": "#d4a373",
            "radius": "18px",
            "shadow": "0 18px 50px rgba(93, 76, 50, 0.18)",
            "font": '"Inter", system-ui, sans-serif',
        },
        style_preset={"buttonStyle": "pills", "cardBorder": False},
    ),
    ThemeTemplate(
        id="electronics",
        name="Electronics",
        description="Сдержанный графитовый стиль для техники и гаджетов.",
        css_vars={
            "bg": "linear-gradient(145deg, #0f172a 0%, #0b1323 60%, #0a0f1c 100%)",
            "text": "#e5e7eb",
            "muted": "#94a3b8",
            "card-bg": "rgba(30, 41, 59, 0.9)",
            "accent": "#60a5fa",
            "radius": "12px",
            "shadow": "0 18px 48px rgba(0, 0, 0, 0.38)",
            "font": '"Inter", system-ui, sans-serif',
        },
        style_preset={"buttonStyle": "solid", "cardBorder": True},
    ),
    ThemeTemplate(
        id="services",
        name="Services",
        description="Нейтральный светлый пресет для услуг и консультаций.",
        css_vars={
            "bg": "#f5f6fb",
            "text": "#1f2937",
            "muted": "#6b7280",
            "card-bg": "#ffffff",
            "accent": "#2563eb",
            "radius": "16px",
            "shadow": "0 16px 40px rgba(15, 23, 42, 0.12)",
            "font": '"Inter", system-ui, sans-serif',
        },
        style_preset={"buttonStyle": "solid", "cardBorder": False},
    ),
)


def get_template_by_id(template_id: str | None) -> ThemeTemplate | None:
    if not template_id:
        return None
    normalized = str(template_id).strip().lower()
    for template in TEMPLATES:
        if template.id == normalized:
            return template
    return None


__all__ = ["DEFAULT_TEMPLATE_ID", "ThemeTemplate", "TEMPLATES", "get_template_by_id"]
