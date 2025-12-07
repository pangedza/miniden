from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HomeBannerIn(BaseModel):
    title: str
    subtitle: str | None = None
    button_text: str | None = None
    button_link: str | None = None
    image_url: str | None = None
    is_active: bool = True
    sort_order: int = 0


class HomeBannerOut(HomeBannerIn):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

