"""Маршруты авторизации админов."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import SESSION_COOKIE_NAME, get_db_session
from services import auth as auth_service

router = APIRouter(tags=["AdminAuth"])


def _normalize_next_url(next_url: str | None) -> str:
    if not next_url or not next_url.startswith("/"):
        return "/adminbot"
    return next_url


@router.get("/login")
async def login_form(request: Request, next: str | None = None):
    return TEMPLATES.TemplateResponse(
        "login.html",
        {"request": request, "error": None, "next": _normalize_next_url(next)},
    )


@router.post("/login")
async def login(
    request: Request,
    next: str = Form("/adminbot"),
    db: Session = Depends(get_db_session),
):
    form = await request.form()

    username = (
        form.get("username")
        or form.get("login")
        or form.get("логин")
    )
    password = (
        form.get("password")
        or form.get("pass")
        or form.get("пароль")
    )

    normalized_next = _normalize_next_url(form.get("next") or next)

    user = auth_service.authenticate_admin(db, username or "", password or "")
    if not user:
        return TEMPLATES.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Неверный логин или пароль",
                "next": normalized_next,
            },
            status_code=400,
        )

    session = auth_service.create_session(db, user)
    max_age = int((session.expires_at - datetime.utcnow()).total_seconds())
    response = RedirectResponse(url=normalized_next, status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session.token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(request: Request, db: Session = Depends(get_db_session)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        auth_service.remove_session(db, token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/logout")
async def logout_get(request: Request, db: Session = Depends(get_db_session)):
    return await logout(request, db)
