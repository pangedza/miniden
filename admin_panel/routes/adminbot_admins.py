"""Управление администраторами внутри AdminBot."""

from datetime import datetime
from typing import Iterable

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models.admin_user import AdminRole, AdminUser, AdminRoleModel
from services import auth as auth_service
from services.passwords import hash_password, verify_password

router = APIRouter(prefix="/adminbot", tags=["AdminBotAdmins"])

ADMIN_ROLES = (
    AdminRole.superadmin,
    AdminRole.admin_bot,
    AdminRole.moderator,
    AdminRole.viewer,
)


def _login_redirect(next_url: str) -> RedirectResponse:
    return RedirectResponse(url=f"/adminbot/login?next={next_url}", status_code=303)


def _active_superadmins_count(db: Session) -> int:
    return db.query(AdminUser).filter(
        AdminUser.is_active.is_(True),
        or_(
            AdminUser.role == AdminRole.superadmin.value,
            AdminUser.roles.any(AdminRoleModel.code == AdminRole.superadmin.value),
        ),
    ).count()


def _load_roles(db: Session) -> list[AdminRoleModel]:
    return db.query(AdminRoleModel).order_by(AdminRoleModel.id.asc()).all()


def _assign_roles(user: AdminUser, role_codes: Iterable[str], db: Session) -> None:
    roles = (
        db.query(AdminRoleModel)
        .filter(AdminRoleModel.code.in_(list(role_codes)))
        .all()
    )
    user.roles = roles
    user.role = roles[0].code if roles else AdminRole.viewer.value


def _render_admins(
    request: Request,
    db: Session,
    current_user: AdminUser,
    *,
    error: str | None = None,
    message: str | None = None,
):
    users = db.query(AdminUser).order_by(AdminUser.id.asc()).all()
    roles = _load_roles(db)
    return TEMPLATES.TemplateResponse(
        "adminbot/admins_list.html",
        {
            "request": request,
            "user": current_user,
            "users": users,
            "roles": roles,
            "error": error,
            "message": message,
            "can_manage_admins": True,
        },
    )


@router.get("/admins")
async def admins_list(request: Request, db: Session = Depends(get_db_session)):
    current_user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not current_user:
        return _login_redirect("/adminbot/admins")

    message = request.query_params.get("message")
    return _render_admins(request, db, current_user=current_user, message=message)


@router.get("/admins/new")
async def admin_new_form(request: Request, db: Session = Depends(get_db_session)):
    current_user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not current_user:
        return _login_redirect("/adminbot/admins/new")

    return TEMPLATES.TemplateResponse(
        "adminbot/admin_edit.html",
        {
            "request": request,
            "user": current_user,
            "roles": _load_roles(db),
            "target": None,
            "error": None,
            "can_manage_admins": True,
        },
    )


@router.post("/admins/new")
async def admin_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    roles: list[str] = Form([]),
    is_active: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    current_user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not current_user:
        return _login_redirect("/adminbot/admins/new")

    username = username.strip()
    if not username:
        return _render_admins(
            request, db, current_user=current_user, error="Логин обязателен"
        )

    if not password:
        return _render_admins(
            request, db, current_user=current_user, error="Пароль обязателен"
        )

    target_roles = [code for code in roles if code]
    if not target_roles:
        return _render_admins(
            request, db, current_user=current_user, error="Нужно выбрать хотя бы одну роль"
        )

    existing = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing:
        return _render_admins(
            request, db, current_user=current_user, error="Логин уже занят"
        )

    user = AdminUser(
        username=username,
        password_hash=hash_password(password),
        is_active=is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()
    _assign_roles(user, target_roles, db)
    db.add(user)
    db.commit()
    db.refresh(user)

    return RedirectResponse(url="/adminbot/admins?message=Администратор создан", status_code=303)


@router.get("/admins/{user_id}/edit")
async def admin_edit_form(
    request: Request, user_id: int, db: Session = Depends(get_db_session)
):
    current_user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not current_user:
        return _login_redirect(f"/adminbot/admins/{user_id}/edit")

    target = db.get(AdminUser, user_id)
    if not target:
        return RedirectResponse(url="/adminbot/admins", status_code=303)

    return TEMPLATES.TemplateResponse(
        "adminbot/admin_edit.html",
        {
            "request": request,
            "user": current_user,
            "roles": _load_roles(db),
            "target": target,
            "error": None,
            "can_manage_admins": True,
        },
    )


@router.post("/admins/{user_id}/edit")
async def admin_update(
    request: Request,
    user_id: int,
    username: str = Form(...),
    roles: list[str] = Form([]),
    is_active: bool = Form(False),
    new_password: str | None = Form(None),
    db: Session = Depends(get_db_session),
):
    current_user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not current_user:
        return _login_redirect(f"/adminbot/admins/{user_id}/edit")

    target = db.get(AdminUser, user_id)
    if not target:
        return RedirectResponse(url="/adminbot/admins", status_code=303)

    username = username.strip()
    if not username:
        return _render_admins(
            request, db, current_user=current_user, error="Логин обязателен"
        )

    target_roles = [code for code in roles if code]
    if not target_roles:
        return _render_admins(
            request, db, current_user=current_user, error="Нужно выбрать хотя бы одну роль"
        )

    exists = (
        db.query(AdminUser)
        .filter(AdminUser.username == username, AdminUser.id != target.id)
        .first()
    )
    if exists:
        return _render_admins(
            request, db, current_user=current_user, error="Логин уже занят"
        )

    if target.has_role(AdminRole.superadmin.value) and (
        AdminRole.superadmin.value not in target_roles or not is_active
    ):
        if _active_superadmins_count(db) <= 1:
            return _render_admins(
                request,
                db,
                current_user=current_user,
                error="Нельзя отключить последнего суперадмина",
            )

    target.username = username
    target.is_active = is_active
    if new_password:
        target.password_hash = hash_password(new_password)
        auth_service.invalidate_user_sessions(db, target.id)

    _assign_roles(target, target_roles, db)

    db.add(target)
    db.commit()

    return RedirectResponse(url="/adminbot/admins?message=Сохранено", status_code=303)


@router.post("/admins/{user_id}/resetpass")
async def admin_reset_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    db: Session = Depends(get_db_session),
):
    current_user = require_admin(request, db, roles=(AdminRole.superadmin,))
    if not current_user:
        return _login_redirect(f"/adminbot/admins/{user_id}/edit")

    target = db.get(AdminUser, user_id)
    if not target:
        return RedirectResponse(url="/adminbot/admins", status_code=303)

    if not new_password:
        return _render_admins(
            request, db, current_user=current_user, error="Пароль обязателен"
        )

    target.password_hash = hash_password(new_password)
    auth_service.invalidate_user_sessions(db, target.id)
    db.add(target)
    db.commit()

    return RedirectResponse(
        url="/adminbot/admins?message=Пароль обновлён", status_code=303
    )


@router.get("/profile")
async def profile(request: Request, db: Session = Depends(get_db_session)):
    current_user = require_admin(request, db, roles=ADMIN_ROLES)
    if not current_user:
        return _login_redirect("/adminbot/profile")

    message = request.query_params.get("message")
    return TEMPLATES.TemplateResponse(
        "adminbot/profile.html",
        {
            "request": request,
            "user": current_user,
            "error": None,
            "message": message,
            "can_manage_admins": current_user.has_role(AdminRole.superadmin.value),
        },
    )


@router.post("/profile/password")
async def change_password(
    request: Request,
    old_password: str = Form(""),
    new_password: str = Form(""),
    new_password_confirm: str = Form(""),
    db: Session = Depends(get_db_session),
):
    current_user = require_admin(request, db, roles=ADMIN_ROLES)
    if not current_user:
        return _login_redirect("/adminbot/profile")

    error = None
    if not old_password or not verify_password(old_password, current_user.password_hash):
        error = "Неверный текущий пароль"
    elif not new_password:
        error = "Новый пароль обязателен"
    elif new_password != new_password_confirm:
        error = "Пароли не совпадают"

    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot/profile.html",
            {
                "request": request,
                "user": current_user,
                "error": error,
                "message": None,
                "can_manage_admins": current_user.has_role(AdminRole.superadmin.value),
            },
            status_code=400,
        )

    current_user.password_hash = hash_password(new_password)
    current_user.updated_at = datetime.utcnow()
    db.add(current_user)
    db.commit()

    auth_service.invalidate_user_sessions(db, current_user.id)
    new_session = auth_service.create_session(db, current_user)

    redirect = RedirectResponse(
        url="/adminbot/profile?message=Пароль обновлён", status_code=303
    )
    max_age = int((new_session.expires_at - datetime.utcnow()).total_seconds())
    from admin_panel.dependencies import SESSION_COOKIE_NAME

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
