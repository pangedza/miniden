from __future__ import annotations

from datetime import datetime
from typing import Optional

HOME_PLACEHOLDER_URL = "/static/img/home-placeholder.svg"


def normalize_home_image_url(url: str | None) -> str | None:
    if not url:
        return None
    trimmed = url.strip()
    if not trimmed:
        return None
    if trimmed.startswith("http://"):
        return "https://" + trimmed[len("http://") :]
    return trimmed


def image_version_from_timestamp(value: datetime | None) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value.timestamp())
    except (OverflowError, OSError, ValueError):
        return None


def append_cache_busting(image_url: str | None, updated_at: datetime | None) -> str | None:
    base_url = normalize_home_image_url(image_url)
    version = image_version_from_timestamp(updated_at)
    if not base_url:
        return None
    if not version:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}v={version}"
