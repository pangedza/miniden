from math import ceil
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models.admin_user import AdminRole
from services.bot_logs import fetch_logs, fetch_user_history
from utils.log_reader import read_tail
from utils.logging_config import API_LOG_FILE, BOT_LOG_FILE

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)
DEFAULT_LIMIT = 200
MAX_LIMIT = 2000

SOURCES: dict[str, Path] = {
    "api": API_LOG_FILE,
    "bot": BOT_LOG_FILE,
}


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot/logs"
    return RedirectResponse(url=f"/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


@router.get("/logs")
async def adminbot_file_logs(
    request: Request,
    source: str = "api",
    limit: int = DEFAULT_LIMIT,
    level: str | None = None,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    normalized_source = source.lower()
    if normalized_source not in SOURCES:
        normalized_source = "api"

    normalized_limit = max(1, min(limit, MAX_LIMIT))
    lines, not_found = read_tail(SOURCES[normalized_source], limit=normalized_limit)

    return TEMPLATES.TemplateResponse(
        "adminbot/logs.html",
        {
            "request": request,
            "lines": lines,
            "selected_source": normalized_source,
            "limit": normalized_limit,
            "not_found": not_found,
            "sources": SOURCES,
            "selected_level": (level or "").upper(),
        },
    )


@router.get("/logs/history")
async def bot_logs_history(
    request: Request,
    page: int = 1,
    event_type: str | None = None,
    user_id: str | None = None,
    username: str | None = None,
    node_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    per_page = 50
    logs, total = fetch_logs(
        db,
        page=page,
        per_page=per_page,
        event_type=event_type,
        user_id=user_id,
        username=username,
        node_code=node_code,
        date_from=date_from,
        date_to=date_to,
    )

    total_pages = ceil(total / per_page) if total else 1

    base_params = {
        "event_type": (event_type or "").strip(),
        "user_id": (user_id or "").strip(),
        "username": (username or "").strip(),
        "node_code": (node_code or "").strip(),
        "date_from": date_from or "",
        "date_to": date_to or "",
    }

    def _page_url(target_page: int) -> str:
        params = {**base_params, "page": target_page}
        normalized = {k: v for k, v in params.items() if v}
        return f"/adminbot/logs/history?{urlencode(normalized)}"

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    return TEMPLATES.TemplateResponse(
        "adminbot_logs.html",
        {
            "request": request,
            "logs": logs,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "prev_url": _page_url(prev_page) if prev_page else None,
            "next_url": _page_url(next_page) if next_page else None,
            "filters": base_params,
        },
    )


@router.get("/users/{user_id}/logs")
async def user_logs(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    history = fetch_user_history(db, user_id=user_id, limit=500)

    return TEMPLATES.TemplateResponse(
        "adminbot_user_logs.html",
        {
            "request": request,
            "logs": history,
            "target_user_id": user_id,
        },
    )
