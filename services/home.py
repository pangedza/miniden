from __future__ import annotations

from sqlalchemy import asc, desc, select

from database import get_session
from models import HomeBanner, HomePost, HomeSection
from schemas.home import HomeBannerIn, HomeBannerOut, HomePostIn, HomePostOut, HomeSectionIn, HomeSectionOut


def _model_to_out(instance, schema_cls):
    if not instance:
        return None
    return schema_cls.from_orm(instance)


def get_active_home_data() -> dict[str, list]:
    with get_session() as session:
        banners = (
            session.execute(
                select(HomeBanner)
                .where(HomeBanner.is_active.is_(True))
                .order_by(asc(HomeBanner.sort_order), asc(HomeBanner.created_at))
            )
            .scalars()
            .all()
        )
        sections = (
            session.execute(
                select(HomeSection)
                .where(HomeSection.is_active.is_(True))
                .order_by(asc(HomeSection.sort_order), asc(HomeSection.id))
            )
            .scalars()
            .all()
        )
        posts = (
            session.execute(
                select(HomePost)
                .where(HomePost.is_active.is_(True))
                .order_by(asc(HomePost.sort_order), desc(HomePost.created_at))
            )
            .scalars()
            .all()
        )

    return {
        "banners": [HomeBannerOut.from_orm(item).dict() for item in banners],
        "sections": [HomeSectionOut.from_orm(item).dict() for item in sections],
        "posts": [HomePostOut.from_orm(item).dict() for item in posts],
    }


# Banner CRUD
def list_banners(include_inactive: bool = True) -> list[HomeBannerOut]:
    with get_session() as session:
        query = select(HomeBanner).order_by(asc(HomeBanner.sort_order), asc(HomeBanner.created_at))
        if not include_inactive:
            query = query.where(HomeBanner.is_active.is_(True))
        rows = session.execute(query).scalars().all()
        return [HomeBannerOut.from_orm(item) for item in rows]


def get_banner(banner_id: int) -> HomeBannerOut | None:
    with get_session() as session:
        banner = session.get(HomeBanner, banner_id)
        return _model_to_out(banner, HomeBannerOut)


def create_banner(payload: HomeBannerIn) -> HomeBannerOut:
    with get_session() as session:
        record = HomeBanner(**payload.dict())
        session.add(record)
        session.flush()
        session.refresh(record)
        return HomeBannerOut.from_orm(record)


def update_banner(banner_id: int, payload: HomeBannerIn) -> HomeBannerOut | None:
    with get_session() as session:
        banner = session.get(HomeBanner, banner_id)
        if not banner:
            return None
        for key, value in payload.dict().items():
            setattr(banner, key, value)
        session.flush()
        session.refresh(banner)
        return HomeBannerOut.from_orm(banner)


def delete_banner(banner_id: int) -> bool:
    with get_session() as session:
        banner = session.get(HomeBanner, banner_id)
        if not banner:
            return False
        session.delete(banner)
        return True


# Section CRUD
def list_sections(include_inactive: bool = True) -> list[HomeSectionOut]:
    with get_session() as session:
        query = select(HomeSection).order_by(asc(HomeSection.sort_order), asc(HomeSection.id))
        if not include_inactive:
            query = query.where(HomeSection.is_active.is_(True))
        rows = session.execute(query).scalars().all()
        return [HomeSectionOut.from_orm(item) for item in rows]


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
    with get_session() as session:
        query = select(HomePost).order_by(asc(HomePost.sort_order), desc(HomePost.created_at))
        if not include_inactive:
            query = query.where(HomePost.is_active.is_(True))
        rows = session.execute(query).scalars().all()
        return [HomePostOut.from_orm(item) for item in rows]


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

