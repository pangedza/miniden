from __future__ import annotations

from datetime import datetime
from typing import Optional

HOME_PLACEHOLDER_URL = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 360'>"
    "<defs><linearGradient id='g' x1='0' x2='1' y1='0' y2='1'>"
    "<stop offset='0%' stop-color='%23f3e7e9'/><stop offset='100%' stop-color='%23e3eeff'/>"
    "</linearGradient></defs>"
    "<rect width='600' height='360' rx='24' fill='url(%23g)'/>"
    "<rect x='160' y='120' width='280' height='120' rx='18' fill='rgba(0,0,0,0.05)'/>"
    "<rect x='200' y='150' width='200' height='12' rx='6' fill='rgba(0,0,0,0.16)'/>"
    "<rect x='200' y='170' width='160' height='12' rx='6' fill='rgba(0,0,0,0.12)'/>"
    "<rect x='200' y='190' width='120' height='12' rx='6' fill='rgba(0,0,0,0.08)'/>"
    "</svg>"
)


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
