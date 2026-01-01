"""Маршруты AdminBot."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from admin_panel.routes import auth as auth_routes
from models.admin_user import AdminRole

from . import (
    adminbot_buttons,
    adminbot_admins,
    adminbot_media,
    adminbot_logs,
    adminbot_nodes,
    adminbot_menu_buttons,
    adminbot_runtime,
    adminbot_templates,
    adminbot_triggers,
)

router = APIRouter(prefix="/adminbot", tags=["AdminBot"])


ALLOWED_ROLES = (
    AdminRole.superadmin,
    AdminRole.admin_bot,
    AdminRole.moderator,
    AdminRole.viewer,
)


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


@router.get("/login")
async def login_form(request: Request):
    return await auth_routes.login_form(request, next="/adminbot")


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_session),
):
    return await auth_routes.login(
        request, username=username, password=password, next="/adminbot", db=db
    )


@router.get("/")
async def dashboard(
    request: Request, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(request.url.path)

    return TEMPLATES.TemplateResponse(
        "adminbot/dashboard.html", {"request": request, "user": user}
    )


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db_session)):
    return await auth_routes.logout(request, db)


router.include_router(adminbot_nodes.router)
router.include_router(adminbot_buttons.router)
router.include_router(adminbot_menu_buttons.router)
router.include_router(adminbot_triggers.router)
router.include_router(adminbot_runtime.router)
router.include_router(adminbot_logs.router)
router.include_router(adminbot_templates.router)
router.include_router(adminbot_admins.router)
router.include_router(adminbot_media.router)
