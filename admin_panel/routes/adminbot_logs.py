from math import ceil
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models.admin_user import AdminRole
from services.bot_logs import fetch_logs, fetch_user_history

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot/logs"
    return RedirectResponse(url=f"/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


@router.get("/adminbot/logs")
async def bot_logs(
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
        return f"/adminbot/logs?{urlencode(normalized)}"

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


@router.get("/adminbot/users/{user_id}/logs")
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
