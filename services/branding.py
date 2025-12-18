from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import SiteBranding


def get_or_create_branding(session: Session) -> SiteBranding:
    branding = session.execute(select(SiteBranding)).scalars().first()
    if branding:
        return branding

    branding = SiteBranding()
    session.add(branding)
    session.flush()
    return branding


def serialize_branding(branding: SiteBranding) -> dict[str, Any]:
    return {
        "site_title": branding.site_title,
        "logo_url": branding.logo_url,
        "favicon_url": branding.favicon_url,
        "assets_version": branding.assets_version or 1,
    }


def update_branding_record(
    branding: SiteBranding,
    *,
    site_title: str | None = None,
    logo_url: str | None = None,
    favicon_url: str | None = None,
    bump_assets: bool = False,
) -> SiteBranding:
    if site_title is not None:
        branding.site_title = site_title.strip() or None
    if logo_url is not None:
        branding.logo_url = logo_url
    if favicon_url is not None:
        branding.favicon_url = favicon_url
    if bump_assets:
        branding.assets_version = (branding.assets_version or 1) + 1
    branding.updated_at = datetime.utcnow()
    return branding
