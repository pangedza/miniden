"""
Основной backend MiniDeN (FastAPI).
Приложение: webapi:app
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import NoMatchFound

from admin_panel import STATIC_DIR
from admin_panel.adminsite import ADMINSITE_STATIC_ROOT
from initdb import init_db
from media_paths import MEDIA_ROOT, ensure_media_dirs
from routes_adminbot import router as adminbot_router
from routes_adminsite import router as adminsite_router
from routes_auth import router as auth_router
from routes_public import BUILD_COMMIT, STATIC_DIR_PUBLIC, WEBAPP_DIR, router as public_router
from utils.logging_config import API_LOG_FILE, setup_logging

ADMINSITE_STATIC_PATH = ADMINSITE_STATIC_ROOT.resolve()
setup_logging(log_file=API_LOG_FILE)

app = FastAPI(title="MiniDeN Web API", version="1.0.0")

logger = logging.getLogger(__name__)


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


@app.exception_handler(Exception)
async def json_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: WPS430
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if request.headers.get("content-type") == "text/html":
        rendered_errors = [
            f"{item.get('loc')} — {item.get('msg')}" for item in exc.errors()
        ]
        content = """
        <html>
            <head>
                <title>Validation Error</title>
            </head>
            <body>
                <h1>Validation Error</h1>
                <ul>
                    {errors}
                </ul>
            </body>
        </html>
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


@app.on_event("startup")
def startup_event() -> None:
    ensure_media_dirs()
    if os.getenv("INIT_DB_ON_STARTUP") == "1":
        init_db()
    else:
        logger.info("init_db skipped; set INIT_DB_ON_STARTUP=1 to enable")

    static_dir = ADMINSITE_STATIC_ROOT.resolve()
    logger.info(
        "AdminSite static root: %s (constructor.js exists=%s)",
        static_dir,
        (static_dir / "adminsite/constructor.js").exists(),
    )


# Keep admin/site routers below static mounts so catch-all paths never override /static.
app.include_router(auth_router)
app.include_router(adminbot_router)
app.include_router(adminsite_router)
app.include_router(public_router)
