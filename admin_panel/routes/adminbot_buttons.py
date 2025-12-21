"""CRUD для кнопок узлов бота."""

from urllib.parse import urlparse
from uuid import uuid4
import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotButton, BotNode
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)

ACTION_TYPES = [
    ("NODE", "Переход в раздел (узел)"),
    ("URL", "Открыть ссылку (URL)"),
    ("WEBAPP", "Открыть WebApp (сайт внутри Telegram)"),
]


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


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


def _get_node(db: Session, node_id: int) -> BotNode | None:
    return db.get(BotNode, node_id)


def _extract_target_code(button: BotButton) -> str | None:
    if button.target_node_code:
        return button.target_node_code
    payload = (button.payload or "").strip()
    if payload.startswith("OPEN_NODE:"):
        return payload.split(":", maxsplit=1)[1]
    return None


def _is_valid_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _prepare_action_fields(
    action_type: str,
    target_node_code: str | None,
    url: str | None,
    webapp_url: str | None,
    *,
    legacy_payload: str | None = None,
) -> tuple[str | None, dict | None]:
    normalized = (action_type or "NODE").upper()
    if normalized not in {"NODE", "URL", "WEBAPP", "LEGACY"}:
        return "Неизвестное действие кнопки", None

    if normalized == "NODE":
        node_code = (target_node_code or "").strip()
        if node_code:
            payload = f"OPEN_NODE:{node_code}"
            return None, {
                "action_type": "NODE",
                "target_node_code": node_code,
                "url": None,
                "webapp_url": None,
                "legacy_type": "callback",
                "legacy_payload": payload,
            }
        if legacy_payload:
            return None, {
                "action_type": "LEGACY",
                "target_node_code": None,
                "url": None,
                "webapp_url": None,
                "legacy_type": "callback",
                "legacy_payload": legacy_payload,
            }
        return "Выберите раздел/узел для перехода", None

    if normalized == "URL":
        url_value = (url or "").strip()
        if not _is_valid_url(url_value):
            return "Укажите корректную ссылку (http/https)", None
        return None, {
            "action_type": "URL",
            "target_node_code": None,
            "url": url_value,
            "webapp_url": None,
            "legacy_type": "url",
            "legacy_payload": url_value,
        }

    if normalized == "WEBAPP":
        webapp_value = (webapp_url or "").strip()
        if not _is_valid_url(webapp_value):
            return "Укажите корректную ссылку WebApp (http/https)", None
        return None, {
            "action_type": "WEBAPP",
            "target_node_code": None,
            "url": None,
            "webapp_url": webapp_value,
            "legacy_type": "webapp",
            "legacy_payload": webapp_value,
        }

    legacy_value = (legacy_payload or "").strip()
    if not legacy_value:
        return "Для старого формата нужен payload", None
    return None, {
        "action_type": "LEGACY",
        "target_node_code": None,
        "url": None,
        "webapp_url": None,
        "legacy_type": "callback",
        "legacy_payload": legacy_value,
    }


def _button_form_state(button: BotButton | None) -> dict:
    if not button:
        return {
            "action_type": "NODE",
            "target_node_code": None,
            "url": "",
            "webapp_url": "",
            "legacy_payload": None,
        }

    action_type = (button.action_type or "").upper() or None
    target_code = _extract_target_code(button)
    legacy_payload = None

    if action_type not in {"NODE", "URL", "WEBAPP"}:
        legacy_payload = button.payload
        action_type = "LEGACY"
    elif action_type == "NODE" and not target_code and button.payload:
        legacy_payload = button.payload
        action_type = "LEGACY"

    if not action_type:
        action_type = "NODE"

    return {
        "action_type": action_type,
        "target_node_code": target_code,
        "url": button.url or (button.payload if button.type == "url" else ""),
        "webapp_url": button.webapp_url
        or (button.payload if button.type == "webapp" else ""),
        "legacy_payload": legacy_payload,
    }


def _button_usage_map(db: Session) -> dict[str, int]:
    usage: dict[str, int] = {}
    for btn in db.query(BotButton).all():
        target_code = _extract_target_code(btn)
        if target_code:
            usage[target_code] = usage.get(target_code, 0) + 1
    return usage


def _collect_node_options(db: Session) -> list[dict]:
    nodes = db.query(BotNode).order_by(BotNode.title, BotNode.code).all()
    usage = _button_usage_map(db)

    def _group_name(node: BotNode) -> str:
        if node.code == "MAIN_MENU":
            return "MAIN"
        if "КАТЕГ" in (node.title or "").upper() or "CAT" in (node.code or "").upper():
            return "Категории"
        return "Служебные"

    sorted_nodes = sorted(
        nodes,
        key=lambda n: (
            0 if n.code == "MAIN_MENU" else 1,
            -usage.get(n.code, 0),
            (n.title or "").lower(),
            n.code,
        ),
    )

    grouped: dict[str, list[dict]] = {}
    for node in sorted_nodes:
        grouped.setdefault(_group_name(node), []).append(
            {
                "code": node.code,
                "title": node.title,
                "label": f"{node.title} ({node.code})",
                "usage": usage.get(node.code, 0),
            }
        )

    return [
        {"name": name, "options": options}
        for name, options in grouped.items()
    ]


def _button_view(button: BotButton) -> dict:
    form_state = _button_form_state(button)
    action_type = form_state.get("action_type") or "NODE"
    display_value = ""
    if action_type == "NODE":
        display_value = form_state.get("target_node_code") or "Не выбран"
    elif action_type == "URL":
        display_value = form_state.get("url")
    elif action_type == "WEBAPP":
        display_value = form_state.get("webapp_url")
    else:
        display_value = form_state.get("legacy_payload") or button.payload

    return {
        "id": button.id,
        "title": button.title,
        "row": button.row,
        "pos": button.pos,
        "is_enabled": button.is_enabled,
        "action_type": action_type,
        "action_value": display_value,
    }


def _generate_node_code(title: str, db: Session) -> str:
    base = re.sub(r"\W+", "_", (title or "NODE").upper()).strip("_") or "NODE"
    base = base[:40]
    if not base:
        base = "NODE"
    candidate = base
    counter = 1
    while db.query(BotNode).filter(BotNode.code == candidate).first():
        counter += 1
        candidate = f"{base}_{counter}"[:64]
    return candidate or f"NODE_{uuid4().hex[:6].upper()}"


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

    button_views = [_button_view(btn) for btn in buttons]

    return TEMPLATES.TemplateResponse(
        "adminbot_buttons_list.html",
        {
            "request": request,
            "user": user,
            "node": node,
            "buttons": button_views,
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
            "action_types": ACTION_TYPES,
            "nodes_groups": _collect_node_options(db),
            "error": None,
            "form_state": _button_form_state(None),
        },
    )


@router.post("/nodes/{node_id}/buttons/new")
async def create_button(
    request: Request,
    node_id: int,
    title: str = Form(...),
    action_type: str = Form("NODE"),
    target_node_code: str | None = Form(None),
    url: str | None = Form(None),
    webapp_url: str | None = Form(None),
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

    form_state = {
        "action_type": action_type,
        "target_node_code": (target_node_code or "").strip() or None,
        "url": (url or "").strip(),
        "webapp_url": (webapp_url or "").strip(),
        "legacy_payload": None,
    }

    error, payload_info = _prepare_action_fields(
        action_type,
        target_node_code,
        url,
        webapp_url,
    )
    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_button_edit.html",
            {
                "request": request,
                "user": user,
                "node": node,
                "button": None,
                "action_types": ACTION_TYPES,
                "nodes_groups": _collect_node_options(db),
                "error": error,
                "form_state": form_state,
            },
            status_code=400,
        )

    db.add(
        BotButton(
            node_id=node.id,
            title=title,
            type=payload_info["legacy_type"],
            payload=payload_info["legacy_payload"],
            action_type=payload_info["action_type"],
            target_node_code=payload_info.get("target_node_code"),
            url=payload_info.get("url"),
            webapp_url=payload_info.get("webapp_url"),
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
            "action_types": ACTION_TYPES,
            "nodes_groups": _collect_node_options(db),
            "error": None,
            "form_state": _button_form_state(button),
        },
    )


@router.post("/buttons/{button_id}/edit")
async def update_button(
    request: Request,
    button_id: int,
    title: str = Form(...),
    action_type: str = Form("NODE"),
    target_node_code: str | None = Form(None),
    url: str | None = Form(None),
    webapp_url: str | None = Form(None),
    row: str | None = Form(None),
    pos: str | None = Form(None),
    is_enabled: bool = Form(False),
    legacy_payload: str | None = Form(None),
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

    form_state = {
        "action_type": action_type,
        "target_node_code": (target_node_code or "").strip() or None,
        "url": (url or "").strip(),
        "webapp_url": (webapp_url or "").strip(),
        "legacy_payload": legacy_payload or button.payload,
    }

    error, payload_info = _prepare_action_fields(
        action_type,
        target_node_code,
        url,
        webapp_url,
        legacy_payload=legacy_payload or button.payload,
    )
    if error:
        node = _get_node(db, button.node_id)
        return TEMPLATES.TemplateResponse(
            "adminbot_button_edit.html",
            {
                "request": request,
                "user": user,
                "node": node,
                "button": button,
                "action_types": ACTION_TYPES,
                "nodes_groups": _collect_node_options(db),
                "error": error,
                "form_state": form_state,
            },
            status_code=400,
        )

    button.title = title
    button.type = payload_info["legacy_type"]
    button.payload = payload_info["legacy_payload"]
    button.action_type = payload_info["action_type"]
    button.target_node_code = payload_info.get("target_node_code")
    button.url = payload_info.get("url")
    button.webapp_url = payload_info.get("webapp_url")
    button.row = row_value
    button.pos = pos_value
    button.is_enabled = is_enabled

    db.add(button)
    db.commit()

    return RedirectResponse(
        url=f"/adminbot/nodes/{button.node_id}/buttons", status_code=303
    )


@router.post("/nodes/quick-create")
async def quick_create_node(
    request: Request,
    title: str = Form(...),
    node_type: str = Form("MESSAGE"),
    message_text: str = Form("Выберите пункт:"),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    clean_title = (title or "").strip()
    if not clean_title:
        return JSONResponse({"ok": False, "error": "Укажите название раздела"}, status_code=400)

    code = _generate_node_code(clean_title, db)

    node = BotNode(
        code=code,
        title=clean_title,
        message_text=message_text or "Выберите пункт:",
        parse_mode="HTML",
        node_type=node_type or "MESSAGE",
        is_enabled=True,
    )
    db.add(node)
    db.commit()
    db.refresh(node)

    return {"ok": True, "node": {"id": node.id, "code": node.code, "title": node.title}}


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

    swap_with = None
    if direction == "up" and idx > 0:
        swap_with = buttons[idx - 1]
    elif direction == "down" and idx < len(buttons) - 1:
        swap_with = buttons[idx + 1]

    if swap_with:
        button.row, swap_with.row = swap_with.row, button.row
        button.pos, swap_with.pos = swap_with.pos, button.pos
        db.add(button)
        db.add(swap_with)
        db.commit()

    return RedirectResponse(
        url=f"/adminbot/nodes/{button.node_id}/buttons", status_code=303
    )
