"""CRUD для кнопок узлов бота."""

from urllib.parse import urlparse
from uuid import uuid4
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotButton, BotNode, BotRuntime
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot, AdminRole.moderator)

MAIN_MENU_CODE = "MAIN_MENU"

BUTTON_TYPES = [
    ("callback", "Действие в боте (callback)"),
    ("url", "Ссылка (открыть браузер)"),
    ("webapp", "WebApp (открыть сайт внутри Telegram)"),
]

CALLBACK_ACTIONS = [
    ("OPEN_NODE", "Перейти в узел"),
    ("GO_MAIN", "Вернуться в главное меню"),
    ("GO_BACK", "Назад (если поддерживается)"),
    ("COMMAND", "Команда (текст)"),
    ("RAW", "Свой payload (для продвинутых)"),
]

RENDER_TYPES = [
    ("INLINE", "Кнопка под сообщением (Inline)"),
    ("REPLY", "Кнопка под строкой ввода (Reply)")
]


class ButtonPayload(BaseModel):
    id: int | None = None
    node_id: int
    title: str
    render: str = "INLINE"
    action_type: str = "NODE"
    action_payload: str | None = None
    target_node_code: str | None = None
    url: str | None = None
    webapp_url: str | None = None
    row: int = 0
    pos: int = 0
    is_enabled: bool = True


class DeletePayload(BaseModel):
    button_id: int


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _bump_runtime(db: Session) -> None:
    runtime = db.query(BotRuntime).first()
    if not runtime:
        runtime = BotRuntime(config_version=1, start_node_code="MAIN_MENU")
    runtime.config_version = (runtime.config_version or 1) + 1
    db.add(runtime)
    db.commit()


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


def _build_callback_payload(action: str, target_node_code: str | None = None) -> str:
    normalized = (action or "").upper()
    if normalized == "OPEN_NODE" and target_node_code:
        return f"OPEN_NODE:{target_node_code}"
    if normalized == "GO_MAIN":
        return f"OPEN_NODE:{MAIN_MENU_CODE}"
    if normalized == "GO_BACK":
        return "GO_BACK"
    return target_node_code or ""


def _prepare_button_payload(
    *,
    button_type: str,
    callback_action: str | None,
    target_node_code: str | None,
    url: str | None,
    webapp_url: str | None,
    raw_payload: str | None,
    legacy_payload: str | None = None,
) -> tuple[str | None, dict | None]:
    normalized_type = (button_type or "callback").lower()

    if normalized_type not in {"callback", "url", "webapp"}:
        return "Неизвестный тип кнопки", None

    if normalized_type == "url":
        url_value = (url or "").strip()
        if not _is_valid_url(url_value):
            return "Укажите корректную ссылку (http/https)", None
        return None, {
            "action_type": "URL",
            "action_payload": url_value,
            "target_node_code": None,
            "url": url_value,
            "webapp_url": None,
            "legacy_type": "url",
            "legacy_payload": url_value,
        }

    if normalized_type == "webapp":
        webapp_value = (webapp_url or "").strip()
        if not _is_valid_url(webapp_value):
            return "Укажите корректную ссылку WebApp (http/https)", None
        return None, {
            "action_type": "WEBAPP",
            "action_payload": webapp_value,
            "target_node_code": None,
            "url": None,
            "webapp_url": webapp_value,
            "legacy_type": "webapp",
            "legacy_payload": webapp_value,
        }

    normalized_action = (callback_action or "OPEN_NODE").upper()
    if normalized_action == "OPEN_NODE":
        node_code = (target_node_code or "").strip()
        if not node_code:
            return "Выберите узел для перехода", None
        payload = _build_callback_payload("OPEN_NODE", node_code)
        return None, {
            "action_type": "NODE",
            "action_payload": node_code,
            "target_node_code": node_code,
            "url": None,
            "webapp_url": None,
            "legacy_type": "callback",
            "legacy_payload": payload,
        }

    if normalized_action == "GO_MAIN":
        payload = _build_callback_payload("GO_MAIN")
        return None, {
            "action_type": "NODE",
            "action_payload": MAIN_MENU_CODE,
            "target_node_code": MAIN_MENU_CODE,
            "url": None,
            "webapp_url": None,
            "legacy_type": "callback",
            "legacy_payload": payload,
        }

    if normalized_action == "GO_BACK":
        payload = _build_callback_payload("GO_BACK")
        return None, {
            "action_type": "BACK",
            "action_payload": payload,
            "target_node_code": None,
            "url": None,
            "webapp_url": None,
            "legacy_type": "callback",
            "legacy_payload": payload or (legacy_payload or "GO_BACK"),
        }

    if normalized_action == "COMMAND":
        command_value = (raw_payload or legacy_payload or "").strip()
        if not command_value:
            return "Укажите текст команды", None
        return None, {
            "action_type": "COMMAND",
            "action_payload": command_value,
            "target_node_code": None,
            "url": None,
            "webapp_url": None,
            "legacy_type": "callback",
            "legacy_payload": command_value,
        }

    if normalized_action == "RAW":
        raw_value = (raw_payload or legacy_payload or "").strip()
        if not raw_value:
            return "Укажите payload для callback", None
        return None, {
            "action_type": "RAW",
            "action_payload": raw_value,
            "target_node_code": None,
            "url": None,
            "webapp_url": None,
            "legacy_type": "callback",
            "legacy_payload": raw_value,
        }

    return "Выберите действие для callback", None


def _detect_callback_action(button: BotButton) -> dict:
    payload = (button.payload or "").strip()
    target_code = button.target_node_code or _extract_target_code(button)
    action_type = (button.action_type or "").upper()

    if action_type == "NODE" and target_code:
        action = "GO_MAIN" if target_code == MAIN_MENU_CODE else "OPEN_NODE"
        return {"action": action, "target_code": target_code, "raw_payload": None}

    if action_type == "BACK" or payload == "GO_BACK":
        return {"action": "GO_BACK", "target_code": None, "raw_payload": payload or "GO_BACK"}

    return {"action": "RAW", "target_code": None, "raw_payload": payload or None}


def _button_form_state(button: BotButton | None) -> dict:
    if not button:
        return {
            "button_type": "callback",
            "callback_action": "OPEN_NODE",
            "target_node_code": None,
            "url": "",
            "webapp_url": "",
            "raw_payload": None,
            "render": "INLINE",
        }

    btn_type = (button.type or "callback").lower()

    if btn_type == "url" or (button.action_type or "").upper() == "URL":
        return {
            "button_type": "url",
            "callback_action": "RAW",
            "target_node_code": None,
            "url": button.url or button.payload,
            "webapp_url": "",
            "raw_payload": button.action_payload,
            "render": button.render or "INLINE",
        }

    if btn_type == "webapp" or (button.action_type or "").upper() == "WEBAPP":
        return {
            "button_type": "webapp",
            "callback_action": "RAW",
            "target_node_code": None,
            "url": "",
            "webapp_url": button.webapp_url or button.payload,
            "raw_payload": button.action_payload,
            "render": button.render or "INLINE",
        }

    detected = _detect_callback_action(button)
    return {
        "button_type": "callback",
        "callback_action": detected.get("action") or "RAW",
        "target_node_code": detected.get("target_code"),
        "url": "",
        "webapp_url": "",
        "raw_payload": button.action_payload or detected.get("raw_payload") or button.payload,
        "render": button.render or "INLINE",
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


def _button_view(button: BotButton, nodes_map: dict[str, BotNode]) -> dict:
    form_state = _button_form_state(button)
    btn_type = form_state.get("button_type") or "callback"

    if btn_type == "url":
        action_label = "Ссылка"
        action_value = form_state.get("url") or "—"
    elif btn_type == "webapp":
        action_label = "WebApp"
        action_value = form_state.get("webapp_url") or "—"
    else:
        action_label = "Действие (callback)"
        callback_action = (form_state.get("callback_action") or "RAW").upper()
        if callback_action == "OPEN_NODE":
            target_code = form_state.get("target_node_code")
            target_title = nodes_map.get(target_code).title if target_code and target_code in nodes_map else None
            human_label = target_title or target_code or "Не выбран"
            action_value = f"Переход в: {human_label}" if human_label else "Не выбран"
        elif callback_action == "GO_MAIN":
            action_value = "Переход в: Главное меню"
        elif callback_action == "GO_BACK":
            action_value = "Назад (payload: GO_BACK)"
        elif callback_action == "COMMAND":
            action_value = f"Команда: {form_state.get('raw_payload') or '—'}"
        else:
            action_value = form_state.get("raw_payload") or button.payload or "—"

    return {
        "id": button.id,
        "title": button.title,
        "row": button.row,
        "pos": button.pos,
        "render": (form_state.get("render") or button.render or "INLINE").upper(),
        "is_enabled": button.is_enabled,
        "action_type": action_label,
        "action_value": action_value,
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


def _normalize_node_code(desired_code: str | None, db: Session) -> str:
    clean = (desired_code or "").strip().upper()
    if not clean:
        return _generate_node_code("NODE", db)

    clean = re.sub(r"\W+", "_", clean).strip("_")[:64] or "NODE"
    if not db.query(BotNode).filter(BotNode.code == clean).first():
        return clean

    return _generate_node_code(clean, db)


def _next_button_position(db: Session, node_id: int) -> tuple[int, int]:
    buttons = (
        db.query(BotButton)
        .filter(BotButton.node_id == node_id)
        .order_by(BotButton.row, BotButton.pos, BotButton.id)
        .all()
    )
    if not buttons:
        return 0, 0

    last = buttons[-1]
    return last.row, last.pos + 1


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

    nodes_map = {item.code: item for item in db.query(BotNode).all()}
    buttons = (
        db.query(BotButton)
        .filter(BotButton.node_id == node.id)
        .order_by(BotButton.row, BotButton.pos, BotButton.id)
        .all()
    )

    button_views = [_button_view(btn, nodes_map) for btn in buttons]

    return TEMPLATES.TemplateResponse(
        "adminbot_buttons_list.html",
        {
            "request": request,
            "user": user,
            "node": node,
            "buttons": button_views,
            "nodes_map": nodes_map,
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
            "callback_actions": CALLBACK_ACTIONS,
            "render_types": RENDER_TYPES,
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
    button_type: str = Form("callback", alias="type"),
    callback_action: str = Form("OPEN_NODE"),
    target_node_code: str | None = Form(None),
    url: str | None = Form(None),
    webapp_url: str | None = Form(None),
    raw_payload: str | None = Form(None),
    render: str = Form("INLINE"),
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
        "button_type": button_type,
        "callback_action": callback_action,
        "target_node_code": (target_node_code or "").strip() or None,
        "url": (url or "").strip(),
        "webapp_url": (webapp_url or "").strip(),
        "raw_payload": (raw_payload or "").strip() or None,
        "render": (render or "INLINE").upper(),
    }

    error, payload_info = _prepare_button_payload(
        button_type=button_type,
        callback_action=callback_action,
        target_node_code=target_node_code,
        url=url,
        webapp_url=webapp_url,
        raw_payload=raw_payload,
    )
    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_button_edit.html",
            {
                "request": request,
                "user": user,
                "node": node,
                "button": None,
                "button_types": BUTTON_TYPES,
                "callback_actions": CALLBACK_ACTIONS,
                "render_types": RENDER_TYPES,
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
            render=(render or "INLINE").upper(),
            action_type=payload_info["action_type"],
            action_payload=payload_info.get("action_payload"),
            target_node_code=payload_info.get("target_node_code"),
            url=payload_info.get("url"),
            webapp_url=payload_info.get("webapp_url"),
            row=row_value,
            pos=pos_value,
            is_enabled=is_enabled,
        )
    )
    db.commit()
    _bump_runtime(db)

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
            "callback_actions": CALLBACK_ACTIONS,
            "render_types": RENDER_TYPES,
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
    button_type: str = Form("callback", alias="type"),
    callback_action: str = Form("OPEN_NODE"),
    target_node_code: str | None = Form(None),
    url: str | None = Form(None),
    webapp_url: str | None = Form(None),
    raw_payload: str | None = Form(None),
    render: str = Form("INLINE"),
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

    form_state = {
        "button_type": button_type,
        "callback_action": callback_action,
        "target_node_code": (target_node_code or "").strip() or None,
        "url": (url or "").strip(),
        "webapp_url": (webapp_url or "").strip(),
        "raw_payload": (raw_payload or "").strip()
        or (button.payload if button.type == "callback" else None),
        "render": (render or "INLINE").upper(),
    }

    error, payload_info = _prepare_button_payload(
        button_type=button_type,
        callback_action=callback_action,
        target_node_code=target_node_code,
        url=url,
        webapp_url=webapp_url,
        raw_payload=raw_payload,
        legacy_payload=button.payload,
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
                "button_types": BUTTON_TYPES,
                "callback_actions": CALLBACK_ACTIONS,
                "render_types": RENDER_TYPES,
                "nodes_groups": _collect_node_options(db),
                "error": error,
                "form_state": form_state,
            },
            status_code=400,
        )

    button.title = title
    button.type = payload_info["legacy_type"]
    button.payload = payload_info["legacy_payload"]
    button.render = (render or "INLINE").upper()
    button.action_type = payload_info["action_type"]
    button.action_payload = payload_info.get("action_payload")
    button.target_node_code = payload_info.get("target_node_code")
    button.url = payload_info.get("url")
    button.webapp_url = payload_info.get("webapp_url")
    button.row = row_value
    button.pos = pos_value
    button.is_enabled = is_enabled

    db.add(button)
    db.commit()
    _bump_runtime(db)

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
    _bump_runtime(db)

    return {"ok": True, "node": {"id": node.id, "code": node.code, "title": node.title}}


@router.get("/api/buttons")
async def api_list_buttons(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    node = _get_node(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    buttons = (
        db.query(BotButton)
        .filter(BotButton.node_id == node_id)
        .order_by(BotButton.row, BotButton.pos, BotButton.id)
        .all()
    )

    return {
        "ok": True,
        "node": {"id": node.id, "code": node.code, "title": node.title},
        "buttons": [
            {
                "id": btn.id,
                "title": btn.title,
                "render": (btn.render or "INLINE").upper(),
                "action_type": (btn.action_type or "NODE").upper(),
                "action_payload": btn.action_payload,
                "target_node_code": btn.target_node_code,
                "url": btn.url,
                "webapp_url": btn.webapp_url,
                "row": btn.row,
                "pos": btn.pos,
                "is_enabled": btn.is_enabled,
            }
            for btn in buttons
        ],
    }


@router.post("/api/buttons/save")
async def api_save_button(
    request: Request,
    payload: ButtonPayload,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    node = _get_node(db, payload.node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    render_type = (payload.render or "INLINE").upper()
    if render_type not in {"INLINE", "REPLY"}:
        raise HTTPException(status_code=422, detail="Invalid render type")

    action_type = (payload.action_type or "NODE").upper()
    button = db.get(BotButton, payload.id) if payload.id else BotButton(node_id=node.id)
    if payload.id and (not button or button.node_id != node.id):
        raise HTTPException(status_code=422, detail="Button not found for node")

    button.node_id = node.id
    button.title = payload.title
    button.render = render_type
    button.action_type = action_type
    button.action_payload = payload.action_payload
    button.target_node_code = payload.target_node_code
    button.url = payload.url
    button.webapp_url = payload.webapp_url
    button.row = payload.row
    button.pos = payload.pos
    button.is_enabled = payload.is_enabled
    button.type = "callback" if action_type not in {"URL", "WEBAPP"} else action_type.lower()
    button.payload = (
        payload.action_payload
        or payload.target_node_code
        or payload.url
        or payload.webapp_url
        or ""
    )

    db.add(button)
    db.commit()
    db.refresh(button)
    _bump_runtime(db)

    return {"ok": True, "button_id": button.id}


@router.post("/api/buttons/delete")
async def api_delete_button(
    request: Request,
    payload: DeletePayload,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    button = db.get(BotButton, payload.button_id)
    if not button:
        raise HTTPException(status_code=404, detail="Button not found")

    db.delete(button)
    db.commit()
    _bump_runtime(db)

    return {"ok": True}


@router.post("/nodes/{node_id}/submenu")
async def create_submenu(
    request: Request,
    node_id: int,
    submenu_title: str = Form(...),
    submenu_code: str | None = Form(None),
    add_back_button: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    parent_node = _get_node(db, node_id)
    if not parent_node:
        return JSONResponse({"ok": False, "error": "Исходный узел не найден"}, status_code=404)

    clean_title = (submenu_title or "").strip()
    if not clean_title:
        return JSONResponse({"ok": False, "error": "Укажите название подменю"}, status_code=400)

    code = _normalize_node_code(submenu_code, db) if submenu_code else _generate_node_code(clean_title, db)

    new_node = BotNode(
        code=code,
        title=clean_title,
        message_text="Выберите пункт:",
        parse_mode="HTML",
        node_type="MESSAGE",
        is_enabled=True,
    )
    db.add(new_node)
    db.commit()
    db.refresh(new_node)

    row_value, pos_value = _next_button_position(db, parent_node.id)
    error, payload_info = _prepare_button_payload(
        button_type="callback",
        callback_action="OPEN_NODE",
        target_node_code=new_node.code,
        url=None,
        webapp_url=None,
        raw_payload=None,
    )
    if error or not payload_info:
        return JSONResponse({"ok": False, "error": "Не удалось создать кнопку перехода"}, status_code=400)

    new_button = BotButton(
        node_id=parent_node.id,
        title=clean_title,
        type=payload_info["legacy_type"],
        payload=payload_info["legacy_payload"],
        action_type=payload_info["action_type"],
        target_node_code=payload_info.get("target_node_code"),
        row=row_value,
        pos=pos_value,
        is_enabled=True,
    )
    db.add(new_button)

    if add_back_button:
        back_error, back_payload = _prepare_button_payload(
            button_type="callback",
            callback_action="OPEN_NODE",
            target_node_code=parent_node.code,
            url=None,
            webapp_url=None,
            raw_payload=None,
        )
        if not back_error and back_payload:
            back_btn = BotButton(
                node_id=new_node.id,
                title="Назад",
                type=back_payload["legacy_type"],
                payload=back_payload["legacy_payload"],
                action_type=back_payload["action_type"],
                target_node_code=back_payload.get("target_node_code"),
                row=0,
                pos=0,
                is_enabled=True,
            )
            db.add(back_btn)

    db.commit()
    _bump_runtime(db)

    return {
        "ok": True,
        "node": {"id": new_node.id, "code": new_node.code, "title": new_node.title},
        "redirect": f"/adminbot/nodes/{new_node.id}/buttons",
    }


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
        _bump_runtime(db)

    return RedirectResponse(
        url=f"/adminbot/nodes/{button.node_id}/buttons", status_code=303
    )
