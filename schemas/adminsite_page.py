from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


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


PageBlock = Annotated[
    Union[HeroBlock, CardsBlock, TextBlock, SocialBlock],
    Field(discriminator="type"),
]


class PageConfig(BaseModel):
    template_id: str = Field(default="services", alias="templateId")
    blocks: list[PageBlock] = Field(default_factory=list)
    theme: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
