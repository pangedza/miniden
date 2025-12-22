"""Управление версией конфигурации бота."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotRuntime
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _get_runtime(db: Session) -> BotRuntime:
    runtime = db.query(BotRuntime).first()
    if not runtime:
        runtime = BotRuntime(config_version=1, start_node_code="MAIN_MENU")
        db.add(runtime)
        db.commit()
        db.refresh(runtime)
    return runtime


@router.get("/runtime")
async def runtime_page(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    runtime = _get_runtime(db)
    return TEMPLATES.TemplateResponse(
        "adminbot_runtime.html",
        {
            "request": request,
            "user": user,
            "runtime": runtime,
        },
    )


@router.post("/runtime")
async def update_runtime_settings(
    request: Request,
    action: str = Form("bump"),
    start_node_code: str | None = Form(None),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    runtime = _get_runtime(db)

    if action == "update_start":
        runtime.start_node_code = (start_node_code or "MAIN_MENU").strip() or "MAIN_MENU"
        runtime.config_version = (runtime.config_version or 1) + 1
    else:
        runtime.config_version = (runtime.config_version or 1) + 1

    db.add(runtime)
    db.commit()

    return RedirectResponse(url="/adminbot/runtime", status_code=303)
