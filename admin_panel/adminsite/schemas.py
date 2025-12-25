from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

TypeLiteral = str
ScopeLiteral = Literal["global", "category"]
SlugPattern = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class CategoryPayload(BaseModel):
    type: TypeLiteral
    title: str
    slug: str | None = Field(default=None, pattern=SlugPattern)
    parent_id: int | None = None
    is_active: bool = True
    sort: int = 0


class CategoryUpdatePayload(BaseModel):
    type: TypeLiteral | None = None
    title: str | None = None
    slug: str | None = Field(default=None, pattern=SlugPattern)
    parent_id: int | None = None
    is_active: bool | None = None
    sort: int | None = None

    model_config = ConfigDict(extra="ignore")


class CategoryResponse(BaseModel):
    id: int
    type: TypeLiteral
    title: str
    slug: str
    parent_id: int | None
    is_active: bool
    sort: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemPayload(BaseModel):
    type: TypeLiteral
    category_id: int
    title: str
    slug: str | None = Field(default=None, pattern=SlugPattern)
    price: Decimal = Field(ge=0)
    image_url: str | None = None
    short_text: str | None = None
    description: str | None = None
    is_active: bool = True
    sort: int = 0

    @field_validator("price", mode="before")
    def _coerce_price(cls, value: Decimal | str | int) -> Decimal:
        return Decimal(value)


class ItemUpdatePayload(BaseModel):
    type: TypeLiteral | None = None
    category_id: int | None = None
    title: str | None = None
    slug: str | None = Field(default=None, pattern=SlugPattern)
    price: Decimal | None = Field(default=None, ge=0)
    image_url: str | None = None
    short_text: str | None = None
    description: str | None = None
    is_active: bool | None = None
    sort: int | None = None

    model_config = ConfigDict(extra="ignore")

    @field_validator("price", mode="before")
    def _coerce_price(cls, value: Decimal | str | int | None) -> Decimal | None:
        if value is None:
            return None
        return Decimal(value)


class ItemResponse(BaseModel):
    id: int
    type: TypeLiteral
    category_id: int
    title: str
    slug: str
    price: Decimal
    image_url: str | None
    short_text: str | None
    description: str | None
    is_active: bool
    sort: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebAppSettingsPayload(BaseModel):
    scope: ScopeLiteral
    type: TypeLiteral
    category_id: int | None = None
    action_enabled: bool = True
    action_label: str | None = "Оформить"
    min_selected: int = Field(1, ge=0)

    @field_validator("category_id")
    def _validate_category_scope(
        cls, value: int | None, info: ValidationInfo
    ) -> int | None:
        scope = (info.data or {}).get("scope")
        if scope == "category" and value is None:
            raise ValueError("category_id is required when scope=category")
        if scope == "global" and value is not None:
            raise ValueError("category_id must be null when scope=global")
        return value


class WebAppSettingsResponse(BaseModel):
    id: int
    scope: ScopeLiteral
    type: TypeLiteral
    category_id: int | None
    action_enabled: bool
    action_label: str | None
    min_selected: int

    model_config = ConfigDict(from_attributes=True)
