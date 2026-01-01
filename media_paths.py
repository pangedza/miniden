from __future__ import annotations

from pathlib import Path

MEDIA_ROOT = Path("/opt/miniden/media")
ADMIN_SITE_MEDIA_ROOT = MEDIA_ROOT / "adminsite"
ADMIN_BOT_MEDIA_ROOT = MEDIA_ROOT / "adminbot"

REQUIRED_MEDIA_DIRS = [
    MEDIA_ROOT,
    ADMIN_SITE_MEDIA_ROOT,
    ADMIN_BOT_MEDIA_ROOT,
    MEDIA_ROOT / "users",
    MEDIA_ROOT / "products",
    MEDIA_ROOT / "courses",
    MEDIA_ROOT / "categories",
    MEDIA_ROOT / "home",
    MEDIA_ROOT / "reviews",
    MEDIA_ROOT / "branding",
    MEDIA_ROOT / "tmp",
    MEDIA_ROOT / "tmp/products",
    MEDIA_ROOT / "tmp/courses",
]


def ensure_media_dirs() -> None:
    for directory in REQUIRED_MEDIA_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
