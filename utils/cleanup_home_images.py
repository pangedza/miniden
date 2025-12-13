from __future__ import annotations

"""Утилита для очистки ссылок картинок главной страницы."""

from sqlalchemy import select

from database import get_session
from models import HomeBanner
from utils.home_images import HOME_PLACEHOLDER_URL, normalize_home_image_url


UNSPLASH_MARKER = "unsplash.com"


def cleanup_unsplash_banners(placeholder: str = HOME_PLACEHOLDER_URL, dry_run: bool = False) -> int:
    """Заменяет ссылки unsplash.com на локальный плейсхолдер.

    Args:
        placeholder: Локальный URL, который нужно установить вместо внешнего.
        dry_run: Если True, изменения не сохраняются в БД.

    Returns:
        Количество обновлённых записей.
    """

    updated = 0
    normalized_placeholder = normalize_home_image_url(placeholder)

    with get_session() as session:
        banners = session.execute(select(HomeBanner)).scalars().all()
        for banner in banners:
            current_url = (banner.image_url or "").strip()
            if UNSPLASH_MARKER in current_url:
                banner.image_url = normalized_placeholder
                updated += 1
        if dry_run:
            session.rollback()
            return updated
    return updated


if __name__ == "__main__":
    count = cleanup_unsplash_banners()
    print(f"Updated {count} home banner images")
