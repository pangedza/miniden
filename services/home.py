from __future__ import annotations

from datetime import datetime

from sqlalchemy import asc, desc, select

from database import get_session
from models import HomeBanner, HomePost, HomeSection
from utils.home_images import append_cache_busting, image_version_from_timestamp, normalize_home_image_url
from schemas.home import HomeBlockIn, HomeBlockOut, HomePostIn, HomePostOut, HomeSectionIn, HomeSectionOut


def _model_to_out(instance, schema_cls):
    if not instance:
        return None
    return schema_cls.from_orm(instance)


def _augment_image_fields(block: HomeBlockOut | None) -> HomeBlockOut | None:
    if not block:
        return None
    block.image_url = normalize_home_image_url(block.image_url)
    block.image_version = image_version_from_timestamp(getattr(block, "updated_at", None))
    block.image_url_with_version = append_cache_busting(block.image_url, getattr(block, "updated_at", None))
    return block


def get_active_home_data() -> dict[str, list]:
    """Legacy aggregator: returns blocks, sections and posts."""
    return {
        "blocks": [block.dict() for block in list_blocks(include_inactive=False)],
        "sections": [HomeSectionOut.from_orm(item).dict() for item in _list_sections(False)],
        "posts": [HomePostOut.from_orm(item).dict() for item in _list_posts(False)],
    }


def _list_blocks_query(include_inactive: bool):
    query = select(HomeBanner).order_by(asc(HomeBanner.sort_order), asc(HomeBanner.id))
    if not include_inactive:
        query = query.where(HomeBanner.is_active.is_(True))
    return query


def list_blocks(include_inactive: bool = True) -> list[HomeBlockOut]:
    with get_session() as session:
        rows = session.execute(_list_blocks_query(include_inactive)).scalars().all()
        return [_augment_image_fields(HomeBlockOut.from_orm(item)) for item in rows]


def get_block(block_id: int) -> HomeBlockOut | None:
    with get_session() as session:
        banner = session.get(HomeBanner, block_id)
        return _augment_image_fields(_model_to_out(banner, HomeBlockOut))


def create_block(payload: HomeBlockIn) -> HomeBlockOut:
    with get_session() as session:
        payload_dict = payload.model_dump(by_alias=True)
        payload_dict["image_url"] = normalize_home_image_url(payload_dict.get("image_url"))
        record = HomeBanner(**payload_dict)
        session.add(record)
        session.flush()
        session.refresh(record)
        return _augment_image_fields(HomeBlockOut.from_orm(record))


def update_block(block_id: int, payload: HomeBlockIn) -> HomeBlockOut | None:
    with get_session() as session:
        banner = session.get(HomeBanner, block_id)
        if not banner:
            return None
        for key, value in payload.model_dump(by_alias=True).items():
            if key == "image_url":
                value = normalize_home_image_url(value)
            setattr(banner, key, value)
        banner.updated_at = datetime.utcnow()
        session.flush()
        session.refresh(banner)
        return _augment_image_fields(HomeBlockOut.from_orm(banner))


def delete_block(block_id: int) -> bool:
    with get_session() as session:
        banner = session.get(HomeBanner, block_id)
        if not banner:
            return False
        session.delete(banner)
        return True


# Backwards-compatible aliases
def list_banners(include_inactive: bool = True) -> list[HomeBlockOut]:
    return list_blocks(include_inactive)


def get_banner(banner_id: int) -> HomeBlockOut | None:
    return get_block(banner_id)


def create_banner(payload: HomeBlockIn) -> HomeBlockOut:
    return create_block(payload)


def update_banner(banner_id: int, payload: HomeBlockIn) -> HomeBlockOut | None:
    return update_block(banner_id, payload)


def delete_banner(banner_id: int) -> bool:
    return delete_block(banner_id)


# Section CRUD
def list_sections(include_inactive: bool = True) -> list[HomeSectionOut]:
    rows = _list_sections(include_inactive)
    return [HomeSectionOut.from_orm(item) for item in rows]


def _list_sections(include_inactive: bool = True):
    with get_session() as session:
        query = select(HomeSection).order_by(asc(HomeSection.sort_order), asc(HomeSection.id))
        if not include_inactive:
            query = query.where(HomeSection.is_active.is_(True))
        return session.execute(query).scalars().all()


def get_section(section_id: int) -> HomeSectionOut | None:
    with get_session() as session:
        section = session.get(HomeSection, section_id)
        return _model_to_out(section, HomeSectionOut)


def create_section(payload: HomeSectionIn) -> HomeSectionOut:
    with get_session() as session:
        record = HomeSection(**payload.dict())
        session.add(record)
        session.flush()
        session.refresh(record)
        return HomeSectionOut.from_orm(record)


def update_section(section_id: int, payload: HomeSectionIn) -> HomeSectionOut | None:
    with get_session() as session:
        section = session.get(HomeSection, section_id)
        if not section:
            return None
        for key, value in payload.dict().items():
            setattr(section, key, value)
        session.flush()
        session.refresh(section)
        return HomeSectionOut.from_orm(section)


def delete_section(section_id: int) -> bool:
    with get_session() as session:
        section = session.get(HomeSection, section_id)
        if not section:
            return False
        session.delete(section)
        return True


# Post CRUD
def list_posts(include_inactive: bool = True) -> list[HomePostOut]:
    rows = _list_posts(include_inactive)
    return [HomePostOut.from_orm(item) for item in rows]


def _list_posts(include_inactive: bool = True):
    with get_session() as session:
        query = select(HomePost).order_by(asc(HomePost.sort_order), desc(HomePost.created_at))
        if not include_inactive:
            query = query.where(HomePost.is_active.is_(True))
        return session.execute(query).scalars().all()


def get_post(post_id: int) -> HomePostOut | None:
    with get_session() as session:
        post = session.get(HomePost, post_id)
        return _model_to_out(post, HomePostOut)


def create_post(payload: HomePostIn) -> HomePostOut:
    with get_session() as session:
        record = HomePost(**payload.dict())
        session.add(record)
        session.flush()
        session.refresh(record)
        return HomePostOut.from_orm(record)


def update_post(post_id: int, payload: HomePostIn) -> HomePostOut | None:
    with get_session() as session:
        post = session.get(HomePost, post_id)
        if not post:
            return None
        for key, value in payload.dict().items():
            setattr(post, key, value)
        session.flush()
        session.refresh(post)
        return HomePostOut.from_orm(post)


def delete_post(post_id: int) -> bool:
    with get_session() as session:
        post = session.get(HomePost, post_id)
        if not post:
            return False
        session.delete(post)
        return True

