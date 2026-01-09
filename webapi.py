"""
Основной backend MiniDeN (FastAPI).
Приложение: webapi:app
"""

from __future__ import annotations

from pydantic import BaseModel

import hashlib
import hmac
import json
import mimetypes
import logging
import os
import subprocess
import time
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode
import urllib.request
from uuid import uuid4

from fastapi import (
    Body,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.routing import NoMatchFound
from pydantic import Field
from sqlalchemy.orm import Session

from admin_panel import STATIC_DIR
from admin_panel.adminsite import (
    ADMINSITE_CONSTRUCTOR_PATH,
    ADMINSITE_STATIC_DIR,
    ADMINSITE_STATIC_ROOT,
    router as adminsite_api_router,
)
from admin_panel.adminsite import service as adminsite_service
from admin_panel.dependencies import get_db_session, require_admin
from admin_panel.routes import adminbot, adminsite
from admin_panel.routes import auth as admin_auth
from admin_panel.routes import users as admin_users
from config import get_settings
from database import get_db, get_session, init_db
from media_paths import (
    ADMIN_BOT_MEDIA_ROOT,
    ADMIN_SITE_MEDIA_ROOT,
    MEDIA_ROOT,
    ensure_media_dirs,
)
from models import AuthSession, User
from models.admin_user import AdminRole
from models.support import (
    SupportMessage,
    SupportMessageList,
    SupportSession,
    SupportSessionDetail,
    SupportSessionList,
    WebChatMessagesResponse,
)
from services import admin_notes as admin_notes_service
from services import cart as cart_service
from services import favorites as favorites_service
from services import home as home_service
from services import faq_service
from services import branding as branding_service
from services import orders as orders_service
from services import menu_catalog
from services import products as products_service
from services import promocodes as promocodes_service
from services import reviews as reviews_service
from services import stats as stats_service
from services import user_admin as user_admin_service
from services import user_stats as user_stats_service
from services import users as users_service
from services import webchat_service
from utils import site_chat_storage
from utils.logging_config import API_LOG_FILE, setup_logging
from services.telegram_webapp_auth import authenticate_telegram_webapp_user
from utils.texts import format_order_for_admin
from schemas.home import HomeBlockIn, HomePostIn, HomeSectionIn


BASE_DIR = Path(__file__).resolve().parent
ADMINSITE_STATIC_PATH = ADMINSITE_STATIC_ROOT.resolve()
WEBAPP_DIR = BASE_DIR / "webapp"
STATIC_DIR_PUBLIC = BASE_DIR / "static"
STATIC_UPLOADS_DIR = STATIC_DIR_PUBLIC / "uploads"
setup_logging(log_file=API_LOG_FILE)

app = FastAPI(title="MiniDeN Web API", version="1.0.0")

logger = logging.getLogger(__name__)


def _serve_webapp_index() -> FileResponse:
    return FileResponse(WEBAPP_DIR / "index.html", media_type="text/html")


def _detect_git_commit() -> str:
    env_commit = os.getenv("BUILD_COMMIT")
    if env_commit:
        return env_commit

    repo_dir = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "unknown"
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to detect git commit")
        return "unknown"


BUILD_COMMIT = _detect_git_commit()
BUILD_TIME = os.getenv("BUILD_TIME") or datetime.utcnow().isoformat() + "Z"
SERVICE_NAME = os.getenv("SERVICE_NAME", "miniden-webapi")


class VersionInfo(BaseModel):
    commit: str
    build_time: str
    service_name: str


class LoggingStaticFiles(StaticFiles):
    """StaticFiles wrapper to log each incoming request path."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        logger.info("[static] request path=%s", scope.get("path"))
        return await super().get_response(path, scope)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_build_header(request: Request, call_next):  # type: ignore[override]
    try:
        response = await call_next(request)
    except Exception:
        # Do not interfere with the underlying error handling
        raise

    if not hasattr(response, "headers"):
        return response

    try:
        response.headers["X-Build-Commit"] = BUILD_COMMIT or "unknown"
    except Exception:
        # Best-effort: never let header-setting break the response
        logger.exception("Failed to set X-Build-Commit header")

    return response


@app.get("/api/version", response_model=VersionInfo)
def version() -> VersionInfo:
    return VersionInfo(
        commit=BUILD_COMMIT,
        build_time=BUILD_TIME,
        service_name=SERVICE_NAME,
    )


@app.exception_handler(Exception)
async def json_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: WPS430
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    body_preview = getattr(exc, "body", None)
    logger.warning(
        "Validation failed on %s: errors=%s body_keys=%s",
        request.url.path,
        exc.errors(),
        list(body_preview.keys()) if isinstance(body_preview, dict) else None,
    )

    if request.url.path.startswith("/adminbot"):
        human_fields = {
            "code": "Код узла",
            "title": "Название",
            "node_type": "Тип узла",
            "input_min_len": "Минимальная длина",
            "row": "Ряд",
            "pos": "Позиция",
        }

        rendered_errors: list[str] = []
        for err in exc.errors():
            location = err.get("loc", [])
            field = location[-1] if location else ""
            human_name = human_fields.get(str(field), str(field) or "поле")
            rendered_errors.append(f"{human_name}: {err.get('msg', 'ошибка ввода')}")

        content = """
        <html lang='ru'><head><meta charset='UTF-8'><title>Ошибка ввода</title>
        <style>body{font-family:Arial,sans-serif;padding:24px;background:#f8fafc;color:#0f172a;} .card{max-width:720px;margin:0 auto;border:1px solid #cbd5e1;background:#fff;border-radius:10px;padding:16px;} h2{margin-top:0;} ul{margin:8px 0 0 20px;} a.button{display:inline-block;margin-top:12px;padding:8px 12px;background:#2563eb;color:#fff;border-radius:6px;text-decoration:none;}</style>
        </head><body>
        <div class='card'>
            <h2>Не удалось сохранить данные</h2>
            <p>Пожалуйста, проверьте форму: некоторые поля заполнены некорректно.</p>
            <ul>{errors}</ul>
            <a class='button' href="javascript:history.back()">Вернуться и исправить</a>
        </div>
        </body></html>
        """.replace("{errors}", "".join([f"<li>{item}</li>" for item in rendered_errors]))

        return HTMLResponse(status_code=422, content=content)

    return JSONResponse(status_code=422, content={"detail": _safe_validation_errors(exc)})


def _safe_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    safe_errors = []
    for err in exc.errors():
        loc = err.get("loc", [])
        if isinstance(loc, (list, tuple)):
            safe_loc = [str(item) for item in loc]
        else:
            safe_loc = [str(loc)] if loc else []

        safe_errors.append(
            {
                "loc": safe_loc,
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
        )

    return safe_errors


ALLOWED_TYPES = {"basket", "course"}
ALLOWED_CATEGORY_TYPES = {"basket", "course", "mixed"}

SETTINGS = get_settings()
BOT_TOKEN = SETTINGS.bot_token
AUTH_SESSION_TTL_SECONDS = 600
COOKIE_MAX_AGE = 30 * 24 * 60 * 60
UPLOAD_FOLDERS = {"products", "courses", "categories", "home", "reviews", "uploads"}

BRANDING_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
BRANDING_FAVICON_EXTENSIONS = {".ico", ".png", ".svg"}
BRANDING_LOGO_MAX_MB = 5
BRANDING_FAVICON_MAX_MB = 2

def ensure_upload_dirs() -> None:
    STATIC_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for folder in UPLOAD_FOLDERS:
        (STATIC_UPLOADS_DIR / folder).mkdir(parents=True, exist_ok=True)


def ensure_admin_static_dirs() -> bool:
    try:
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
        (STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
        (STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)
        (STATIC_DIR / "img").mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "Admin static directory is unavailable, skipping mount: %s", exc
        )
        return False

    return True


def log_static_mount() -> None:
    """Validate that url_for('static') is available for AdminSite assets."""

    try:
        url_path = app.url_path_for("static", path="adminsite/base.css")
    except NoMatchFound:
        logger.exception("Static route named 'static' is missing; AdminSite will fail")
        raise
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to validate static mount")
        raise
    else:
        logger.info("AdminSite static mounted at %s", url_path)


def ensure_adminsite_static_dir() -> None:
    """Ensure AdminSite static directory exists before mounting."""

    try:
        ADMINSITE_STATIC_PATH.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "AdminSite static directory is unavailable, continuing mount anyway: %s",
            exc,
        )


ensure_media_dirs()
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
ensure_adminsite_static_dir()
app.mount(
    "/static",
    # AdminSite templates rely on url_for('static', path='adminsite/...').
    LoggingStaticFiles(
        directory=str(STATIC_DIR_PUBLIC),
        packages=[("admin_panel.adminsite", "static")],
        check_dir=False,
    ),
    name="static",
)
log_static_mount()
app.mount("/css", StaticFiles(directory=WEBAPP_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=WEBAPP_DIR / "js"), name="js")
if ensure_admin_static_dirs():
    try:
        app.mount(
            "/admin/static", StaticFiles(directory=STATIC_DIR), name="admin-static"
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "Admin static will not be served because mount failed: %s", exc
        )
else:  # pragma: no cover - defensive
    logger.warning(
        "Admin static will not be served because the directory is missing or unreadable."
    )



# Keep admin/site routers below static mounts so catch-all paths never override /static.
app.include_router(admin_auth.router)
app.include_router(adminbot.router)
app.include_router(adminsite.router)
app.include_router(admin_users.router)
app.include_router(adminsite_api_router)


class WebChatStartPayload(BaseModel):
    session_key: str | None = None
    page: str | None = None
    referrer: str | None = None
    user_identifier: str | None = None

    class Config:
        extra = "ignore"


class WebChatMessagePayload(BaseModel):
    session_key: str | None = None
    text: str | None = None
    user_identifier: str | None = None

    class Config:
        extra = "ignore"


class WebChatManagerReplyPayload(BaseModel):
    session_id: int | None = None
    session_key: str | None = None
    text: str | None = None
    message: str | None = None
    reply: str | None = None


class AdminWebChatSendPayload(BaseModel):
    session_id: int
    text: str


class AdminWebChatClosePayload(BaseModel):
    session_id: int


class MenuCategoryPayload(BaseModel):
    title: str
    slug: str | None = None
    type: str = "product"
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = None
    order_index: int = 0
    is_active: bool = True


class MenuCategoryUpdatePayload(BaseModel):
    title: str | None = None
    slug: str | None = None
    type: str | None = None
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = None
    order_index: int | None = None
    is_active: bool | None = None

    class Config:
        extra = "ignore"


class MenuItemPayload(BaseModel):
    category_id: int
    title: str
    slug: str | None = None
    subtitle: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    images: list[str] = []
    image_url: str | None = None
    legacy_link: str | None = None
    order_index: int = 0
    is_active: bool = True
    stock_qty: int | None = None
    type: str = "product"
    meta: dict[str, Any] = {}


class MenuItemUpdatePayload(BaseModel):
    category_id: int | None = None
    title: str | None = None
    slug: str | None = None
    subtitle: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    images: list[str] | None = None
    image_url: str | None = None
    legacy_link: str | None = None
    order_index: int | None = None
    is_active: bool | None = None
    stock_qty: int | None = None
    type: str | None = None
    meta: dict[str, Any] | None = None

    class Config:
        extra = "ignore"


class MenuReorderEntry(BaseModel):
    id: int
    order_index: int


class MenuReorderPayload(BaseModel):
    categories: list[MenuReorderEntry] = []
    items: list[MenuReorderEntry] = []


class SiteSettingsPayload(BaseModel):
    brand_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    background_color: str | None = None
    contacts: dict[str, Any] = {}
    social_links: dict[str, Any] = {}
    hero_enabled: bool | None = None
    hero_title: str | None = None
    hero_subtitle: str | None = None
    hero_image_url: str | None = None


class SiteBlockPayload(BaseModel):
    page: str
    type: str
    title: str | None = None
    subtitle: str | None = None
    image_url: str | None = None
    payload: dict[str, Any] = {}
    order_index: int = 0
    is_active: bool = True


class SiteBlockUpdatePayload(BaseModel):
    page: str | None = None
    type: str | None = None
    title: str | None = None
    subtitle: str | None = None
    image_url: str | None = None
    payload: dict[str, Any] | None = None
    order_index: int | None = None
    is_active: bool | None = None

    class Config:
        extra = "ignore"


class BlockReorderEntry(BaseModel):
    id: int
    order_index: int


class BlockReorderPayload(BaseModel):
    blocks: list[BlockReorderEntry] = []


class AdminWebChatReadPayload(BaseModel):
    last_read_message_id: int | None = None


class AdminWebChatReplyBody(BaseModel):
    text: str


def _send_message_to_admins(text: str) -> list[int]:
    admin_ids = list(getattr(SETTINGS, "admin_ids", set()) or [])
    primary_admin = getattr(SETTINGS, "admin_chat_id", None)
    if primary_admin and primary_admin not in admin_ids:
        admin_ids.append(primary_admin)

    if not BOT_TOKEN or not admin_ids:
        return []

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    message_ids: list[int] = []

    for chat_id in admin_ids:
        payload = urlencode({"chat_id": chat_id, "text": text}).encode()
        try:
            with urllib.request.urlopen(api_url, data=payload, timeout=10) as response:
                data = json.load(response)
        except Exception:
            logger.exception("Failed to notify admin via Telegram")
            continue

        if data.get("ok"):
            try:
                message_id = int(data["result"]["message_id"])
                message_ids.append(message_id)
            except Exception:
                continue
    return message_ids


def _notify_admin_about_chat(chat_session, preview_text: str) -> list[int]:
    snippet = (preview_text or "")[:200]
    text = (
        f"Новый чат с сайта #{chat_session.id}\n"
        f"Текст: {snippet}\n"
        "Чтобы ответить — ответьте на это сообщение."
    )
    message_ids = _send_message_to_admins(text)
    for message_id in message_ids:
        try:
            site_chat_storage.remember_admin_message(message_id, int(chat_session.id))
        except Exception:
            logger.exception("Failed to persist mapping for admin notification")
    return message_ids


def _save_uploaded_image(
    file: UploadFile, base_folder: str, *, scope: str = "adminsite"
) -> dict[str, Any]:
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Неверный формат изображения")

    base_folder = (base_folder or "").strip("/") or "uploads"
    if base_folder not in UPLOAD_FOLDERS:
        base_folder = "uploads"

    media_root = ADMIN_SITE_MEDIA_ROOT if scope == "adminsite" else ADMIN_BOT_MEDIA_ROOT
    ensure_media_dirs()

    ext = (file.filename or "jpg").split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"

    filename = f"{uuid4().hex}.{ext}"
    target_dir = media_root / base_folder if base_folder else media_root
    target_dir.mkdir(parents=True, exist_ok=True)
    full_path = target_dir / filename

    content = file.file.read()
    with full_path.open("wb") as f:
        f.write(content)

    if not full_path.exists():
        logger.error("Upload write reported success but file is missing: %s", full_path)
        raise HTTPException(
            status_code=500,
            detail="Не удалось сохранить файл на сервер",
        )

    saved_size = len(content)
    content_type = file.content_type or mimetypes.guess_type(full_path.name)[0]
    relative = full_path.relative_to(MEDIA_ROOT).as_posix()
    url = f"/media/{relative}"

    logger.info(
        "Saved upload to %s (size=%s, content_type=%s)",
        full_path,
        saved_size,
        content_type,
    )

    return {
        "url": url,
        "original_name": file.filename or filename,
        "size": saved_size,
        "content_type": content_type or "application/octet-stream",
    }


def _save_branding_file(
    file: UploadFile, allowed_extensions: set[str], max_size_mb: int, prefix: str
) -> str:
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Недопустимый формат файла")

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")

    max_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Файл слишком большой (до {max_size_mb} МБ)")

    ensure_media_dirs()
    target_dir = MEDIA_ROOT / "branding"
    target_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{prefix}_{uuid4().hex}{ext}"
    full_path = target_dir / unique_name
    with full_path.open("wb") as f:
        f.write(content)

    return f"/media/branding/{unique_name}"


def _delete_media_file(url: str | None) -> None:
    if not url:
        return

    try:
        if url.startswith("/media/"):
            target_path = MEDIA_ROOT / url.split("/media/", 1)[1]
        elif url.startswith("/static/uploads/"):
            target_path = STATIC_DIR_PUBLIC / url.replace("/static/", "")
        else:
            return

        if target_path.is_file():
            target_path.unlink()
    except OSError:
        # тихо игнорируем ошибки удаления, чтобы не ломать основной поток
        pass


def _bool_from_any(value, default: bool | None = None) -> bool | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}
    return default


def _int_from_any(value, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class AdminImageKind(str, Enum):
    product = "product"
    course = "course"
    home = "home"


@app.on_event("startup")
def startup_event() -> None:
    ensure_media_dirs()
    init_db()

    static_dir = ADMINSITE_STATIC_ROOT.resolve()
    logger.info(
        "AdminSite static root: %s (constructor.js exists=%s)",
        static_dir,
        ADMINSITE_CONSTRUCTOR_PATH.exists(),
    )


@app.get("/api/env")
def api_env():
    from config import get_settings

    settings = get_settings()
    bot_username = settings.bot_username.lstrip("@") if hasattr(settings, "bot_username") else ""
    return {
        "bot_link": f"https://t.me/{bot_username}",
        "channel_link": settings.required_channel_link,
    }


@app.get("/api/branding")
def api_get_branding():
    with get_session() as session:
        branding = branding_service.get_or_create_branding(session)
        return branding_service.serialize_branding(branding)


@app.get("/api/home")
def api_home():
    return home_service.get_active_home_data()


@app.get("/api/homepage/blocks")
def api_homepage_blocks():
    try:
        blocks = home_service.list_blocks(include_inactive=False)
    except Exception as exc:  # noqa: WPS430
        logger.exception("Failed to load homepage blocks")
        return {"items": [], "error": str(exc)}
    return {"items": [block.dict() for block in blocks]}


@app.get("/api/health")
def api_health():
    return {"ok": True}


@app.get("/api/adminsite/debug/static")
def adminsite_debug_static():
    static_dir = ADMINSITE_STATIC_ROOT.resolve()
    constructor_path = ADMINSITE_CONSTRUCTOR_PATH.resolve()

    return {
        "static_mount": "/static",
        "static_dir": str(static_dir),
        "static_dir_exists": static_dir.exists(),
        "constructor_path": str(constructor_path),
        "constructor_exists": constructor_path.exists(),
    }


@app.get("/api/adminsite/debug/routes")
def adminsite_debug_routes():
    return [
        {"path": getattr(route, "path", ""), "name": getattr(route, "name", "")}
        for route in app.routes
    ]


@app.get("/api/faq")
def api_faq(category: str | None = None):
    items = faq_service.get_faq_list(category)
    return [_faq_to_dict(item) for item in items]


@app.get("/api/faq/{faq_id}")
def api_faq_detail(faq_id: int):
    item = faq_service.get_faq_item(faq_id)
    if not item:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return _faq_to_dict(item)


@app.post("/api/webchat/start")
async def api_webchat_start(
    request: Request, payload: WebChatStartPayload = Body(default=WebChatStartPayload())
):
    """
    Старт/инициализация сессии веб-чата.
    Ожидается JSON:
    {
      "session_key": "строка",
      "page": "опционально, строка"
    }
    """
    session_key = payload.session_key
    page = payload.page
    user_identifier = payload.user_identifier
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request and request.client else None

    if not session_key:
        raise HTTPException(status_code=400, detail="session_key is required")

    logger.info(
        "webchat_start: session_key=%s page=%s user_identifier=%s",
        session_key,
        page,
        user_identifier,
    )

    session = webchat_service.get_session_by_key(session_key)
    created = False
    if not session:
        session = webchat_service.get_or_create_session(
            session_key,
            user_identifier=user_identifier,
            user_agent=user_agent,
            client_ip=client_ip,
        )
        created = True
    else:
        webchat_service.get_or_create_session(
            session_key,
            user_identifier=user_identifier,
            user_agent=user_agent,
            client_ip=client_ip,
        )

    if created:
        try:
            webchat_service.add_system_message(session, "Чат начат")
        except Exception:
            logger.exception("Failed to add system message for webchat start")

    return {
        "ok": True,
        "session_id": int(session.id),
        "session_key": session.session_key,
        "status": session.status,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@app.post("/api/webchat/message")
async def api_webchat_message(
    request: Request, payload: WebChatMessagePayload = Body(default=WebChatMessagePayload())
):
    """
    Приём сообщения пользователя из веб-чата.
    Ожидается JSON:
    {
      "session_key": "строка",
      "text": "строка"
    }
    """
    session_key = payload.session_key
    text = payload.text
    user_identifier = payload.user_identifier
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request and request.client else None

    if not session_key:
        raise HTTPException(status_code=400, detail="session_key is required")
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    logger.info(
        "webchat_message: session_key=%s text_len=%s user_identifier=%s",
        session_key,
        len(text or ""),
        user_identifier,
    )

    session = webchat_service.get_or_create_session(
        session_key,
        user_identifier=user_identifier,
        user_agent=user_agent,
        client_ip=client_ip,
    )

    message = webchat_service.add_user_message(session, text)

    current_session = webchat_service.get_session_by_key(session_key) or session
    if current_session.status == "open":
        webchat_service.mark_waiting_manager(current_session)

    current_session = webchat_service.get_session_by_key(session_key) or current_session
    if (
        current_session.status == "waiting_manager"
        and not current_session.telegram_thread_message_id
    ):
        message_ids = _notify_admin_about_chat(current_session, text)
        if message_ids:
            webchat_service.set_thread_message_id(current_session, message_ids[0])

    return {"ok": True, "message_id": int(message.id), "text": text}


@app.get("/api/webchat/messages", response_model=WebChatMessagesResponse)
def api_webchat_messages(
    session_key: str, limit: Optional[int] = None, after_id: int = 0
):
    session = webchat_service.get_session_by_key(session_key)
    if not session:
        return {"ok": True, "status": "open", "messages": []}

    messages = webchat_service.get_messages(
        session, limit=limit, after_id=after_id, mark_read_for="client"
    )

    payload_messages = []
    for msg in messages:
        payload_messages.append(
            {
                "id": msg.id,
                "sender": msg.sender,
                "text": msg.text,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "is_read_by_manager": msg.is_read_by_manager,
                "is_read_by_client": msg.is_read_by_client,
            }
        )

    return {
        "ok": True,
        "status": session.status,
        "messages": payload_messages,
    }


async def _handle_manager_reply(
    session_id: int | str | None, text: str, session_key: str | None = None
):
    session = None
    if session_id is not None:
        try:
            session = webchat_service.get_session_by_id(int(session_id))
        except Exception:
            session = None
    if not session and session_key:
        session = webchat_service.get_session_by_key(session_key)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.add_manager_message(session, text)

    if session.status == "waiting_manager":
        webchat_service.mark_open(session)

    return {"ok": True}


@app.post("/api/webchat/manager_reply")
async def api_webchat_manager_reply(
    payload: WebChatManagerReplyPayload = Body(default=WebChatManagerReplyPayload()),
    session_id: int | None = Query(default=None),
    text: str | None = Query(default=None),
):
    sid = payload.session_id if payload.session_id is not None else session_id
    session_key = payload.session_key
    reply_text = payload.text or payload.message or payload.reply or text

    if sid is None and not session_key:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not reply_text:
        raise HTTPException(status_code=400, detail="text is required")

    logger.info(
        "manager_reply: session_id=%s session_key=%s text_len=%s",
        sid,
        session_key,
        len(reply_text or ""),
    )
    return await _handle_manager_reply(sid, reply_text, session_key=session_key)


def _validate_type(product_type: str) -> str:
    if product_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="type must be 'basket' or 'course'")
    return product_type


def _validate_category_type(product_type: str) -> str:
    if product_type not in ALLOWED_CATEGORY_TYPES:
        raise HTTPException(status_code=400, detail="type must be 'basket', 'course' or 'mixed'")
    return product_type


def _faq_to_dict(item) -> dict:
    return {
        "id": int(item.id),
        "category": item.category,
        "question": item.question,
        "answer": item.answer,
        "sort_order": int(item.sort_order or 0),
    }


class CartItemPayload(BaseModel):
    user_id: int
    product_id: int
    qty: int | None = 1
    type: str = "basket"


class CartClearPayload(BaseModel):
    user_id: int


class CheckoutPayload(BaseModel):
    user_id: int
    user_name: str | None = Field(None, description="Имя пользователя из Telegram")
    customer_name: str = Field(..., description="Имя клиента")
    contact: str = Field(..., description="Способ связи")
    comment: str | None = None
    promocode: str | None = None


class TelegramAuthPayload(BaseModel):
    init_data: str | None = None
    auth_query: str | None = None


class TelegramWebAppAuthPayload(BaseModel):
    init_data: str | None = None


class ProfileUpdatePayload(BaseModel):
    full_name: str | None = None
    phone: str | None = None


class FaqCreatePayload(BaseModel):
    category: str
    question: str
    answer: str


class WebChatStartPayload(BaseModel):
    session_key: str
    page: str | None = None


class WebChatMessagePayload(BaseModel):
    session_key: str
    text: str

class FaqUpdatePayload(BaseModel):
    category: str | None = None
    question: str | None = None
    answer: str | None = None
    sort_order: int | None = None


class AvatarUpdatePayload(BaseModel):
    avatar_url: str


class ContactPayload(BaseModel):
    telegram_id: int
    phone: str | None = None


class FavoriteTogglePayload(BaseModel):
    telegram_id: int
    product_id: int
    type: str


class ReviewCreatePayload(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    text: str
    photos: list[str] | None = None
    order_id: int | None = None


class ReviewStatusUpdatePayload(BaseModel):
    status: str
    is_deleted: bool | None = None


class AdminSupportMessagePayload(BaseModel):
    session_id: int
    text: str


class AdminSupportClosePayload(BaseModel):
    session_id: int


def _ensure_admin(user_id: int | None) -> int:
    if user_id is None or not users_service.is_admin(int(user_id)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return int(user_id)


def _validate_telegram_webapp_init_data(
    init_data: str, bot_token: str | None = None
) -> dict[str, Any]:
    if not init_data:
        raise HTTPException(status_code=400, detail="init_data_missing")

    try:
        parsed_pairs = list(parse_qsl(init_data, keep_blank_values=True))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid init_data format")

    received_hash = None
    filtered_pairs: list[tuple[str, str]] = []
    for key, value in parsed_pairs:
        if key == "hash":
            received_hash = value
        else:
            filtered_pairs.append((key, value))

    if not received_hash:
        raise HTTPException(status_code=401, detail="invalid_signature")

    resolved_bot_token = bot_token or BOT_TOKEN
    secret_key = hashlib.sha256(resolved_bot_token.encode()).digest()
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(filtered_pairs, key=lambda item: item[0]))
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, str(received_hash)):
        logger.warning("Telegram WebApp auth failed: invalid signature")
        raise HTTPException(status_code=401, detail="invalid_signature")

    data_dict = {k: v for k, v in filtered_pairs}

    auth_date_raw = data_dict.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError:
            raise HTTPException(status_code=401, detail="invalid_signature")

        if time.time() - auth_date > 24 * 60 * 60:
            raise HTTPException(status_code=401, detail="invalid_signature")

    user_json = data_dict.get("user")
    if not user_json:
        raise HTTPException(status_code=401, detail="invalid_signature")

    try:
        return json.loads(user_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid user payload")


def _parse_telegram_auth_data(auth_payload: str, bot_token: str | None = None) -> dict:
    if not auth_payload:
        raise HTTPException(status_code=400, detail="auth payload is empty")

    normalized_payload = auth_payload[1:] if auth_payload.startswith("?") else auth_payload

    try:
        parsed_pairs = list(parse_qsl(normalized_payload, keep_blank_values=True))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid auth payload format")

    received_hash = None
    filtered_pairs: list[tuple[str, str]] = []
    for key, value in parsed_pairs:
        if key == "hash":
            received_hash = value
        else:
            filtered_pairs.append((key, value))

    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash")

    resolved_bot_token = bot_token or BOT_TOKEN
    secret_key = hashlib.sha256(resolved_bot_token.encode()).digest()
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(filtered_pairs, key=lambda item: item[0]))
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, str(received_hash)):
        raise HTTPException(status_code=401, detail="Invalid auth signature")

    data_dict = {k: v for k, v in filtered_pairs}

    auth_date_raw = data_dict.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid auth_date")

        if time.time() - auth_date > 24 * 60 * 60:
            raise HTTPException(status_code=401, detail="auth_date is too old")

    return data_dict


def _full_name(user) -> str:
    parts = [user.first_name, user.last_name]
    return " ".join(part for part in parts if part).strip()


def _extract_user_from_auth_data(data: dict[str, Any]) -> dict[str, Any]:
    if "user" in data:
        try:
            return json.loads(data["user"])
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid user payload")
    return data


def _split_full_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.split(" ", 1)
    first_name = parts[0].strip() if parts else None
    last_name = parts[1].strip() if len(parts) > 1 else None
    return first_name or None, last_name or None


def _build_user_profile(session: Session, user: User, *, include_notes: bool = False) -> dict:
    """
    Собирает полный профиль пользователя для фронтенда.

    Возвращаемые поля:
      - ok: True
      - telegram_id: int
      - telegram_username: str | None
      - full_name: str | None
      - phone: str | None
      - created_at: str | None (ISO8601)
      - is_admin: bool
      - orders: list[dict]
      - stats: dict
      - favorites: list[dict]
      - ban: dict | None
    Заметки (notes) для CRM можно добавлять только если user.is_admin и include_notes=True.
    """
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    telegram_id = int(user.telegram_id)
    display_full_name = _full_name(user) or None

    try:
        orders = orders_service.get_orders_by_user(
            telegram_id, include_archived=False
        ) or []
    except Exception:
        orders = []

    try:
        favorites = favorites_service.list_favorites(telegram_id) or []
    except Exception:
        favorites = []

    try:
        courses = orders_service.get_user_courses_with_access(telegram_id) or []
    except Exception:
        courses = []

    try:
        stats = user_stats_service.get_user_order_stats(telegram_id) or {}
    except Exception:
        stats = {}

    try:
        ban_status = user_admin_service.get_user_ban_status(telegram_id) or None
    except Exception:
        ban_status = None

    notes = []
    if include_notes and user.is_admin:
        try:
            notes = user_admin_service.get_user_notes(telegram_id, limit=20) or []
        except Exception:
            notes = []

    return {
        "ok": True,
        "telegram_id": telegram_id,
        "telegram_username": user.username,
        "username": user.username,
        "full_name": display_full_name,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        "is_admin": bool(user.is_admin),
        "orders": orders,
        "favorites": favorites,
        "courses": courses,
        "stats": stats,
        "ban": ban_status,
        "notes": notes,
    }


def _get_current_user_from_cookie(session: Session, request: Request) -> User | None:
    user_id = request.cookies.get("tg_user_id")
    if not user_id:
        return None

    try:
        telegram_id = int(user_id)
    except ValueError:
        return None

    return session.query(User).filter(User.telegram_id == telegram_id).first()


def get_admin_user(request: Request) -> User:
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user or not getattr(user, "is_admin", False):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user


def _product_by_type(product_type: str, product_id: int, *, include_inactive: bool = False):
    if product_type == "basket":
        return products_service.get_basket_by_id(product_id, include_inactive=include_inactive)
    return products_service.get_course_by_id(product_id, include_inactive=include_inactive)


def _build_cart_response(user_id: int) -> dict[str, Any]:
    items, removed_ids = cart_service.get_cart_items(user_id)

    normalized_items: list[dict[str, Any]] = []
    removed_items: list[dict[str, Any]] = []
    total = 0

    for item in items:
        product_type = item.get("type") or "basket"
        if product_type not in ALLOWED_TYPES:
            removed_items.append({"product_id": item.get("product_id"), "type": product_type, "reason": "invalid"})
            cart_service.remove_from_cart(user_id, int(item.get("product_id") or 0), product_type)
            continue
        try:
            product_id = int(item.get("product_id"))
        except (TypeError, ValueError):
            removed_items.append({"product_id": None, "type": product_type, "reason": "invalid"})
            continue

        product_info = _product_by_type(product_type, product_id)
        if not product_info:
            removed_items.append({"product_id": product_id, "type": product_type, "reason": "inactive"})
            cart_service.remove_from_cart(user_id, product_id, product_type)
            continue

        qty = max(int(item.get("qty") or 0), 0)
        if qty <= 0:
            cart_service.remove_from_cart(user_id, product_id, product_type)
            continue

        price = int(product_info.get("price") or 0)
        subtotal = price * qty
        total += subtotal

        normalized_items.append(
            {
                "product_id": product_id,
                "type": product_type,
                "name": product_info.get("name"),
                "price": price,
                "qty": qty,
                "subtotal": subtotal,
                "category_id": product_info.get("category_id"),
            }
        )

    for removed_id in removed_ids:
        product_info = products_service.get_product_by_id(removed_id, include_inactive=True)
        removed_items.append(
            {
                "product_id": removed_id,
                "type": product_info.get("type") if product_info else "unknown",
                "reason": "inactive" if product_info else "not_found",
            }
        )

    return {"items": normalized_items, "removed_items": removed_items, "total": total}


@app.post("/api/auth/telegram_webapp")
def api_auth_telegram_webapp(payload: TelegramWebAppAuthPayload, response: Response):
    """Авторизация WebApp через init_data внутри Telegram."""

    init_data = (payload.init_data or "").strip()
    if not init_data:
        response.status_code = 400
        return {"status": "error", "error": "init_data_missing"}

    try:
        user_data = _validate_telegram_webapp_init_data(init_data, BOT_TOKEN)
    except HTTPException as exc:
        response.status_code = exc.status_code
        error_code = exc.detail if isinstance(exc.detail, str) else "invalid_signature"
        if error_code == "init_data is empty":
            error_code = "init_data_missing"
        if error_code not in {"init_data_missing", "invalid_signature"}:
            error_code = "invalid_signature"
        return {"status": "error", "error": error_code}

    telegram_id = user_data.get("id")
    if telegram_id is None:
        response.status_code = 400
        return {"status": "error", "error": "invalid_user"}

    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    full_name = " ".join(part for part in [first_name, last_name] if part).strip() or None

    with get_session() as session:
        try:
            user = users_service.get_or_create_user_from_telegram(
                session,
                telegram_id=int(telegram_id),
                username=user_data.get("username"),
                full_name=full_name,
                phone=user_data.get("phone"),
            )
        except ValueError:
            response.status_code = 400
            return {"status": "error", "error": "invalid_user"}
        except Exception:
            response.status_code = 500
            return {"status": "error", "error": "authorization_failed"}

        response.set_cookie(
            key="tg_user_id",
            value=str(user.telegram_id),
            httponly=True,
            max_age=COOKIE_MAX_AGE,
            samesite="lax",
        )

        logger.info(
            "Telegram WebApp auth succeeded: telegram_id=%s, user_id=%s",
            user.telegram_id,
            user.id,
        )

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
            },
        }


@app.post("/api/auth/create-token")
def api_auth_create_token():
    """
    Создать новую сессию авторизации для deeplink-а из бота.
    Возвращает {"ok": true, "token": "..."}.
    """
    token = str(uuid4())
    with get_session() as s:
        s.add(AuthSession(token=token))
    return {"ok": True, "token": token}


@app.get("/api/auth/check")
def api_auth_check(token: str, response: Response, include_notes: bool = False):
    """
    Проверить токен AuthSession, выданный по deeplink-у из бота.
    При успешной проверке возвращает профиль пользователя в едином формате.
    """
    with get_session() as s:
        session = s.query(AuthSession).filter(AuthSession.token == token).first()
        if not session:
            response.status_code = 404
            return {"ok": False, "reason": "not_found"}

        if session.created_at and datetime.utcnow() - session.created_at > timedelta(seconds=AUTH_SESSION_TTL_SECONDS):
            response.status_code = 410
            return {"ok": False, "reason": "expired"}

        if not session.telegram_id:
            return {"ok": False, "reason": "pending"}

        telegram_id = int(session.telegram_id)

        user = s.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id)
            s.add(user)
            s.flush()

        profile = _build_user_profile(s, user, include_notes=include_notes)

    if not profile:
        response.status_code = 404
        return {"ok": False, "reason": "not_found"}

    response.set_cookie(
        key="tg_user_id",
        value=str(telegram_id),
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
    )

    return profile


@app.get("/api/auth/telegram-login")
def api_auth_telegram_login(request: Request):
    """
    Авторизация через Telegram Login Widget (браузер на сайте).
    Telegram делает GET на этот URL с параметрами:
    id, first_name, last_name, username, photo_url, auth_date, hash.
    Алгоритм проверки: https://core.telegram.org/widgets/login
    """
    params = dict(request.query_params)
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=400, detail="Missing hash")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items()) if v is not None and v != ""
    )

    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=400, detail="Invalid login data")

    auth_date = int(params.get("auth_date", "0") or 0)
    if auth_date and time.time() - auth_date > 86400:
        raise HTTPException(status_code=400, detail="Login data is too old")

    user_data = {
        "id": int(params["id"]),
        "first_name": params.get("first_name") or "",
        "last_name": params.get("last_name") or "",
        "username": params.get("username") or "",
        "photo_url": params.get("photo_url") or "",
    }

    try:
        user = users_service.get_or_create_user_from_telegram(user_data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user data")

    response = RedirectResponse(url="/profile.html", status_code=302)
    response.set_cookie(
        key="tg_user_id",
        value=str(user.telegram_id),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


def _wrap_home_banner_error(action: str, func):
    try:
        return func()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: WPS430
        logger.exception("Home banner %s failed", action)
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Не удалось {action} блок главной",
                "error": str(exc),
            },
        ) from exc


def _wrap_home_block_error(action: str, func):
    return _wrap_home_banner_error(action, func)


@app.get("/api/auth/session")
async def api_auth_session(request: Request, response: Response, include_notes: bool = False):
    """
    Авторизация из браузера или Telegram WebApp по cookie tg_user_id.

    Если cookie отсутствует, пробует авторизовать пользователя по initData
    из запроса Telegram WebApp. Если сессия не найдена — возвращает
    `{"authenticated": false}` без ошибки 401.
    """
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            user = await authenticate_telegram_webapp_user(
                request,
                session,
                _validate_telegram_webapp_init_data,
                response=response,
                cookie_max_age=COOKIE_MAX_AGE,
            )

        if not user:
            return {"authenticated": False}

        try:
            profile = _build_user_profile(session, user, include_notes=include_notes)
        except HTTPException as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return {"authenticated": True, "user": profile}


class AdminProductsCreatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    stock: int = Field(default=0, ge=0)
    short_description: str | None = ""
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    image: str | None = None
    image_url: str | None = None
    wb_url: str | None = None
    ozon_url: str | None = None
    yandex_url: str | None = None
    avito_url: str | None = None
    masterclass_url: str | None = None


class AdminProductsUpdatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    stock: int | None = Field(default=None, ge=0)
    short_description: str | None = ""
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    is_active: bool | None = None
    image: str | None = None
    image_url: str | None = None
    wb_url: str | None = None
    ozon_url: str | None = None
    yandex_url: str | None = None
    avito_url: str | None = None
    masterclass_url: str | None = None


class AdminProductCategoryPayload(BaseModel):
    user_id: int
    name: str
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    sort_order: int = 0
    is_active: bool | None = True
    type: str = "basket"


class AdminProductCategoryUpdatePayload(BaseModel):
    user_id: int
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    type: str | None = None


class AdminCategoryPagePayload(BaseModel):
    user_id: int
    force: bool | None = False


class AdminTogglePayload(BaseModel):
    user_id: int
    type: str


class AdminOrderStatusPayload(BaseModel):
    user_id: int
    status: str


class AdminPromocodeCreatePayload(BaseModel):
    user_id: int
    code: str
    discount_type: str
    discount_value: float
    scope: str = "all"
    target_id: int | None = None
    max_uses: int | None = None
    date_start: str | None = None
    date_end: str | None = None
    expires_at: str | None = None
    active: bool | None = None
    one_per_user: bool | None = None


class AdminPromocodeUpdatePayload(BaseModel):
    user_id: int
    code: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    max_uses: int | None = None
    active: bool | None = None
    scope: str | None = None
    target_id: int | None = None
    date_start: str | None = None
    date_end: str | None = None
    expires_at: str | None = None
    one_per_user: bool | None = None


class PromocodeCartItemPayload(BaseModel):
    product_id: int
    qty: int = 1
    type: str = "basket"
    price: int | None = None
    category_id: int | None = None


class PromocodeValidatePayload(BaseModel):
    telegram_id: int
    code: str
    items: list[PromocodeCartItemPayload] | None = None


class CartPromocodeApplyPayload(BaseModel):
    user_id: int
    code: str


@app.post("/api/auth/telegram")
def api_auth_telegram(payload: TelegramAuthPayload, response: Response):
    """
    Единый endpoint авторизации через Telegram WebApp или Login Widget.

    Поддерживает:
      * init_data — строка initData из Telegram WebApp;
      * auth_query — query-string из Telegram Login Widget или deeplink-а.
    """

    if (payload.init_data is None and payload.auth_query is None) or (
        payload.init_data is not None and payload.auth_query is not None
    ):
        raise HTTPException(status_code=400, detail="Provide exactly one of init_data or auth_query")

    raw_auth_payload = payload.init_data or payload.auth_query or ""

    try:
        validated_data = _parse_telegram_auth_data(raw_auth_payload, BOT_TOKEN)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid telegram auth data")

    user_data = _extract_user_from_auth_data(validated_data)

    telegram_id = user_data.get("id")
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="Missing user id")

    try:
        telegram_id_int = int(telegram_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid user id")

    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    full_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    phone = user_data.get("phone") or user_data.get("phone_number")

    with get_session() as session:
        try:
            user = users_service.get_or_create_user_from_telegram(
                session,
                telegram_id=telegram_id_int,
                username=user_data.get("username"),
                full_name=full_name,
                phone=phone,
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user data")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to authorize user")

        response.set_cookie(
            key="tg_user_id",
            value=str(user.telegram_id),
            httponly=True,
            max_age=COOKIE_MAX_AGE,
            samesite="lax",
        )

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
            },
        }


@app.post("/api/auth/logout")
def api_auth_logout(response: Response):
    """
    Logout для обычного сайта: сбрасывает cookie tg_user_id.
    Используется кнопкой "Выйти"/"Сменить пользователя".
    """
    response.delete_cookie("tg_user_id", path="/")
    return {"ok": True}


@app.post("/api/profile/update")
def api_profile_update(payload: ProfileUpdatePayload, request: Request):
    """
    Обновление имени и телефона текущего пользователя (по cookie tg_user_id).
    Telegram ID и username менять нельзя.
    """
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        if payload.full_name is not None:
            first_name, last_name = _split_full_name(payload.full_name.strip())
            user.first_name = first_name
            user.last_name = last_name
        if payload.phone is not None:
            user.phone = payload.phone.strip()

        session.add(user)
        session.commit()
        session.refresh(user)
        return {"ok": True, "user": _build_user_profile(session, user)}


@app.post("/api/profile/avatar-url")
def update_avatar_url(payload: AvatarUpdatePayload, request: Request):
    """
    Обновление avatar_url для текущего пользователя.
    Фактический файл аватара должен быть уже размещён владельцем проекта на сервере
    по указанному пути (например, /media/users/<telegram_id>/avatar.jpg).
    """
    ensure_media_dirs()
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        avatar_url = payload.avatar_url.strip()
        user.avatar_url = avatar_url or None

        session.add(user)
        session.commit()
        session.refresh(user)

        profile = _build_user_profile(session, user)
        return {"ok": True, "avatar_url": user.avatar_url, "profile": profile}


@app.post("/api/profile/avatar")
def upload_avatar(request: Request, file: UploadFile = File(...)) -> dict:
    """Загрузка файла аватара текущего пользователя."""

    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Неверный формат изображения")

    ensure_media_dirs()

    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user_dir = MEDIA_ROOT / "users" / str(user.telegram_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        ext = (file.filename or "jpg").split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        filename = f"avatar.{ext}"
        full_path = user_dir / filename

        with full_path.open("wb") as f:
            f.write(file.file.read())

        relative = full_path.relative_to(MEDIA_ROOT).as_posix()
        user.avatar_url = f"/media/{relative}"

        session.add(user)
        session.commit()
        session.refresh(user)

        profile = _build_user_profile(session, user)
        return {"ok": True, "avatar_url": user.avatar_url, "profile": profile}


@app.post("/api/orders/{order_id}/archive")
def archive_order(order_id: int, request: Request):
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

    archived = orders_service.archive_order_for_user(order_id, int(user.telegram_id))
    if not archived:
        order = orders_service.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=403, detail="Forbidden")

    return {"ok": True}


@app.get("/public/site-settings")
def public_site_settings():
    return menu_catalog.get_site_settings()


@app.get("/public/menu")
def public_menu(type: str | None = None):
    try:
        return menu_catalog.build_public_menu(type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/public/menu/tree")
def public_menu_tree(type: str | None = None):
    try:
        return menu_catalog.build_public_menu_tree(type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/public/menu/categories")
def public_menu_categories(type: str | None = None):
    try:
        return {"items": menu_catalog.list_categories(include_inactive=False, category_type=type)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/public/menu/items")
def public_menu_items(category: str | None = None, type: str | None = None):
    try:
        if category:
            if category.isdigit():
                return {
                    "items": menu_catalog.list_items(
                        include_inactive=False,
                        category_id=int(category),
                        category_type=type,
                    )
                }
            category_record = menu_catalog.get_category_by_slug(
                category, include_inactive=False, category_type=type
            )
            if not category_record:
                raise HTTPException(status_code=404, detail="Category not found")
            return {
                "items": menu_catalog.list_items(
                    include_inactive=False,
                    category_id=int(category_record.id),
                    category_type=type,
                )
            }
        return {
            "items": menu_catalog.list_items(include_inactive=False, category_type=type)
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/public/site-settings")
def api_public_site_settings():
    return menu_catalog.get_site_settings()


@app.get("/api/public/menu")
def api_public_menu(type: str | None = None):
    try:
        return menu_catalog.build_public_menu(type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/public/menu/tree")
def api_public_menu_tree(type: str | None = None):
    try:
        return menu_catalog.build_public_menu_tree(type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/public/menu/categories")
def api_public_menu_categories(type: str | None = None):
    try:
        return {"items": menu_catalog.list_categories(include_inactive=False, category_type=type)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/public/menu/category/{slug}")
def api_public_menu_category(slug: str, type: str | None = None):
    try:
        category = menu_catalog.get_category_details(
            slug, include_inactive=False, category_type=type
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@app.get("/api/public/menu/items")
def api_public_menu_items(category_slug: str | None = None, type: str | None = None):
    try:
        if category_slug:
            category_record = menu_catalog.get_category_by_slug(
                category_slug, include_inactive=False, category_type=type
            )
            if not category_record:
                raise HTTPException(status_code=404, detail="Category not found")
            return {
                "items": menu_catalog.list_items(
                    include_inactive=False,
                    category_id=int(category_record.id),
                    category_type=type,
                )
            }
        return {"items": menu_catalog.list_items(include_inactive=False, category_type=type)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/public/item/{item_id}")
def api_public_item(item_id: int):
    item = menu_catalog.get_item_by_id(item_id, include_inactive=False)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/api/public/blocks")
def api_public_blocks(page: str | None = None):
    return {"items": menu_catalog.list_blocks(include_inactive=False, page=page)}


@app.get("/api/site/menu")
def site_menu():
    return menu_catalog.build_public_menu()


@app.get("/api/site/theme")
def site_theme():
    raise HTTPException(status_code=410, detail="Theme constructor disabled")


@app.get("/api/site-settings")
def site_settings():
    return menu_catalog.get_site_settings()


@app.put("/api/site-settings")
def update_site_settings(payload: SiteSettingsPayload, request: Request, db: Session = Depends(get_db)):
    adminsite_service.ensure_admin(request, db)
    return menu_catalog.update_site_settings(payload.model_dump())


@app.get("/api/site/categories")
def site_categories():
    return {"items": menu_catalog.list_categories(include_inactive=False)}


@app.get("/api/site/categories/{slug}")
def site_category(slug: str):
    category = menu_catalog.get_category_details(slug, include_inactive=False)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@app.get("/api/site/products/{slug}")
def site_product(slug: str):
    item = menu_catalog.get_item_by_slug(slug, include_inactive=False)
    if not item or item.get("type") != "product":
        raise HTTPException(status_code=404, detail="Product not found")
    return item


@app.get("/api/site/masterclasses/{slug}")
def site_masterclass(slug: str):
    item = menu_catalog.get_item_by_slug(slug, include_inactive=False)
    if not item or item.get("type") != "course":
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return item


@app.get("/api/site/items")
def site_items(category_id: int | None = None, type: str | None = None):
    return {
        "items": menu_catalog.list_items(
            include_inactive=False, category_id=category_id, item_type=type
        )
    }


@app.get("/api/site/home")
def site_home():
    return {
        "settings": menu_catalog.get_site_settings(),
        "menu": menu_catalog.build_public_menu(),
    }


@app.get("/api/site/pages/{page_key}")
def site_page(page_key: str):
    raise HTTPException(status_code=410, detail="Page constructor disabled")


@app.get("/api/categories")
def api_categories(type: str | None = None, active_only: bool = True):
    """
    Вернуть список категорий для товаров или курсов.
    Если type не указан — вернуть активные категории всех типов.
    """
    product_type = _validate_category_type(type) if type else None
    return products_service.list_categories(product_type, include_inactive=not active_only)


@app.get("/api/categories/{slug}")
def api_category_detail(slug: str):
    category = products_service.get_category_with_items(slug)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@app.get("/api/products")
def api_products(type: str, category_slug: str | None = None):
    """
    Вернуть список товаров/курсов.
    Если category_slug передан — фильтровать по категории.
    """
    product_type = _validate_type(type)
    return products_service.list_products(product_type, category_slug=category_slug, is_active=True)


@app.get("/api/products/{product_id}")
def api_product_detail(product_id: int):
    """Возвращает данные одного товара или мастер-класса по ID."""
    product = products_service.get_product_by_id(product_id)
    if not product or not product.get("is_active"):
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/api/masterclasses/{masterclass_id}")
def api_masterclass_detail(masterclass_id: int):
    """Возвращает данные мастер-класса по ID."""
    masterclass = products_service.get_course_by_id(masterclass_id)
    if not masterclass or not masterclass.get("is_active"):
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return masterclass


@app.post("/api/masterclasses/{masterclass_id}/reviews")
def create_masterclass_review(
    masterclass_id: int, payload: ReviewCreatePayload, request: Request
):
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

    masterclass = products_service.get_course_by_id(masterclass_id)
    if not masterclass or not masterclass.get("is_active", True):
        raise HTTPException(status_code=404, detail="Masterclass not found")

    try:
        review_id = reviews_service.create_masterclass_review(
            masterclass_id,
            user,
            payload.rating,
            payload.text,
            payload.photos,
            payload.order_id,
        )
    except ValueError as exc:  # pragma: no cover - defensive
        detail = "Invalid payload"
        if str(exc) == "masterclass_not_found":
            detail = "Masterclass not found"
        elif str(exc) == "rating must be between 1 and 5":
            detail = str(exc)
        raise HTTPException(status_code=400, detail=detail)

    return {"success": True, "review_id": review_id, "status": "pending"}


@app.get("/api/masterclasses/{masterclass_id}/reviews")
def get_masterclass_reviews(
    masterclass_id: int, page: int = 1, limit: int = 20, with_meta: bool = False
):
    masterclass = products_service.get_course_by_id(masterclass_id)
    if not masterclass:
        raise HTTPException(status_code=404, detail="Masterclass not found")

    reviews = reviews_service.get_reviews_for_masterclass(masterclass_id, page=page, limit=limit)
    if with_meta:
        return {"items": reviews, "page": page, "limit": limit}
    return reviews


@app.post("/api/products/{product_id}/reviews")
def create_product_review(product_id: int, payload: ReviewCreatePayload, request: Request):
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

    product = products_service.get_product_by_id(product_id)
    if not product or not product.get("is_active", True):
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        review_id = reviews_service.create_review(
            product_id,
            user,
            payload.rating,
            payload.text,
            payload.photos,
            payload.order_id,
        )
    except ValueError as exc:  # pragma: no cover - defensive
        detail = "Invalid payload"
        if str(exc) == "product_not_found":
            detail = "Product not found"
        elif str(exc) == "rating must be between 1 and 5":
            detail = str(exc)
        raise HTTPException(status_code=400, detail=detail)

    return {"success": True, "review_id": review_id, "status": "pending"}


@app.get("/api/products/{product_id}/reviews")
def get_product_reviews(
    product_id: int, page: int = 1, limit: int = 20, with_meta: bool = False
):
    product = products_service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    reviews = reviews_service.get_reviews_for_product(product_id, page=page, limit=limit)
    if with_meta:
        return {"items": reviews, "page": page, "limit": limit}
    return reviews


@app.get("/api/products/{product_id}/rating")
def get_product_rating(product_id: int):
    product = products_service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return reviews_service.get_rating_summary(product_id)


@app.post("/api/reviews/{review_id}/photos")
def upload_review_photo(review_id: int, request: Request, file: list[UploadFile] = File(...)):
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

    review = reviews_service.get_review_by_id(review_id)
    if not review or review.is_deleted:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.user_id != user.telegram_id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    ensure_media_dirs()
    try:
        photos = reviews_service.add_review_photo(review_id, file, MEDIA_ROOT)
    except ValueError as exc:  # pragma: no cover - defensive
        detail = str(exc)
        if detail == "review_not_found":
            raise HTTPException(status_code=404, detail="Review not found")
        raise HTTPException(status_code=400, detail=detail)

    return {"ok": True, "photos": photos}


@app.get("/api/cart")
def api_cart(user_id: int):
    """Вернуть содержимое корзины пользователя и сумму заказа."""
    return _build_cart_response(user_id)


@app.post("/api/cart/apply-promocode")
def api_cart_apply_promocode(payload: CartPromocodeApplyPayload):
    if payload.user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")

    cart_data = _build_cart_response(payload.user_id)
    items = cart_data.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    result = promocodes_service.validate_promocode(payload.code, payload.user_id, items)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid promocode")

    return {
        "code": result.get("code"),
        "discount_amount": result.get("discount_amount", 0),
        "final_total": result.get("final_total", cart_data.get("total", 0)),
        "scope": result.get("scope"),
        "target_id": result.get("target_id"),
        "eligible_items": result.get("eligible_items", []),
        "cart_total": cart_data.get("total", 0),
        "used_count": result.get("used_count"),
        "max_uses": result.get("max_uses"),
        "one_per_user": result.get("one_per_user"),
    }


@app.post("/api/checkout")
def api_checkout(payload: CheckoutPayload):
    """Оформить заказ из текущей корзины WebApp."""
    if payload.user_id is None or not users_service.get_user_by_telegram_id(int(payload.user_id)):
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    cart_data = _build_cart_response(payload.user_id)
    normalized_items = cart_data.get("items") or []
    removed_items = cart_data.get("removed_items") or []
    total = int(cart_data.get("total") or 0)

    if not normalized_items:
        cart_service.clear_cart(payload.user_id)
        raise HTTPException(status_code=400, detail="No valid items in cart")

    user_name = payload.user_name or "webapp"

    promo_result = None
    if payload.promocode:
        promo_result = promocodes_service.validate_promocode(
            payload.promocode, payload.user_id, normalized_items
        )
        if not promo_result:
            raise HTTPException(status_code=400, detail="Invalid promocode")

    discount_amount = int(promo_result.get("discount_amount", 0)) if promo_result else 0
    final_total = int(promo_result.get("final_total", total)) if promo_result else total

    order_text = format_order_for_admin(
        user_id=payload.user_id,
        user_name=user_name,
        items=normalized_items,
        total=final_total,
        customer_name=payload.customer_name,
        contact=payload.contact,
        comment=payload.comment or "",
    )

    users_service.get_or_create_user_from_telegram(
        {
            "id": payload.user_id,
            "username": payload.user_name,
            "first_name": payload.customer_name,
        }
    )

    order_id = orders_service.add_order(
        user_id=payload.user_id,
        user_name=user_name,
        items=normalized_items,
        total=final_total,
        customer_name=payload.customer_name,
        contact=payload.contact,
        comment=payload.comment or "",
        order_text=order_text,
        promocode_code=promo_result.get("code") if promo_result else None,
        discount_amount=discount_amount if promo_result else None,
    )

    if promo_result:
        promocodes_service.increment_usage(promo_result.get("code"))

    cart_service.clear_cart(payload.user_id)

    return {
        "ok": True,
        "order_id": order_id,
        "total": final_total,
        "discount_amount": discount_amount,
        "removed_items": removed_items,
    }


@app.post("/api/cart/add")
def api_cart_add(payload: CartItemPayload):
    qty = payload.qty or 1
    if qty <= 0:
        raise HTTPException(status_code=400, detail="qty must be positive")

    product_type = _validate_type(payload.type)
    product = _product_by_type(product_type, int(payload.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    cart_service.add_to_cart(
        user_id=payload.user_id,
        product_id=int(payload.product_id),
        qty=qty,
        product_type=product_type,
    )

    return _build_cart_response(payload.user_id)


@app.post("/api/cart/update")
def api_cart_update(payload: CartItemPayload):
    qty = payload.qty or 0
    product_type = _validate_type(payload.type)

    if qty <= 0:
        cart_service.remove_from_cart(payload.user_id, int(payload.product_id), product_type)
        return _build_cart_response(payload.user_id)

    product = _product_by_type(product_type, int(payload.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")

    current_items, _ = cart_service.get_cart_items(payload.user_id)
    existing = next(
        (
            i
            for i in current_items
            if int(i.get("product_id")) == int(payload.product_id) and i.get("type") == product_type
        ),
        None,
    )

    if existing:
        delta = qty - int(existing.get("qty") or 0)
        if delta != 0:
            cart_service.change_qty(payload.user_id, int(payload.product_id), delta, product_type)
    else:
        cart_service.add_to_cart(
            user_id=payload.user_id,
            product_id=int(payload.product_id),
            qty=qty,
            product_type=product_type,
        )

    return _build_cart_response(payload.user_id)


@app.post("/api/cart/clear")
def api_cart_clear(payload: CartClearPayload):
    cart_service.clear_cart(payload.user_id)
    return _build_cart_response(payload.user_id)


@app.get("/api/me")
def api_me(telegram_id: int):
    """
    Вернуть профиль пользователя (личный кабинет) по его telegram_id.
    Формат ответа совпадает с /api/auth/telegram, чтобы фронту было удобно.
    """
    with get_session() as session:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        profile = _build_user_profile(session, user, include_notes=True)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    return profile


@app.post("/api/me/contact")
def api_me_contact(payload: ContactPayload):
    try:
        user = users_service.update_user_contact(payload.telegram_id, payload.phone)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")

    return {"ok": True, "phone": user.phone}


@app.get("/api/favorites")
def api_favorites(telegram_id: int):
    user = users_service.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return favorites_service.list_favorites(telegram_id)


@app.post("/api/favorites/toggle")
def api_favorites_toggle(payload: FavoriteTogglePayload):
    product_type = _validate_type(payload.type)
    user = users_service.get_user_by_telegram_id(payload.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    already_fav = favorites_service.is_favorite(
        payload.telegram_id, payload.product_id, product_type
    )
    if already_fav:
        favorites_service.remove_favorite(payload.telegram_id, payload.product_id, product_type)
        is_fav = False
    else:
        favorites_service.add_favorite(payload.telegram_id, payload.product_id, product_type)
        is_fav = True

    return {"ok": True, "is_favorite": is_fav}


@app.post("/api/promocode/validate")
def api_promocode_validate(payload: PromocodeValidatePayload):
    cart_items: list[dict[str, Any]] = []
    if payload.items:
        for item in payload.items:
            product_type = _validate_type(item.type)
            qty = max(int(item.qty or 0), 0)
            if qty <= 0:
                continue
            product = _product_by_type(product_type, int(item.product_id))
            if not product:
                continue
            cart_items.append(
                {
                    "product_id": int(item.product_id),
                    "type": product_type,
                    "qty": qty,
                    "price": int(product.get("price") or item.price or 0),
                    "category_id": product.get("category_id"),
                }
            )
    else:
        cart_data = _build_cart_response(payload.telegram_id)
        cart_items = cart_data.get("items") or []

    result = promocodes_service.validate_promocode(payload.code, payload.telegram_id, cart_items)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid promocode")

    cart_total = sum(int(item.get("price", 0)) * int(item.get("qty", 0)) for item in cart_items)

    return {
        "code": result["code"],
        "discount_type": result["discount_type"],
        "discount_value": result["discount_value"],
        "discount_amount": result["discount_amount"],
        "final_total": result["final_total"],
        "scope": result.get("scope"),
        "target_id": result.get("target_id"),
        "eligible_items": result.get("eligible_items", []),
        "total": cart_total,
    }


@app.post("/api/admin/branding")
def admin_update_branding(
    site_title: str | None = Form(None),
    logo_file: UploadFile | None = File(None),
    favicon_file: UploadFile | None = File(None),
    admin_user=Depends(get_admin_user),
):
    logo_url = None
    favicon_url = None
    bump_assets = False

    if logo_file:
        logo_url = _save_branding_file(
            logo_file, BRANDING_LOGO_EXTENSIONS, BRANDING_LOGO_MAX_MB, "logo"
        )
        bump_assets = True

    if favicon_file:
        favicon_url = _save_branding_file(
            favicon_file, BRANDING_FAVICON_EXTENSIONS, BRANDING_FAVICON_MAX_MB, "favicon"
        )
        bump_assets = True

    with get_session() as session:
        branding = branding_service.get_or_create_branding(session)
        branding_service.update_branding_record(
            branding,
            site_title=site_title if site_title is not None else None,
            logo_url=logo_url,
            favicon_url=favicon_url,
            bump_assets=bump_assets,
        )
        session.add(branding)
        session.flush()
    return branding_service.serialize_branding(branding)


@app.get("/api/admin/site-settings")
def admin_get_site_settings(request: Request, db: Session = Depends(get_db)):
    adminsite_service.ensure_admin(request, db)
    return menu_catalog.get_site_settings()


@app.put("/api/admin/site-settings")
def admin_update_site_settings(
    payload: SiteSettingsPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    return menu_catalog.update_site_settings(payload.model_dump())


@app.get("/api/admin/blocks")
def admin_blocks(
    request: Request,
    include_inactive: bool = True,
    page: str | None = None,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    return {"items": menu_catalog.list_blocks(include_inactive=include_inactive, page=page)}


@app.post("/api/admin/blocks")
def admin_create_block(
    payload: SiteBlockPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.create_block(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.put("/api/admin/blocks/{block_id}")
def admin_update_block(
    block_id: int,
    payload: SiteBlockUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.update_block(block_id, payload.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.delete("/api/admin/blocks/{block_id}")
def admin_delete_block(
    block_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        menu_catalog.delete_block(block_id)
        return {"status": "ok"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/admin/blocks/reorder")
def admin_blocks_reorder(
    payload: BlockReorderPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    menu_catalog.reorder_blocks(payload.model_dump())
    return {"status": "ok"}


def _resolve_public_base_url() -> str | None:
    settings = menu_catalog.get_site_settings()
    base_url = (settings or {}).get("base_url") if isinstance(settings, dict) else None
    if not base_url:
        return None
    return str(base_url).rstrip("/")


def _build_public_link(base_url: str | None, path: str) -> str:
    if base_url:
        return f"{base_url}{path}"
    return path


@app.get("/api/admin/menu/categories")
def admin_menu_categories(
    request: Request,
    include_inactive: bool = True,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    base_url = _resolve_public_base_url()
    categories = menu_catalog.list_categories(include_inactive=include_inactive)
    for category in categories:
        category["public_url"] = _build_public_link(
            base_url, f"/c/{category.get('slug')}"
        )
    return {"items": categories}


@app.post("/api/admin/menu/categories")
def admin_menu_create_category(
    payload: MenuCategoryPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.create_category(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.put("/api/admin/menu/categories/{category_id}")
def admin_menu_update_category(
    category_id: int,
    payload: MenuCategoryUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.update_category(category_id, payload.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.delete("/api/admin/menu/categories/{category_id}")
def admin_menu_delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        menu_catalog.delete_category(category_id)
        return {"status": "ok"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/api/admin/menu/items")
def admin_menu_items(
    request: Request,
    category_id: int | None = None,
    type: str | None = None,
    include_inactive: bool = True,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        base_url = _resolve_public_base_url()
        items = menu_catalog.list_items(
            include_inactive=include_inactive,
            category_id=category_id,
            item_type=type,
        )
        for item in items:
            item["public_url"] = _build_public_link(
                base_url, f"/i/{item.get('id')}"
            )
        return {"items": items}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/admin/menu/items")
def admin_menu_create_item(
    payload: MenuItemPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.create_item(payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.put("/api/admin/menu/items/{item_id}")
def admin_menu_update_item(
    item_id: int,
    payload: MenuItemUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.update_item(item_id, payload.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.delete("/api/admin/menu/items/{item_id}")
def admin_menu_delete_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        menu_catalog.delete_item(item_id)
        return {"status": "ok"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/admin/menu/reorder")
def admin_menu_reorder(
    payload: MenuReorderPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    menu_catalog.reorder_entities(payload.model_dump())
    return {"status": "ok"}


# ----------------------------
# Admin uploads
# ----------------------------


@app.post("/api/admin/upload-image")
def admin_upload_image(
    kind: AdminImageKind = Form(...),
    file: UploadFile = File(...),
    admin_user=Depends(get_admin_user),
):
    """
    Загрузка изображения для товара/курса из админки.
    Сохраняет файл в файловой системе и возвращает URL, который потом пишется в image_url.
    """
    base_folder_by_kind = {
        AdminImageKind.product: "products",
        AdminImageKind.course: "courses",
        AdminImageKind.home: "home",
    }
    base_folder = base_folder_by_kind.get(kind, "products")
    upload = _save_uploaded_image(file, base_folder)

    return {"ok": True, **upload}


@app.post("/api/admin/home/upload_image")
def admin_upload_home_image(file: UploadFile = File(...), admin_user=Depends(get_admin_user)):
    """
    Загрузка изображения для блоков главной страницы.
    Путь отличается от общего upload-image, но сохраняет файл в `/media/adminsite/home/`.
    """
    upload = _save_uploaded_image(file, "home")
    return {"ok": True, **upload}


@app.get("/api/admin/products/{product_id}/images")
def admin_product_images(product_id: int, user_id: int):
    _ensure_admin(user_id)
    try:
        images = products_service.list_product_images(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"items": images}


@app.post("/api/admin/products/{product_id}/images")
def admin_upload_product_images(
    product_id: int,
    files: list[UploadFile] = File(...),
    admin_user=Depends(get_admin_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов для загрузки")

    uploads = [_save_uploaded_image(file, "products") for file in files]
    urls = [item["url"] for item in uploads]
    try:
        images = products_service.add_product_images(product_id, urls)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"items": images, "uploads": uploads}


@app.delete("/api/admin/products/images/{image_id}")
def admin_delete_product_image(image_id: int, user_id: int):
    _ensure_admin(user_id)
    image_url = products_service.delete_product_image(image_id)
    if not image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    _delete_media_file(image_url)
    return {"ok": True}


@app.get("/api/admin/masterclasses/{masterclass_id}/images")
def admin_masterclass_images(masterclass_id: int, user_id: int):
    _ensure_admin(user_id)
    try:
        images = products_service.list_masterclass_images(masterclass_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return {"items": images}


@app.post("/api/admin/masterclasses/{masterclass_id}/images")
def admin_upload_masterclass_images(
    masterclass_id: int,
    files: list[UploadFile] = File(...),
    admin_user=Depends(get_admin_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов для загрузки")

    uploads = [_save_uploaded_image(file, "courses") for file in files]
    urls = [item["url"] for item in uploads]
    try:
        images = products_service.add_masterclass_images(masterclass_id, urls)
    except ValueError:
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return {"items": images, "uploads": uploads}


@app.delete("/api/admin/masterclasses/images/{image_id}")
def admin_delete_masterclass_image(image_id: int, user_id: int):
    _ensure_admin(user_id)
    image_url = products_service.delete_masterclass_image(image_id)
    if not image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    _delete_media_file(image_url)
    return {"ok": True}


@app.get("/api/admin/reviews")
def admin_reviews(
    status: str | None = None,
    product_id: int | None = None,
    user_id: int | None = None,
    page: int = 1,
    limit: int = 50,
    admin_user=Depends(get_admin_user),
):
    reviews = reviews_service.admin_list_reviews(
        status=status, product_id=product_id, user_id=user_id, page=page, limit=limit
    )
    return {"items": reviews, "page": page, "limit": limit}


@app.post("/api/admin/reviews/{review_id}/status")
def admin_update_review_status(
    review_id: int, payload: ReviewStatusUpdatePayload, admin_user=Depends(get_admin_user)
):
    try:
        review = reviews_service.admin_update_review_status(
            review_id, new_status=payload.status, is_deleted=payload.is_deleted
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return {"ok": True, "status": review.status, "is_deleted": review.is_deleted}


@app.get("/api/admin/faq")
def admin_faq_list(user_id: int, category: str | None = None):
    _ensure_admin(user_id)
    items = faq_service.get_faq_list(category)
    return {"items": [_faq_to_dict(item) for item in items]}


@app.post("/api/admin/faq")
def admin_create_faq(payload: FaqCreatePayload, user_id: int):
    _ensure_admin(user_id)
    item = faq_service.create_faq_item(payload.dict())
    return _faq_to_dict(item)


@app.put("/api/admin/faq/{faq_id}")
def admin_update_faq(faq_id: int, payload: FaqUpdatePayload, user_id: int):
    _ensure_admin(user_id)
    data = {key: value for key, value in payload.dict().items() if value is not None}
    item = faq_service.update_faq_item(faq_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return _faq_to_dict(item)


@app.delete("/api/admin/faq/{faq_id}")
def admin_delete_faq(faq_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = faq_service.delete_faq_item(faq_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"ok": True}


@app.get("/api/admin/home/banners")
def admin_home_banners(user_id: int):
    _ensure_admin(user_id)
    items = _wrap_home_banner_error("list", home_service.list_banners)
    return {"items": [item.dict() for item in items]}


@app.post("/api/admin/home/banners")
def admin_create_home_banner(payload: HomeBlockIn, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error("create", lambda: home_service.create_banner(payload))
    return banner.dict()


@app.get("/api/admin/home/banners/{banner_id}")
def admin_get_home_banner(banner_id: int, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error("get", lambda: home_service.get_banner(banner_id))
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    return banner.dict()


@app.put("/api/admin/home/banners/{banner_id}")
def admin_update_home_banner(banner_id: int, payload: HomeBlockIn, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error(
        "update", lambda: home_service.update_banner(banner_id, payload)
    )
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    return banner.dict()


@app.delete("/api/admin/home/banners/{banner_id}")
def admin_delete_home_banner(banner_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = _wrap_home_banner_error("delete", lambda: home_service.delete_banner(banner_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Banner not found")
    return {"ok": True}


@app.get("/api/admin/home/blocks")
def admin_home_blocks(user_id: int):
    _ensure_admin(user_id)
    items = _wrap_home_block_error("list", home_service.list_blocks)
    return {"items": [item.dict() for item in items]}


@app.post("/api/admin/home/blocks")
def admin_create_home_block(payload: HomeBlockIn, user_id: int):
    _ensure_admin(user_id)
    block = _wrap_home_block_error("create", lambda: home_service.create_block(payload))
    return block.dict()


@app.get("/api/admin/home/blocks/{block_id}")
def admin_get_home_block(block_id: int, user_id: int):
    _ensure_admin(user_id)
    block = _wrap_home_block_error("get", lambda: home_service.get_block(block_id))
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block.dict()


@app.put("/api/admin/home/blocks/{block_id}")
def admin_update_home_block(block_id: int, payload: HomeBlockIn, user_id: int):
    _ensure_admin(user_id)
    block = _wrap_home_block_error("update", lambda: home_service.update_block(block_id, payload))
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block.dict()


@app.delete("/api/admin/home/blocks/{block_id}")
def admin_delete_home_block(block_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = _wrap_home_block_error("delete", lambda: home_service.delete_block(block_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Block not found")
    return {"ok": True}


@app.get("/api/admin/home/sections")
def admin_home_sections(user_id: int):
    _ensure_admin(user_id)
    items = home_service.list_sections()
    return {"items": [item.dict() for item in items]}


@app.post("/api/admin/home/sections")
def admin_create_home_section(payload: HomeSectionIn, user_id: int):
    _ensure_admin(user_id)
    section = home_service.create_section(payload)
    return section.dict()


@app.get("/api/admin/home/sections/{section_id}")
def admin_get_home_section(section_id: int, user_id: int):
    _ensure_admin(user_id)
    section = home_service.get_section(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section.dict()


@app.put("/api/admin/home/sections/{section_id}")
def admin_update_home_section(section_id: int, payload: HomeSectionIn, user_id: int):
    _ensure_admin(user_id)
    section = home_service.update_section(section_id, payload)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section.dict()


@app.delete("/api/admin/home/sections/{section_id}")
def admin_delete_home_section(section_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = home_service.delete_section(section_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Section not found")
    return {"ok": True}


@app.get("/api/admin/home/posts")
def admin_home_posts(user_id: int):
    _ensure_admin(user_id)
    items = home_service.list_posts()
    return {"items": [item.dict() for item in items]}


@app.post("/api/admin/home/posts")
def admin_create_home_post(payload: HomePostIn, user_id: int):
    _ensure_admin(user_id)
    post = home_service.create_post(payload)
    return post.dict()


@app.get("/api/admin/home/posts/{post_id}")
def admin_get_home_post(post_id: int, user_id: int):
    _ensure_admin(user_id)
    post = home_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.dict()


@app.put("/api/admin/home/posts/{post_id}")
def admin_update_home_post(post_id: int, payload: HomePostIn, user_id: int):
    _ensure_admin(user_id)
    post = home_service.update_post(post_id, payload)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.dict()


@app.delete("/api/admin/home/posts/{post_id}")
def admin_delete_home_post(post_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = home_service.delete_post(post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"ok": True}


# ----------------------------
# Admin endpoints
# ----------------------------


async def _parse_category_payload(
    request: Request, image_file: UploadFile | None = None, *, is_update: bool = False
) -> tuple[dict[str, Any], UploadFile | None]:
    raw: dict[str, Any] = {}
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("application/json"):
        try:
            raw = await request.json()
        except Exception:
            raw = {}
    else:
        form = await request.form()
        raw = {key: value for key, value in form.items() if not isinstance(value, UploadFile)}
        form_file = form.get("image_file")
        if isinstance(form_file, UploadFile) and image_file is None:
            image_file = form_file

    payload = {
        "user_id": _int_from_any(raw.get("user_id")),
        "name": raw.get("name"),
        "slug": raw.get("slug") or None,
        "description": raw.get("description") or None,
        "image_url": raw.get("image_url") or None,
        "sort_order": _int_from_any(raw.get("sort_order"), 0 if not is_update else None),
        "is_active": _bool_from_any(raw.get("is_active"), None if is_update else True),
        "type": raw.get("type") or ("basket" if not is_update else None),
    }

    if payload["type"] is not None:
        payload["type"] = _validate_category_type(str(payload["type"]))

    if payload["user_id"] is None:
        raise HTTPException(status_code=400, detail="user_id is required")

    if not is_update and not (payload.get("name") and str(payload["name"]).strip()):
        raise HTTPException(status_code=400, detail="name is required")

    return payload, image_file


def _persist_category_image(image_file: UploadFile | None, *, current_url: str | None = None) -> str | None:
    if not image_file:
        return current_url
    upload = _save_uploaded_image(image_file, "categories")
    new_url = upload["url"]
    if current_url and current_url != new_url:
        _delete_media_file(current_url)
    return new_url


@app.get("/api/admin/products")
def admin_products(user_id: int, type: str | None = None, status: str | None = None):
    _ensure_admin(user_id)
    if type:
        _validate_type(type)
    items = products_service.list_products_admin(type, status)
    return {"items": items}


@app.post("/api/admin/products")
def admin_create_product(payload: AdminProductsCreatePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    new_id = products_service.create_product(
        product_type,
        payload.name,
        payload.price,
        payload.stock,
        payload.short_description or None,
        payload.description or "",
        payload.detail_url,
        payload.category_id,
        image=payload.image,
        image_url=payload.image_url,
        wb_url=payload.wb_url,
        ozon_url=payload.ozon_url,
        yandex_url=payload.yandex_url,
        avito_url=payload.avito_url,
        masterclass_url=payload.masterclass_url,
    )
    return {"id": new_id}


@app.put("/api/admin/products/{product_id}")
def admin_update_product(product_id: int, payload: AdminProductsUpdatePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    updated = products_service.update_product_full(
        product_id,
        product_type,
        payload.name,
        payload.price,
        payload.stock,
        payload.short_description or None,
        payload.description or "",
        payload.detail_url,
        payload.category_id,
        payload.is_active,
        image=payload.image,
        image_url=payload.image_url,
        wb_url=payload.wb_url,
        ozon_url=payload.ozon_url,
        yandex_url=payload.yandex_url,
        avito_url=payload.avito_url,
        masterclass_url=payload.masterclass_url,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.patch("/api/admin/products/{product_id}/toggle_active")
@app.post("/api/admin/products/{product_id}/toggle")
def admin_toggle_product(product_id: int, payload: AdminTogglePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    changed = products_service.toggle_product_active(product_id, product_type)
    if not changed:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.get("/api/admin/product-categories")
def admin_product_categories(user_id: int, type: str = "basket"):
    _ensure_admin(user_id)
    product_type = _validate_category_type(type)
    items = products_service.list_product_categories_admin(product_type)
    return {"items": items}


@app.post("/api/admin/product-categories")
async def admin_create_product_category(request: Request, image_file: UploadFile | None = File(None)):
    payload, image_file = await _parse_category_payload(request, image_file=image_file)
    _ensure_admin(payload["user_id"])

    product_type = payload.get("type") or "basket"
    image_url = payload.get("image_url")
    if image_file:
        image_url = _persist_category_image(image_file)

    new_id = products_service.create_product_category(
        payload.get("name") or "Категория",
        slug=payload.get("slug"),
        description=payload.get("description"),
        image_url=image_url,
        sort_order=payload.get("sort_order") or 0,
        is_active=payload.get("is_active") if payload.get("is_active") is not None else True,
        product_type=product_type,
    )
    created_category = products_service.get_product_category_by_id(new_id)
    return {
        "id": new_id,
        "image_url": image_url,
        "page_id": created_category.get("page_id") if created_category else None,
        "page_slug": created_category.get("page_slug") if created_category else None,
    }


@app.put("/api/admin/product-categories/{category_id}")
async def admin_update_product_category(
    category_id: int, request: Request, image_file: UploadFile | None = File(None)
):
    payload, image_file = await _parse_category_payload(request, image_file=image_file, is_update=True)
    _ensure_admin(payload["user_id"])
    product_type = payload.get("type")

    current = products_service.get_product_category_by_id(category_id)
    if not current:
        raise HTTPException(status_code=404, detail="Category not found")

    image_url = payload.get("image_url", current.get("image_url"))
    if image_file:
        image_url = _persist_category_image(image_file, current_url=current.get("image_url"))

    updated = products_service.update_product_category(
        category_id,
        name=payload.get("name"),
        slug=payload.get("slug"),
        description=payload.get("description"),
        image_url=image_url,
        sort_order=payload.get("sort_order"),
        is_active=payload.get("is_active"),
        product_type=product_type,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")
    updated_category = products_service.get_product_category_by_id(category_id)
    return {
        "ok": True,
        "image_url": image_url,
        "page_id": updated_category.get("page_id") if updated_category else None,
        "page_slug": updated_category.get("page_slug") if updated_category else None,
    }


@app.post("/api/admin/product-categories/{category_id}/page")
def admin_ensure_category_page(category_id: int, payload: AdminCategoryPagePayload):
    _ensure_admin(payload.user_id)
    page = products_service.ensure_category_page(category_id, force_create=bool(payload.force))
    if not page:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"page_id": page.get("id"), "page_slug": page.get("slug")}


@app.delete("/api/admin/product-categories/{category_id}")
def admin_delete_product_category(category_id: int, user_id: int):
    _ensure_admin(user_id)
    image_url = products_service.delete_product_category(category_id)
    if image_url is None:
        raise HTTPException(status_code=404, detail="Category not found")
    _delete_media_file(image_url)
    return {"ok": True}


def _serialize_webchat_message(msg) -> dict:
    return {
        "id": msg.id,
        "text": msg.text,
        "sender": msg.sender,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "is_read_by_manager": getattr(msg, "is_read_by_manager", None),
        "is_read_by_client": getattr(msg, "is_read_by_client", None),
    }


@app.get("/api/admin/webchat/sessions", response_model=SupportSessionList)
def admin_webchat_sessions(
    request: Request,
    status: str = "open",
    search: str | None = None,
    page: int = 1,
    limit: int = 50,
    admin: User = Depends(get_admin_user),
):
    normalized_status = status if status != "all" else None
    sessions = webchat_service.list_sessions(
        status=normalized_status, limit=limit, search=search, page=page
    )

    items = []
    for session, last_message in sessions:
        items.append(
            {
                "session_id": int(session.id),
                "session_key": session.session_key or session.session_id,
                "status": session.status,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "user_identifier": session.user_identifier,
                "client_ip": session.client_ip,
                "last_message": last_message.text if last_message else None,
                "last_sender": last_message.sender if last_message else None,
                "last_message_at": session.last_message_at.isoformat()
                if session.last_message_at
                else None,
                "unread_for_manager": int(session.unread_for_manager or 0),
            }
        )

    return {"items": items}


@app.get("/api/admin/webchat/messages", response_model=SupportMessageList)
def admin_webchat_messages(
    session_id: int,
    after_id: int = 0,
    limit: int | None = None,
    admin: User = Depends(get_admin_user),
):
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = webchat_service.get_messages(
        session, limit=limit, after_id=after_id, mark_read_for="manager"
    )
    return {"items": [_serialize_webchat_message(msg) for msg in messages]}


@app.post("/api/admin/webchat/send", response_model=SupportMessage)
def admin_webchat_send(
    payload: AdminWebChatSendPayload, admin: User = Depends(get_admin_user)
):
    if not payload.text:
        raise HTTPException(status_code=400, detail="text is required")

    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message = webchat_service.add_manager_message(session, payload.text)
    return _serialize_webchat_message(message)


@app.post("/api/admin/webchat/close")
def admin_webchat_close(
    payload: AdminWebChatClosePayload, admin: User = Depends(get_admin_user)
):
    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_closed(session)
    return {"ok": True}


@app.post("/api/admin/webchat/reopen")
def admin_webchat_reopen(
    payload: AdminWebChatClosePayload, admin: User = Depends(get_admin_user)
):
    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_open(session)
    return {"ok": True}


@app.get("/api/webchat/sessions", response_model=SupportSessionList)
def api_admin_webchat_sessions(
    status: str = "open",
    search: str | None = None,
    page: int = 1,
    limit: int = 50,
    admin: User = Depends(get_admin_user),
):
    normalized_status = status if status != "all" else None
    sessions = webchat_service.list_sessions(
        status=normalized_status, limit=limit, search=search, page=page
    )

    items: list[dict[str, Any]] = []
    for session, last_message in sessions:
        items.append(
            {
                "session_id": int(session.id),
                "session_key": session.session_key or session.session_id,
                "status": session.status,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "user_identifier": session.user_identifier,
                "client_ip": session.client_ip,
                "last_message_at": session.last_message_at,
                "last_message": last_message.text if last_message else None,
                "last_sender": last_message.sender if last_message else None,
                "unread_for_manager": int(session.unread_for_manager or 0),
            }
        )

    return {"items": items}


@app.get("/api/webchat/sessions/{session_id}", response_model=SupportSessionDetail)
def api_admin_webchat_session_detail(
    session_id: int,
    after_id: int = 0,
    limit: int | None = None,
    admin: User = Depends(get_admin_user),
):
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = webchat_service.get_messages(
        session,
        limit=limit,
        after_id=after_id,
        mark_read_for="manager",
    )

    return {
        "session": {
            "session_id": int(session.id),
            "session_key": session.session_key or session.session_id,
            "status": session.status,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "last_message_at": session.last_message_at,
            "last_message": messages[-1].text if messages else None,
            "last_sender": messages[-1].sender if messages else None,
            "unread_for_manager": int(session.unread_for_manager or 0),
        },
        "messages": [_serialize_webchat_message(msg) for msg in messages],
    }


@app.post("/api/webchat/sessions/{session_id}/reply", response_model=SupportMessage)
def api_admin_webchat_reply(
    session_id: int,
    payload: AdminWebChatReplyBody,
    admin: User = Depends(get_admin_user),
):
    if not payload.text:
        raise HTTPException(status_code=400, detail="text is required")

    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message = webchat_service.add_manager_message(session, payload.text)
    if session.status == "waiting_manager":
        webchat_service.mark_open(session)

    return _serialize_webchat_message(message)


@app.post("/api/webchat/sessions/{session_id}/read")
def api_admin_webchat_mark_read(
    session_id: int,
    payload: AdminWebChatReadPayload = Body(default=AdminWebChatReadPayload()),
    admin: User = Depends(get_admin_user),
):
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_read_for_manager(
        session.id, last_read_message_id=payload.last_read_message_id
    )
    return {"ok": True}


@app.post("/api/webchat/sessions/{session_id}/close")
def api_admin_webchat_close(
    session_id: int, admin: User = Depends(get_admin_user)
):
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_closed(session)
    return {"ok": True}


@app.get("/api/admin/support/sessions", response_model=SupportSessionList)
def admin_support_sessions(user_id: int, status: str = "open", limit: int = 100):
    _ensure_admin(user_id)
    normalized_status = status if status != "all" else None
    sessions = webchat_service.list_sessions(status=normalized_status, limit=limit)

    items = []
    for session, last_message in sessions:
        items.append(
            {
                "session_id": int(session.id),
                "session_key": session.session_key or session.session_id,
                "status": session.status,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "last_message": last_message.text if last_message else None,
                "last_sender": last_message.sender if last_message else None,
            }
        )

    return {"items": items}


@app.get("/api/admin/support/messages", response_model=SupportMessageList)
def admin_support_messages(user_id: int, session_id: int):
    _ensure_admin(user_id)
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = webchat_service.get_messages(
        session, limit=None, mark_read_for="manager"
    )
    return {"items": [_serialize_webchat_message(msg) for msg in messages]}


@app.post("/api/admin/support/message", response_model=SupportMessage)
def admin_support_send_message(user_id: int, payload: AdminSupportMessagePayload):
    _ensure_admin(user_id)
    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message = webchat_service.add_manager_message(session, payload.text)
    if session.status == "waiting_manager":
        webchat_service.mark_open(session)

    return _serialize_webchat_message(message)


@app.post("/api/admin/support/close")
def admin_support_close(user_id: int, payload: AdminSupportClosePayload):
    _ensure_admin(user_id)
    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_closed(session)
    return {"ok": True}


@app.get("/api/admin/orders")
def admin_orders(user_id: int, status: str | None = None, limit: int = 100):
    _ensure_admin(user_id)
    orders = orders_service.list_orders(status=status, limit=limit)
    return {"items": orders}


@app.get("/api/admin/stats")
def admin_stats(user_id: int):
    _ensure_admin(user_id)
    return stats_service.get_admin_dashboard_stats()


@app.get("/api/admin/notes")
def admin_notes(user_id: int, target_id: int):
    _ensure_admin(user_id)
    return {"items": admin_notes_service.list_notes(target_id)}


class AdminNotePayload(BaseModel):
    user_id: int
    target_id: int
    note: str


@app.post("/api/admin/notes")
def admin_add_note(payload: AdminNotePayload):
    _ensure_admin(payload.user_id)
    record = admin_notes_service.add_note(payload.target_id, payload.note, admin_id=payload.user_id)
    return {
        "id": record.id,
        "user_id": record.user_id,
        "admin_id": record.admin_id,
        "note": record.note,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@app.delete("/api/admin/notes/{note_id}")
def admin_delete_note(note_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = admin_notes_service.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


@app.get("/api/admin/orders/{order_id}")
def admin_order_detail(order_id: int, user_id: int):
    _ensure_admin(user_id)
    order = orders_service.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/api/admin/orders/{order_id}/status")
@app.put("/api/admin/orders/{order_id}/status")
def admin_order_set_status(order_id: int, payload: AdminOrderStatusPayload):
    _ensure_admin(payload.user_id)
    if payload.status not in orders_service.STATUS_TITLES:
        raise HTTPException(status_code=400, detail="Invalid status")
    updated = orders_service.update_order_status(order_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders_service.get_order_by_id(order_id)


@app.get("/api/admin/promocodes")
def admin_promocodes(user_id: int):
    _ensure_admin(user_id)
    promos = promocodes_service.list_promocodes()
    return {"items": promos}


@app.post("/api/admin/promocodes")
def admin_create_promocode(payload: AdminPromocodeCreatePayload):
    _ensure_admin(payload.user_id)
    try:
        promo_data = payload.dict()
        promo_data.pop("user_id", None)
        promo = promocodes_service.create_promocode(promo_data)
    except ValueError as exc:  # noqa: WPS440
        raise HTTPException(status_code=400, detail=str(exc))
    return promo


@app.put("/api/admin/promocodes/{promocode_id}")
def admin_update_promocode(promocode_id: int, payload: AdminPromocodeUpdatePayload):
    _ensure_admin(payload.user_id)
    try:
        update_data = payload.dict()
        update_data.pop("user_id", None)
        updated = promocodes_service.update_promocode(promocode_id, update_data)
    except ValueError as exc:  # noqa: WPS440
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return updated


@app.delete("/api/admin/promocodes/{promocode_id}")
def admin_delete_promocode(promocode_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = promocodes_service.delete_promocode(promocode_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return {"ok": True}


@app.get("/", include_in_schema=False)
def webapp_home():
    return _serve_webapp_index()


@app.get("/cart", include_in_schema=False)
def webapp_cart():
    return FileResponse(WEBAPP_DIR / "cart.html", media_type="text/html")


@app.get("/categories", include_in_schema=False)
def categories_page():
    return RedirectResponse(url="/webapp/categories.html", status_code=302)


@app.get("/category/{slug}", include_in_schema=False)
def category_page(slug: str):
    return RedirectResponse(url=f"/c/{slug}", status_code=302)


@app.get("/c/{slug}", include_in_schema=False)
def category_slug_page(slug: str):
    return _serve_webapp_index()


@app.get("/i/{slug}", include_in_schema=False)
def item_slug_page(slug: str):
    return _serve_webapp_index()


@app.get("/p/{slug}", include_in_schema=False)
def product_slug_page(slug: str):
    return _serve_webapp_index()


@app.get("/m/{slug}", include_in_schema=False)
def masterclass_slug_page(slug: str):
    return _serve_webapp_index()


@app.get("/item/{slug}", include_in_schema=False)
def item_page(slug: str):
    return _serve_webapp_index()
