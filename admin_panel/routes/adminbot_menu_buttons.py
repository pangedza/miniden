from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotRuntime, MenuButton
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot, AdminRole.moderator)
ACTION_TYPES = {"node", "command", "url", "webapp"}


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


def _normalize_int(value: str | int | None, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default
        return int(value)
    except Exception:
        return default


def _bump_runtime(db: Session) -> None:
    runtime = db.query(BotRuntime).first()
    if not runtime:
        runtime = BotRuntime(config_version=1)
    runtime.config_version = (runtime.config_version or 1) + 1
    db.add(runtime)


def _is_valid_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _prepare_menu_button_payload(
    *,
    text: str | None,
    action_type: str | None,
    action_payload: str | None,
    row: str | int | None,
    position: str | int | None,
    is_active: bool,
) -> tuple[str | None, dict]:
    clean_text = (text or "").strip()
    if not clean_text:
        return "Укажите текст кнопки", {}

    normalized_type = (action_type or "node").strip().lower()
    if normalized_type not in ACTION_TYPES:
        return "Некорректный тип действия", {}

    payload_value = (action_payload or "").strip()
    if normalized_type == "node" and not payload_value:
        return "Укажите код узла для перехода", {}
    if normalized_type == "command" and not payload_value:
        return "Укажите команду для запуска", {}
    if normalized_type in {"url", "webapp"} and not _is_valid_url(payload_value):
        return "Укажите корректную ссылку (http/https)", {}

    prepared = {
        "text": clean_text,
        "action_type": normalized_type,
        "action_payload": payload_value or None,
        "row": _normalize_int(row, 0),
        "position": _normalize_int(position, 0),
        "is_active": bool(is_active),
    }
    return None, prepared


@router.get("/menu-buttons")
async def menu_buttons_list(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(request.url.path)

    buttons = (
        db.query(MenuButton)
        .order_by(MenuButton.row, MenuButton.position, MenuButton.id)
        .all()
    )
    return TEMPLATES.TemplateResponse(
        "adminbot_menu_buttons_list.html",
        {"request": request, "user": user, "buttons": buttons},
    )


@router.get("/menu-buttons/new")
async def new_menu_button_form(
    request: Request, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    return TEMPLATES.TemplateResponse(
        "adminbot_menu_button_edit.html",
        {"request": request, "user": user, "button": None, "error": None},
    )


@router.post("/menu-buttons/new")
async def create_menu_button(
    request: Request,
    text: str = Form(...),
    action_type: str = Form("node"),
    action_payload: str | None = Form(None),
    row: str | None = Form(None),
    position: str | None = Form(None),
    is_active: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    error, payload = _prepare_menu_button_payload(
        text=text,
        action_type=action_type,
        action_payload=action_payload,
        row=row,
        position=position,
        is_active=is_active,
    )

    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_menu_button_edit.html",
            {
                "request": request,
                "user": user,
                "button": None,
                "error": error,
            },
            status_code=422,
        )

    db.add(MenuButton(**payload))
    _bump_runtime(db)
    db.commit()

    return RedirectResponse(url="/adminbot/menu-buttons", status_code=303)


@router.get("/menu-buttons/{button_id}/edit")
async def edit_menu_button_form(
    request: Request, button_id: int, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    button = db.get(MenuButton, button_id)
    if not button:
        return RedirectResponse(url="/adminbot/menu-buttons", status_code=303)

    return TEMPLATES.TemplateResponse(
        "adminbot_menu_button_edit.html",
        {"request": request, "user": user, "button": button, "error": None},
    )


@router.post("/menu-buttons/{button_id}/edit")
async def edit_menu_button(
    request: Request,
    button_id: int,
    text: str = Form(...),
    action_type: str = Form("node"),
    action_payload: str | None = Form(None),
    row: str | None = Form(None),
    position: str | None = Form(None),
    is_active: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    button = db.get(MenuButton, button_id)
    if not button:
        return RedirectResponse(url="/adminbot/menu-buttons", status_code=303)

    error, payload = _prepare_menu_button_payload(
        text=text,
        action_type=action_type,
        action_payload=action_payload,
        row=row,
        position=position,
        is_active=is_active,
    )

    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_menu_button_edit.html",
            {
                "request": request,
                "user": user,
                "button": button,
                "error": error,
            },
            status_code=422,
        )

    for key, value in payload.items():
        setattr(button, key, value)

    db.add(button)
    _bump_runtime(db)
    db.commit()

    return RedirectResponse(url="/adminbot/menu-buttons", status_code=303)


@router.post("/menu-buttons/{button_id}/delete")
async def deactivate_menu_button(
    request: Request, button_id: int, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    button = db.get(MenuButton, button_id)
    if not button:
        return RedirectResponse(url="/adminbot/menu-buttons", status_code=303)

    button.is_active = False
    db.add(button)
    _bump_runtime(db)
    db.commit()

    return RedirectResponse(url="/adminbot/menu-buttons", status_code=303)


@router.post("/menu-buttons/{button_id}/activate")
async def activate_menu_button(
    request: Request, button_id: int, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    button = db.get(MenuButton, button_id)
    if not button:
        return RedirectResponse(url="/adminbot/menu-buttons", status_code=303)

    button.is_active = True
    db.add(button)
    _bump_runtime(db)
    db.commit()

    return RedirectResponse(url="/adminbot/menu-buttons", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"
