"""Маршруты AdminSite."""

from datetime import datetime
import logging
import traceback

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from admin_panel.dependencies import (
    SESSION_COOKIE_NAME,
    get_db_session,
    require_admin,
)
from admin_panel.adminsite import (
    ADMINSITE_CONSTRUCTOR_PATH,
    ADMINSITE_STATIC_DIR,
    ADMINSITE_STATIC_ROOT,
    TEMPLATES,
)
from admin_panel.routes import auth as auth_routes
from models.admin_user import AdminRole
from services import auth as auth_service

router = APIRouter(prefix="/adminsite", tags=["AdminSite"])


logger = logging.getLogger(__name__)
ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_site)


def _render_login_page(request: Request):
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"

    normalized_next = auth_routes._normalize_next_url(next_path or "/adminsite")

    return TEMPLATES.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": None,
            "next": normalized_next,
        },
    )


@router.get("/_debug_static")
async def debug_static_assets() -> dict[str, str | bool]:
    base_css = ADMINSITE_STATIC_DIR / "base.css"
    constructor_js = ADMINSITE_CONSTRUCTOR_PATH
    return {
        "static_root": str(ADMINSITE_STATIC_ROOT),
        "base_css_exists": base_css.exists(),
        "constructor_js_exists": constructor_js.exists(),
    }


@router.get("/login")
async def login_form(request: Request):
    return TEMPLATES.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": None,
            "next": auth_routes._normalize_next_url("/adminsite"),
        },
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_session),
):
    form = await request.form()

    normalized_next = auth_routes._normalize_next_url(
        form.get("next") or "/adminsite"
    )

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


@router.get("/")
async def dashboard(
    request: Request, db: Session = Depends(get_db_session)
):
    try:
        user = require_admin(request, db, roles=ALLOWED_ROLES)
        if not user:
            return _render_login_page(request)

        return TEMPLATES.TemplateResponse(
            "dashboard.html", {"request": request, "user": user}
        )
    except Exception:  # noqa: WPS329 - log full traceback for diagnostics
        logger.exception("Failed to render /adminsite dashboard")
        print(traceback.format_exc())
        raise


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db_session)):
    return await auth_routes.logout(request, db)


@router.get("/constructor")
async def constructor(
    request: Request, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _render_login_page(request)

    return TEMPLATES.TemplateResponse(
        "constructor.html", {"request": request, "user": user}
    )
