"""Маршруты AdminSite."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from admin_panel.routes import auth as auth_routes
from models.admin_user import AdminRole

router = APIRouter(prefix="/adminsite", tags=["AdminSite"])


ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_site)


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login?next=/adminsite", status_code=303)


@router.get("/login")
async def login_form(request: Request):
    return await auth_routes.login_form(request, next="/adminsite")


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_session),
):
    return await auth_routes.login(
        request, username=username, password=password, next="/adminsite", db=db
    )


@router.get("/")
async def dashboard(
    request: Request, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect()

    return TEMPLATES.TemplateResponse(
        "adminsite/dashboard.html", {"request": request, "user": user}
    )


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db_session)):
    return await auth_routes.logout(request, db)
