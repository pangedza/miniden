"""Управление администраторами и профилем."""

from datetime import datetime
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import SESSION_COOKIE_NAME, get_db_session, require_admin
from models.admin_user import AdminRole, AdminUser
from services import auth as auth_service
from services.passwords import hash_password, verify_password

router = APIRouter(prefix="/admin", tags=["AdminUsers"])


def _login_redirect(next_url: str) -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={next_url}", status_code=303)


def _render_users_page(
    request: Request,
    db: Session,
    current_user: AdminUser,
    error: str | None = None,
    message: str | None = None,
):
    users = db.query(AdminUser).order_by(AdminUser.id.asc()).all()
    return TEMPLATES.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "user": current_user,
            "users": users,
            "error": error,
            "message": message,
            "roles": [role.value for role in AdminRole],
        },
    )


def _active_superadmins_count(db: Session) -> int:
    return (
        db.query(AdminUser)
        .filter(
            AdminUser.role == AdminRole.superadmin.value,
            AdminUser.is_active.is_(True),
        )
        .count()
    )


def _parse_role(role_value: str) -> Optional[str]:
    for role in AdminRole:
        if role.value == role_value:
            return role.value
    return None


@router.get("/users")
async def list_admins(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not user:
        return _login_redirect("/admin/users")

    message = request.query_params.get("message")
    return _render_users_page(request, db, current_user=user, message=message)


@router.post("/users")
async def create_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(AdminRole.admin_bot.value),
    is_active: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not user:
        return _login_redirect("/admin/users")

    username = username.strip()
    role_value = _parse_role(role)
    if not role_value:
        return _render_users_page(
            request, db, current_user=user, error="Неверная роль пользователя"
        )

    if not password:
        return _render_users_page(
            request, db, current_user=user, error="Пароль обязателен",
        )

    existing = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing:
        return _render_users_page(
            request, db, current_user=user, error="Логин уже занят",
        )

    db.add(
        AdminUser(
            username=username,
            password_hash=hash_password(password),
            role=role_value,
            is_active=is_active,
        )
    )
    db.commit()

    return RedirectResponse(url="/admin/users?message=Пользователь создан", status_code=303)


@router.post("/users/{user_id}")
async def update_admin(
    request: Request,
    user_id: int,
    username: str = Form(...),
    role: str = Form(AdminRole.admin_bot.value),
    is_active: bool = Form(False),
    new_password: str | None = Form(None),
    db: Session = Depends(get_db_session),
):
    current_user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not current_user:
        return _login_redirect("/admin/users")

    target = db.get(AdminUser, user_id)
    if not target:
        return RedirectResponse(url="/admin/users", status_code=303)

    role_value = _parse_role(role)
    if not role_value:
        return _render_users_page(
            request, db, current_user=current_user, error="Неверная роль пользователя"
        )

    username = username.strip()
    existing = (
        db.query(AdminUser)
        .filter(AdminUser.username == username, AdminUser.id != target.id)
        .first()
    )
    if existing:
        return _render_users_page(
            request, db, current_user=current_user, error="Логин уже занят"
        )

    if target.role == AdminRole.superadmin.value and (
        role_value != AdminRole.superadmin.value or not is_active
    ):
        if _active_superadmins_count(db) <= 1:
            return _render_users_page(
                request,
                db,
                current_user=current_user,
                error="Нельзя отключить или разжаловать последнего супер-админа",
            )

    target.username = username
    target.role = role_value
    target.is_active = is_active

    if new_password:
        target.password_hash = hash_password(new_password)
        auth_service.invalidate_user_sessions(db, target.id)

    db.add(target)
    db.commit()

    return RedirectResponse(url="/admin/users?message=Сохранено", status_code=303)


@router.post("/users/{user_id}/reset_password")
async def reset_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    db: Session = Depends(get_db_session),
):
    current_user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not current_user:
        return _login_redirect("/admin/users")

    target = db.get(AdminUser, user_id)
    if not target:
        return RedirectResponse(url="/admin/users", status_code=303)

    if not new_password:
        return _render_users_page(
            request,
            db,
            current_user=current_user,
            error="Новый пароль обязателен",
        )

    target.password_hash = hash_password(new_password)
    auth_service.invalidate_user_sessions(db, target.id)
    db.add(target)
    db.commit()

    return RedirectResponse(url="/admin/users?message=Пароль обновлён", status_code=303)


@router.get("/profile")
async def profile(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db)
    if not user:
        return _login_redirect("/admin/profile")

    message = request.query_params.get("message")
    return TEMPLATES.TemplateResponse(
        "admin_profile.html",
        {
            "request": request,
            "user": user,
            "error": None,
            "message": message,
        },
    )


@router.post("/profile")
async def update_profile(
    request: Request,
    username: str = Form(...),
    old_password: str = Form(""),
    new_password: str = Form(""),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db)
    if not user:
        return _login_redirect("/admin/profile")

    username = username.strip()
    error = None
    new_session = None

    existing = (
        db.query(AdminUser)
        .filter(AdminUser.username == username, AdminUser.id != user.id)
        .first()
    )
    if existing:
        error = "Такое имя пользователя уже занято"

    if new_password:
        if not old_password or not verify_password(old_password, user.password_hash):
            error = "Неверный текущий пароль"
        else:
            user.password_hash = hash_password(new_password)
            auth_service.invalidate_user_sessions(db, user.id)
            new_session = auth_service.create_session(db, user)

    if error:
        return TEMPLATES.TemplateResponse(
            "admin_profile.html",
            {
                "request": request,
                "user": user,
                "error": error,
                "message": None,
            },
            status_code=400,
        )

    user.username = username
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()

    redirect = RedirectResponse(
        url="/admin/profile?message=Профиль обновлён", status_code=303
    )

    if new_session:
        max_age = int((new_session.expires_at - datetime.utcnow()).total_seconds())
        redirect.set_cookie(
            SESSION_COOKIE_NAME,
            new_session.token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=max_age,
            path="/",
        )

    return redirect
