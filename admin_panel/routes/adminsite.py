"""Маршруты AdminSite."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.auth import create_session, delete_session, verify_password
from admin_panel.dependencies import COOKIE_NAMES, get_db_session, require_admin
from models import AdminUser

router = APIRouter(prefix="/adminsite", tags=["AdminSite"])


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/adminsite/login", status_code=303)


@router.get("/login")
async def login_form(request: Request):
    return TEMPLATES.TemplateResponse(
        "adminsite/login.html",
        {"request": request, "error": None},
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_session),
):
    user: AdminUser | None = (
        db.query(AdminUser)
        .filter(AdminUser.username == username, AdminUser.is_active.is_(True))
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return TEMPLATES.TemplateResponse(
            "adminsite/login.html",
            {"request": request, "error": "Неверный логин или пароль"},
            status_code=400,
        )

    session = create_session(db, user, app_name="adminsite")
    response = RedirectResponse(url="/adminsite", status_code=303)
    max_age = int((session.expires_at - datetime.utcnow()).total_seconds())
    response.set_cookie(
        COOKIE_NAMES["adminsite"],
        session.token,
        httponly=True,
        max_age=max_age,
        path="/adminsite",
    )
    return response


@router.get("/")
async def dashboard(
    request: Request, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, app_name="adminsite")
    if not user:
        return _login_redirect()

    return TEMPLATES.TemplateResponse(
        "adminsite/dashboard.html", {"request": request, "user": user}
    )


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db_session)):
    token = request.cookies.get(COOKIE_NAMES["adminsite"])
    if token:
        delete_session(db, token)
    response = _login_redirect()
    response.delete_cookie(COOKIE_NAMES["adminsite"], path="/adminsite")
    return response
