"""CRUD для кнопок узлов бота."""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotButton, BotNode
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)


BUTTON_TYPES = [
    ("callback", "Callback"),
    ("url", "URL"),
    ("webapp", "WebApp"),
]


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _validate_button_payload(button_type: str, payload: str) -> str | None:
    if button_type == "callback":
        if ":" not in payload:
            return "Формат payload для callback: ACTION:VALUE"
    elif button_type in {"url", "webapp"}:
        parsed = urlparse(payload)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "Payload должен быть валидной http(s) ссылкой"
    else:
        return "Неизвестный тип кнопки"
    return None


def _get_node(db: Session, node_id: int) -> BotNode | None:
    return db.get(BotNode, node_id)


def _normalize_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    value = value.strip()
    if not value:
        return default
    try:
        return int(value)
    except Exception:
        return default


@router.get("/nodes/{node_id}/buttons")
async def list_buttons(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = _get_node(db, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    buttons = (
        db.query(BotButton)
        .filter(BotButton.node_id == node.id)
        .order_by(BotButton.row, BotButton.pos, BotButton.id)
        .all()
    )

    return TEMPLATES.TemplateResponse(
        "adminbot_buttons_list.html",
        {
            "request": request,
            "user": user,
            "node": node,
            "buttons": buttons,
        },
    )


@router.get("/nodes/{node_id}/buttons/new")
async def new_button_form(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = _get_node(db, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    return TEMPLATES.TemplateResponse(
        "adminbot_button_edit.html",
        {
            "request": request,
            "user": user,
            "node": node,
            "button": None,
            "button_types": BUTTON_TYPES,
            "error": None,
        },
    )


@router.post("/nodes/{node_id}/buttons/new")
async def create_button(
    request: Request,
    node_id: int,
    title: str = Form(...),
    button_type: str = Form(..., alias="type"),
    payload: str = Form(...),
    row: str | None = Form(None),
    pos: str | None = Form(None),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = _get_node(db, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    row_value = _normalize_int(row)
    pos_value = _normalize_int(pos)

    error = _validate_button_payload(button_type, payload)
    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_button_edit.html",
            {
                "request": request,
                "user": user,
                "node": node,
                "button": None,
            "button_types": BUTTON_TYPES,
            "error": error,
        },
        status_code=400,
    )

    db.add(
        BotButton(
            node_id=node.id,
            title=title,
            type=button_type,
            payload=payload,
            row=row_value,
            pos=pos_value,
            is_enabled=is_enabled,
        )
    )
    db.commit()

    return RedirectResponse(url=f"/adminbot/nodes/{node.id}/buttons", status_code=303)


@router.get("/buttons/{button_id}/edit")
async def edit_button_form(
    request: Request,
    button_id: int,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    button = db.get(BotButton, button_id)
    if not button:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    node = _get_node(db, button.node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    return TEMPLATES.TemplateResponse(
        "adminbot_button_edit.html",
        {
            "request": request,
            "user": user,
            "node": node,
            "button": button,
            "button_types": BUTTON_TYPES,
            "error": None,
        },
    )


@router.post("/buttons/{button_id}/edit")
async def update_button(
    request: Request,
    button_id: int,
    title: str = Form(...),
    button_type: str = Form(..., alias="type"),
    payload: str = Form(...),
    row: str | None = Form(None),
    pos: str | None = Form(None),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    button = db.get(BotButton, button_id)
    if not button:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    row_value = _normalize_int(row)
    pos_value = _normalize_int(pos)

    error = _validate_button_payload(button_type, payload)
    if error:
        node = _get_node(db, button.node_id)
        return TEMPLATES.TemplateResponse(
            "adminbot_button_edit.html",
            {
                "request": request,
                "user": user,
                "node": node,
                "button": button,
                "button_types": BUTTON_TYPES,
                "error": error,
            },
            status_code=400,
        )

    button.title = title
    button.type = button_type
    button.payload = payload
    button.row = row_value
    button.pos = pos_value
    button.is_enabled = is_enabled

    db.add(button)
    db.commit()

    return RedirectResponse(
        url=f"/adminbot/nodes/{button.node_id}/buttons", status_code=303
    )


@router.get("/buttons/{button_id}/move")
async def move_button(
    request: Request,
    button_id: int,
    direction: str,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    button = db.get(BotButton, button_id)
    if not button:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    buttons = (
        db.query(BotButton)
        .filter(BotButton.node_id == button.node_id)
        .order_by(BotButton.row, BotButton.pos, BotButton.id)
        .all()
    )

    idx = next((i for i, item in enumerate(buttons) if item.id == button.id), None)
    if idx is None:
        return RedirectResponse(
            url=f"/adminbot/nodes/{button.node_id}/buttons", status_code=303
        )

    if direction == "up" and idx > 0:
        swap_with = buttons[idx - 1]
    elif direction == "down" and idx < len(buttons) - 1:
        swap_with = buttons[idx + 1]
    else:
        swap_with = None

    if swap_with:
        button.row, swap_with.row = swap_with.row, button.row
        button.pos, swap_with.pos = swap_with.pos, button.pos
        db.add(button)
        db.add(swap_with)
        db.commit()

    return RedirectResponse(
        url=f"/adminbot/nodes/{button.node_id}/buttons", status_code=303
    )
