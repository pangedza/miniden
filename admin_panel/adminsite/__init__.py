"""API and utilities for AdminSite constructor."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

ADMINSITE_DIR = Path(__file__).resolve().parent
ADMINSITE_TEMPLATE_DIR = ADMINSITE_DIR / "templates"
ADMINSITE_STATIC_ROOT = ADMINSITE_DIR / "static"
ADMINSITE_STATIC_DIR = ADMINSITE_STATIC_ROOT / "adminsite"
ADMINSITE_CONSTRUCTOR_PATH = ADMINSITE_STATIC_DIR / "constructor.js"

TEMPLATES = Jinja2Templates(directory=str(ADMINSITE_TEMPLATE_DIR.resolve()))

from admin_panel.adminsite.router import router

__all__ = [
    "ADMINSITE_CONSTRUCTOR_PATH",
    "ADMINSITE_STATIC_DIR",
    "ADMINSITE_STATIC_ROOT",
    "ADMINSITE_TEMPLATE_DIR",
    "TEMPLATES",
    "router",
]

