"""CRUD для бот-узлов (экраны/сообщения)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import re

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotNode
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])


ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)

NODE_TYPES = {"MESSAGE", "INPUT", "CONDITION"}
INPUT_TYPES = {"TEXT", "NUMBER", "PHONE_TEXT", "CONTACT"}
CONDITION_OPERATORS = {
    "EXISTS",
    "NOT_EXISTS",
    "EQ",
    "NEQ",
    "CONTAINS",
    "STARTS_WITH",
    "ENDS_WITH",
    "GT",
    "GTE",
    "LT",
    "LTE",
}
INPUT_KEY_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{1,32}$")


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _prepare_node_payload(
    *,
    title: str,
    message_text: str,
    parse_mode: str,
    image_url: str | None,
    is_enabled: bool,
    node_type: str,
    input_type: str | None,
    input_var_key: str | None,
    input_required: bool,
    input_min_len: int | None,
    input_error_text: str | None,
    next_node_code_success: str | None,
    next_node_code_cancel: str | None,
    cond_var_key: str | None,
    cond_operator: str | None,
    cond_value: str | None,
    next_node_code_true: str | None,
    next_node_code_false: str | None,
) -> tuple[str | None, dict]:
    normalized_node_type = (node_type or "MESSAGE").strip().upper()
    normalized_input_type = (input_type or "").strip().upper() or None
    normalized_var_key = (input_var_key or "").strip() or None
    normalized_next_success = (next_node_code_success or "").strip() or None
    normalized_next_cancel = (next_node_code_cancel or "").strip() or None
    normalized_cond_var_key = (cond_var_key or "").strip() or None
    normalized_cond_operator = (cond_operator or "").strip().upper() or None
    normalized_cond_value = (cond_value or "").strip()
    normalized_cond_value = normalized_cond_value if normalized_cond_value else None
    normalized_next_true = (next_node_code_true or "").strip() or None
    normalized_next_false = (next_node_code_false or "").strip() or None

    if normalized_node_type not in NODE_TYPES:
        return "Некорректный тип узла", {}

    if normalized_node_type == "INPUT":
        if normalized_input_type not in INPUT_TYPES:
            return "Укажите тип ввода", {}
        if not normalized_var_key or not INPUT_KEY_REGEX.match(normalized_var_key):
            return (
                "Некорректный ключ переменной. Разрешены латинские буквы, цифры и _ (пример: phone).",
                {},
            )
        if not normalized_next_success:
            return "Укажите код узла для перехода при успешном вводе", {}

    if normalized_node_type == "CONDITION":
        if not all(
            [
                normalized_cond_var_key,
                normalized_cond_operator,
                normalized_next_true,
                normalized_next_false,
            ]
        ):
            return "Заполните обязательные поля для узла «Условие».", {}

        if not INPUT_KEY_REGEX.match(normalized_cond_var_key):
            return (
                "Некорректный ключ переменной. Разрешены латинские буквы, цифры и _ (пример: phone).",
                {},
            )
        if normalized_cond_operator not in CONDITION_OPERATORS:
            return "Заполните обязательные поля для узла «Условие».", {}
        if normalized_cond_operator not in {"EXISTS", "NOT_EXISTS"} and not normalized_cond_value:
            return "Для выбранного оператора нужно значение для сравнения.", {}

    payload = {
        "title": title,
        "message_text": message_text,
        "parse_mode": parse_mode or "HTML",
        "image_url": image_url or None,
        "is_enabled": is_enabled,
        "node_type": normalized_node_type,
        "input_type": normalized_input_type,
        "input_var_key": normalized_var_key,
        "input_required": bool(input_required),
        "input_min_len": input_min_len,
        "input_error_text": input_error_text or None,
        "next_node_code_success": normalized_next_success,
        "next_node_code_cancel": normalized_next_cancel,
        "cond_var_key": normalized_cond_var_key,
        "cond_operator": normalized_cond_operator,
        "cond_value": normalized_cond_value,
        "next_node_code_true": normalized_next_true,
        "next_node_code_false": normalized_next_false,
    }

    if normalized_node_type != "INPUT":
        payload.update(
            {
                "input_type": None,
                "input_var_key": None,
                "input_required": True,
                "input_min_len": None,
                "input_error_text": None,
                "next_node_code_success": None,
                "next_node_code_cancel": None,
            }
        )

    if normalized_node_type != "CONDITION":
        payload.update(
            {
                "cond_var_key": None,
                "cond_operator": None,
                "cond_value": None,
                "next_node_code_true": None,
                "next_node_code_false": None,
            }
        )

    return None, payload


@router.get("/nodes")
async def list_nodes(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    nodes = (
        db.query(BotNode)
        .order_by(BotNode.updated_at.desc().nullslast(), BotNode.id.desc())
        .all()
    )

    return TEMPLATES.TemplateResponse(
        "adminbot_nodes_list.html",
        {
            "request": request,
            "user": user,
            "nodes": nodes,
        },
    )


@router.get("/nodes/new")
async def new_node_form(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    return TEMPLATES.TemplateResponse(
        "adminbot_node_edit.html",
        {
            "request": request,
            "user": user,
            "node": None,
            "error": None,
        },
    )


@router.post("/nodes/new")
async def create_node(
    request: Request,
    code: str = Form(...),
    title: str = Form(...),
    message_text: str = Form(...),
    parse_mode: str = Form("HTML"),
    image_url: str | None = Form(None),
    is_enabled: bool = Form(False),
    node_type: str = Form("MESSAGE"),
    input_type: str | None = Form(None),
    input_var_key: str | None = Form(None),
    input_required: bool = Form(True),
    input_min_len: int | None = Form(None),
    input_error_text: str | None = Form(None),
    next_node_code_success: str | None = Form(None),
    next_node_code_cancel: str | None = Form(None),
    cond_var_key: str | None = Form(None),
    cond_operator: str | None = Form(None),
    cond_value: str | None = Form(None),
    next_node_code_true: str | None = Form(None),
    next_node_code_false: str | None = Form(None),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    code = (code or "").strip()
    existing = db.query(BotNode).filter(BotNode.code == code).first()
    if existing:
        return TEMPLATES.TemplateResponse(
            "adminbot_node_edit.html",
            {
                "request": request,
                "user": user,
                "node": None,
                "error": "Код узла уже используется",
            },
            status_code=400,
        )

    error, payload = _prepare_node_payload(
        title=title,
        message_text=message_text,
        parse_mode=parse_mode,
        image_url=image_url,
        is_enabled=is_enabled,
        node_type=node_type,
        input_type=input_type,
        input_var_key=input_var_key,
        input_required=input_required,
        input_min_len=input_min_len,
        input_error_text=input_error_text,
        next_node_code_success=next_node_code_success,
        next_node_code_cancel=next_node_code_cancel,
        cond_var_key=cond_var_key,
        cond_operator=cond_operator,
        cond_value=cond_value,
        next_node_code_true=next_node_code_true,
        next_node_code_false=next_node_code_false,
    )

    if error:
        draft_node = BotNode(code=code, **payload)
        return TEMPLATES.TemplateResponse(
            "adminbot_node_edit.html",
            {
                "request": request,
                "user": user,
                "node": draft_node,
                "error": error,
            },
            status_code=400,
        )

    db.add(BotNode(code=code, **payload))
    db.commit()

    return RedirectResponse(url="/adminbot/nodes", status_code=303)


@router.get("/nodes/{node_id}/edit")
async def edit_node_form(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = db.get(BotNode, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    return TEMPLATES.TemplateResponse(
        "adminbot_node_edit.html",
        {
            "request": request,
            "user": user,
            "node": node,
            "error": None,
        },
    )


@router.post("/nodes/{node_id}/edit")
async def edit_node(
    request: Request,
    node_id: int,
    title: str = Form(...),
    message_text: str = Form(...),
    parse_mode: str = Form("HTML"),
    image_url: str | None = Form(None),
    is_enabled: bool = Form(False),
    node_type: str = Form("MESSAGE"),
    input_type: str | None = Form(None),
    input_var_key: str | None = Form(None),
    input_required: bool = Form(True),
    input_min_len: int | None = Form(None),
    input_error_text: str | None = Form(None),
    next_node_code_success: str | None = Form(None),
    next_node_code_cancel: str | None = Form(None),
    cond_var_key: str | None = Form(None),
    cond_operator: str | None = Form(None),
    cond_value: str | None = Form(None),
    next_node_code_true: str | None = Form(None),
    next_node_code_false: str | None = Form(None),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = db.get(BotNode, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    error, payload = _prepare_node_payload(
        title=title,
        message_text=message_text,
        parse_mode=parse_mode,
        image_url=image_url,
        is_enabled=is_enabled,
        node_type=node_type,
        input_type=input_type,
        input_var_key=input_var_key,
        input_required=input_required,
        input_min_len=input_min_len,
        input_error_text=input_error_text,
        next_node_code_success=next_node_code_success,
        next_node_code_cancel=next_node_code_cancel,
        cond_var_key=cond_var_key,
        cond_operator=cond_operator,
        cond_value=cond_value,
        next_node_code_true=next_node_code_true,
        next_node_code_false=next_node_code_false,
    )

    if error:
        draft_node = BotNode(code=node.code, **payload)
        draft_node.id = node.id
        return TEMPLATES.TemplateResponse(
            "adminbot_node_edit.html",
            {
                "request": request,
                "user": user,
                "node": draft_node,
                "error": error,
            },
            status_code=400,
        )

    for field, value in payload.items():
        setattr(node, field, value)

    db.add(node)
    db.commit()

    return RedirectResponse(url="/adminbot/nodes", status_code=303)
