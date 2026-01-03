from __future__ import annotations

import json
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BackgroundConfig(BaseModel):
    type: Literal["color", "gradient", "image"] = "color"
    value: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class LayoutConfig(BaseModel):
    columns: Literal[1, 2, 3] = 2

    model_config = ConfigDict(populate_by_name=True)


class HeroBlock(BaseModel):
    type: Literal["hero"] = "hero"
    title: str
    subtitle: str | None = None
    image_url: str | None = Field(default=None, alias="imageUrl")
    background: BackgroundConfig = Field(default_factory=BackgroundConfig)

    model_config = ConfigDict(populate_by_name=True)


class CardItem(BaseModel):
    title: str
    image_url: str | None = Field(default=None, alias="imageUrl")
    href: str | None = None
    icon: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class CardsBlock(BaseModel):
    type: Literal["cards"] = "cards"
    title: str | None = None
    subtitle: str | None = None
    items: list[CardItem] = Field(default_factory=list)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)

    model_config = ConfigDict(populate_by_name=True)


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    title: str | None = None
    text: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class SocialItem(BaseModel):
    type: Literal[
        "telegram",
        "whatsapp",
        "vk",
        "instagram",
        "website",
        "phone",
        "email",
    ]
    label: str
    href: str
    icon: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class SocialBlock(BaseModel):
    type: Literal["social"] = "social"
    items: list[SocialItem] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class CategoryRef(BaseModel):
    title: str | None = None
    slug: str | None = None
    type: Literal["product", "course"] | None = "product"
    url: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class CategoriesBlock(BaseModel):
    type: Literal["categories"] = "categories"
    title: str | None = None
    subtitle: str | None = None
    items: list[CategoryRef] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


PageBlock = Annotated[
    Union[HeroBlock, CardsBlock, TextBlock, SocialBlock, CategoriesBlock],
    Field(discriminator="type"),
]


class StylePreset(BaseModel):
    card_border: bool | str | None = Field(default=None, alias="cardBorder")
    button_style: str | None = Field(default=None, alias="buttonStyle")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("card_border", mode="before")
    @classmethod
    def parse_card_border(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1"}:
                return True
            if normalized in {"false", "0"}:
                return False
        return value


class ThemeConfig(BaseModel):
    applied_template_id: str | None = Field(default=None, alias="appliedTemplateId")
    css_vars: dict[str, Any] = Field(default_factory=dict, alias="cssVars")
    style_preset: StylePreset | None = Field(
        default_factory=StylePreset, alias="stylePreset"
    )
    timestamp: int | str | None = None
    updated_at: str | None = Field(default=None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)

    @staticmethod
    def _normalize_mapping(value: Any) -> dict[str, Any]:
        if isinstance(value, StylePreset):
            return value.model_dump(by_alias=True, exclude_none=True)
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    @field_validator("css_vars", "style_preset", mode="before")
    @classmethod
    def parse_theme_mapping(cls, value: Any) -> dict[str, Any]:
        return cls._normalize_mapping(value)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value: Any) -> int | str | None:
        if value is None:
            return None
        if isinstance(value, (int, str)):
            try:
                return int(value)
            except Exception:
                return value
        return None


class PageConfig(BaseModel):
    template_id: str = Field(default="services", alias="templateId")
    blocks: list[PageBlock] = Field(default_factory=list)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)

    model_config = ConfigDict(populate_by_name=True)
