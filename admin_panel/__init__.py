"""Минимальная веб-админка для AdminBot и AdminSite."""

from pathlib import Path

try:
    import jinja2  # noqa: F401
except ImportError as import_error:  # pragma: no cover - defensive guard
    raise ImportError("Jinja2Templates requires jinja2. Install it via `pip install jinja2`.") from import_error

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
# Все статические ассеты AdminSite/constructor лежат в admin_panel/adminsite/static
STATIC_DIR = BASE_DIR / "adminsite" / "static"
