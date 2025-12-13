from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HomeBlockBase(BaseModel):
    block_key: str | None = None
    title: str
    subtitle: str | None = None
    body: str | None = None
    button_text: str | None = None
    button_url: str | None = Field(default=None, alias="button_link")
    image_url: str | None = None
    is_active: bool = True
    order: int = Field(default=0, alias="sort_order")


class HomeBlockIn(HomeBlockBase):
    model_config = ConfigDict(populate_by_name=True)


class HomeBlockOut(HomeBlockBase):
    id: int
    created_at: datetime
    updated_at: datetime
    image_version: int | None = None
    image_url_with_version: str | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class HomeSectionIn(BaseModel):
    slug: str
    title: str
    text: str
    icon: str | None = None
    sort_order: int = 0
    is_active: bool = True


class HomeSectionOut(HomeSectionIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


class HomePostIn(BaseModel):
    title: str
    short_text: str
    link: str | None = None
    is_active: bool = True
    sort_order: int = 0


class HomePostOut(HomePostIn):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

