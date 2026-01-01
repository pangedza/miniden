"""CRUD для бот-узлов (экраны/сообщения)."""

import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotButton, BotNode, BotNodeAction, BotRuntime, BotTrigger
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])


ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot, AdminRole.moderator)

NODE_TYPES = {"MESSAGE", "INPUT", "CONDITION", "ACTION"}
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
ACTION_TYPES = {
    "SET_VAR",
    "CLEAR_VAR",
    "INCREMENT_VAR",
    "DECREMENT_VAR",
    "ADD_TAG",
    "REMOVE_TAG",
    "SEND_MESSAGE",
    "SEND_ADMIN_MESSAGE",
    "GOTO_NODE",
    "GOTO_MAIN",
    "STOP_FLOW",
    "REQUEST_CONTACT",
    "REQUEST_LOCATION",
}
INPUT_KEY_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{1,32}$")


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _bump_runtime(db: Session) -> None:
    runtime = db.query(BotRuntime).first()
    if not runtime:
        runtime = BotRuntime(config_version=1)
    runtime.config_version = (runtime.config_version or 1) + 1
    db.add(runtime)


def _to_optional_int(value: int | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        return int(value)
    except Exception:
        return None


def _find_incoming_links(db: Session, node_code: str | None) -> dict:
    if not node_code:
        return {"nodes": [], "buttons": [], "triggers": []}

    linked_nodes = (
        db.query(BotNode)
        .filter(
            or_(
                BotNode.next_node_code == node_code,
                BotNode.next_node_code_success == node_code,
                BotNode.next_node_code_cancel == node_code,
                BotNode.next_node_code_true == node_code,
                BotNode.next_node_code_false == node_code,
            )
        )
        .all()
    )

    linked_buttons = (
        db.query(BotButton)
        .filter(
            or_(
                BotButton.target_node_code == node_code,
                BotButton.payload.ilike(f"%OPEN_NODE:{node_code}%"),
            )
        )
        .all()
    )

    linked_triggers = (
        db.query(BotTrigger)
        .filter(BotTrigger.target_node_code == node_code)
        .all()
    )

    return {
        "nodes": linked_nodes,
        "buttons": linked_buttons,
        "triggers": linked_triggers,
    }


def _cleanup_node_links(db: Session, node_code: str) -> None:
    linked_nodes = (
        db.query(BotNode)
        .filter(
            or_(
                BotNode.next_node_code == node_code,
                BotNode.next_node_code_success == node_code,
                BotNode.next_node_code_cancel == node_code,
                BotNode.next_node_code_true == node_code,
                BotNode.next_node_code_false == node_code,
            )
        )
        .all()
    )
    for ref in linked_nodes:
        if ref.next_node_code == node_code:
            ref.next_node_code = None
        if ref.next_node_code_success == node_code:
            ref.next_node_code_success = None
        if ref.next_node_code_cancel == node_code:
            ref.next_node_code_cancel = None
        if ref.next_node_code_true == node_code:
            ref.next_node_code_true = None
        if ref.next_node_code_false == node_code:
            ref.next_node_code_false = None
        db.add(ref)

    buttons = (
        db.query(BotButton)
        .filter(
            or_(
                BotButton.target_node_code == node_code,
                BotButton.payload.ilike(f"%OPEN_NODE:{node_code}%"),
            )
        )
        .all()
    )
    for btn in buttons:
        btn.target_node_code = None
        payload = (btn.payload or "").strip()
        if payload.startswith("OPEN_NODE:"):
            btn.payload = ""
        btn.is_enabled = False
        db.add(btn)

    triggers = db.query(BotTrigger).filter(BotTrigger.target_node_code == node_code).all()
    for trig in triggers:
        trig.is_enabled = False
        db.add(trig)

    db.query(BotNodeAction).filter(BotNodeAction.node_code == node_code).delete()


def _prepare_node_payload(
    *,
    node_code: str | None,
    title: str,
    message_text: str | None,
    parse_mode: str,
    image_url: str | None,
    is_enabled: bool,
    clear_chat: bool,
    node_type: str,
    input_type: str | None,
    input_var_key: str | None,
    input_required: bool,
    input_min_len: int | str | None,
    input_error_text: str | None,
    next_node_code_success: str | None,
    next_node_code_cancel: str | None,
    next_node_code: str | None,
    cond_var_key: str | None,
    cond_operator: str | None,
    cond_value: str | None,
    next_node_code_true: str | None,
    next_node_code_false: str | None,
    condition_type: str | None,
    cond_sub_channels: str | None,
    cond_sub_on_success: str | None,
    cond_sub_on_fail: str | None,
    cond_sub_fail_message: str | None,
    cond_sub_subscribe_url: str | None,
    cond_sub_check_button_text: str | None,
    cond_sub_subscribe_button_text: str | None,
) -> tuple[str | None, dict]:
    clean_title = (title or "").strip()
    clean_message = (message_text or "").strip()
    clean_parse_mode = (parse_mode or "HTML").strip() or "HTML"

    normalized_node_type = (node_type or "MESSAGE").strip().upper()
    normalized_input_type = (input_type or "").strip().upper() or None
    normalized_var_key = (input_var_key or "").strip() or None
    normalized_next_success = (next_node_code_success or "").strip() or None
    normalized_next_cancel = (next_node_code_cancel or "").strip() or None
    normalized_next_node_code = (next_node_code or "").strip() or None
    normalized_cond_var_key = (cond_var_key or "").strip() or None
    normalized_cond_operator = (cond_operator or "").strip().upper() or None
    normalized_cond_value = (cond_value or "").strip()
    normalized_cond_value = normalized_cond_value if normalized_cond_value else None
    normalized_next_true = (next_node_code_true or "").strip() or None
    normalized_next_false = (next_node_code_false or "").strip() or None

    if not clean_title:
        return "Заполните название узла.", {}

    if normalized_node_type not in NODE_TYPES:
        return "Некорректный тип узла", {}

    if normalized_node_type == "MESSAGE" and not clean_message:
        return "Заполните текст сообщения", {}

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

        min_len_value = _to_optional_int(input_min_len)
        if min_len_value is None or min_len_value < 0:
            min_len_value = 0
    else:
        min_len_value = None

    config_json: dict | None = None

    if normalized_node_type == "CONDITION":
        normalized_condition_type = (condition_type or "LEGACY").strip().upper()

        if normalized_condition_type == "CHECK_SUBSCRIPTION":
            channels_raw = cond_sub_channels or ""
            channels: list[str] = []
            for row in channels_raw.replace(",", "\n").split("\n"):
                normalized = row.strip()
                if normalized:
                    channels.append(normalized)

            if not channels:
                return "Укажите хотя бы один канал для проверки подписки", {}

            config_json = {
                "condition_type": "CHECK_SUBSCRIPTION",
                "condition_payload": {
                    "channels": channels,
                    "on_success_node": (cond_sub_on_success or "").strip()
                    or normalized_next_true,
                    "on_fail_node": (cond_sub_on_fail or "").strip()
                    or normalized_next_false
                    or node_code,
                    "fail_message": (cond_sub_fail_message or "").strip()
                    or "Подпишитесь на канал и нажмите «Проверить подписку».",
                    "subscribe_url": (cond_sub_subscribe_url or "").strip() or None,
                    "check_button_text": (cond_sub_check_button_text or "").strip()
                    or "Проверить подписку",
                    "subscribe_button_text": (
                        (cond_sub_subscribe_button_text or "").strip()
                        or "Подписаться"
                    ),
                },
            }

            normalized_cond_var_key = None
            normalized_cond_operator = None
            normalized_cond_value = None
            normalized_next_true = config_json["condition_payload"].get("on_success_node")
            normalized_next_false = config_json["condition_payload"].get("on_fail_node")

            if not normalized_next_true or not normalized_next_false:
                return "Укажите узлы для перехода при успехе и провале проверки подписки", {}
        else:
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
            config_json = {"condition_type": "LEGACY"}

    if normalized_node_type == "ACTION":
        normalized_next_success = None
        normalized_next_cancel = None

    payload = {
        "title": clean_title,
        "message_text": clean_message or " ",
        "parse_mode": clean_parse_mode,
        "image_url": image_url or None,
        "is_enabled": is_enabled,
        "clear_chat": bool(clear_chat),
        "node_type": normalized_node_type,
        "input_type": normalized_input_type,
        "input_var_key": normalized_var_key,
        "input_required": bool(input_required),
        "input_min_len": min_len_value,
        "input_error_text": input_error_text or None,
        "next_node_code_success": normalized_next_success,
        "next_node_code_cancel": normalized_next_cancel,
        "next_node_code": normalized_next_node_code,
        "cond_var_key": normalized_cond_var_key,
        "cond_operator": normalized_cond_operator,
        "cond_value": normalized_cond_value,
        "next_node_code_true": normalized_next_true,
        "next_node_code_false": normalized_next_false,
        "config_json": config_json,
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
                "config_json": None,
            }
        )

    return None, payload


def _parse_actions_from_form(form) -> tuple[str | None, list[dict]]:
    action_types = form.getlist("action_type") if hasattr(form, "getlist") else []
    if not action_types:
        return None, []

    sort_orders = form.getlist("action_sort") if hasattr(form, "getlist") else []
    enabled_flags = form.getlist("action_enabled") if hasattr(form, "getlist") else []
    var_keys = form.getlist("action_var_key") if hasattr(form, "getlist") else []
    values = form.getlist("action_value") if hasattr(form, "getlist") else []
    steps = form.getlist("action_step") if hasattr(form, "getlist") else []
    tags = form.getlist("action_tag") if hasattr(form, "getlist") else []
    texts = form.getlist("action_text") if hasattr(form, "getlist") else []
    node_codes = form.getlist("action_node_code") if hasattr(form, "getlist") else []

    actions: list[dict] = []
    for idx, raw_type in enumerate(action_types):
        normalized_type = (raw_type or "").strip().upper()
        if not normalized_type:
            continue
        if normalized_type not in ACTION_TYPES:
            return f"Некорректный тип действия №{idx + 1}", []

        payload: dict[str, object] = {}
        var_key = (var_keys[idx] if idx < len(var_keys) else "") or ""
        value = values[idx] if idx < len(values) else ""
        step = steps[idx] if idx < len(steps) else ""
        tag = tags[idx] if idx < len(tags) else ""
        text_value = texts[idx] if idx < len(texts) else ""
        node_code = (node_codes[idx] if idx < len(node_codes) else "") or ""

        if normalized_type in {"SET_VAR", "INCREMENT_VAR", "DECREMENT_VAR", "CLEAR_VAR"}:
            if not var_key:
                return f"Заполните ключ переменной для действия №{idx + 1}", []
            payload["key"] = var_key
            if normalized_type == "SET_VAR":
                payload["value"] = value
            if normalized_type in {"INCREMENT_VAR", "DECREMENT_VAR"}:
                try:
                    payload["step"] = int(step or 1)
                except Exception:
                    payload["step"] = 1

        if normalized_type in {"ADD_TAG", "REMOVE_TAG"}:
            if not tag:
                return f"Заполните тег для действия №{idx + 1}", []
            payload["tag"] = tag

        if normalized_type in {"SEND_MESSAGE", "SEND_ADMIN_MESSAGE", "REQUEST_CONTACT", "REQUEST_LOCATION"}:
            if not text_value and normalized_type in {"SEND_MESSAGE", "SEND_ADMIN_MESSAGE"}:
                return f"Заполните текст для действия №{idx + 1}", []
            if text_value:
                payload["text"] = text_value

        if normalized_type == "GOTO_NODE":
            if not node_code:
                return f"Укажите код узла для перехода в действии №{idx + 1}", []
            payload["node_code"] = node_code

        sort_value = sort_orders[idx] if idx < len(sort_orders) else idx
        try:
            sort_order = int(sort_value)
        except Exception:
            sort_order = idx

        is_enabled = (enabled_flags[idx] if idx < len(enabled_flags) else "1") == "1"

        actions.append(
            {
                "action_type": normalized_type,
                "payload": payload,
                "sort_order": sort_order,
                "is_enabled": is_enabled,
            }
        )

    return None, actions


def _save_node_actions(db: Session, node_code: str, actions: list[dict]) -> None:
    db.query(BotNodeAction).filter(BotNodeAction.node_code == node_code).delete()
    for idx, action in enumerate(actions):
        db.add(
            BotNodeAction(
                node_code=node_code,
                action_type=action.get("action_type"),
                action_payload=action.get("payload"),
                sort_order=action.get("sort_order", idx) or idx,
                is_enabled=bool(action.get("is_enabled", True)),
            )
        )
    db.commit()


def _convert_to_action_models(actions: list[dict], node_code: str | None = None) -> list[BotNodeAction]:
    converted: list[BotNodeAction] = []
    for idx, action in enumerate(actions):
        converted.append(
            BotNodeAction(
                node_code=node_code or "",
                action_type=action.get("action_type"),
                action_payload=action.get("payload"),
                sort_order=action.get("sort_order", idx) or idx,
                is_enabled=bool(action.get("is_enabled", True)),
            )
        )
    return converted


def _serialize_actions(actions: list[BotNodeAction]) -> list[dict]:
    serialized: list[dict] = []
    for action in actions:
        serialized.append(
            {
                "action_type": action.action_type,
                "action_payload": action.action_payload or {},
                "sort_order": action.sort_order or 0,
                "is_enabled": bool(action.is_enabled),
            }
        )
    return serialized


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
            "actions": [],
            "actions_json": [],
            "references": {"nodes": [], "buttons": [], "triggers": []},
        },
    )


@router.post("/nodes/new")
async def create_node(
    request: Request,
    code: str = Form(...),
    title: str = Form(...),
    message_text: str | None = Form(None),
    parse_mode: str = Form("HTML"),
    image_url: str | None = Form(None),
    is_enabled: bool = Form(False),
    clear_chat: bool = Form(False),
    node_type: str = Form("MESSAGE"),
    input_type: str | None = Form(None),
    input_var_key: str | None = Form(None),
    input_required: bool = Form(True),
    input_min_len: str | None = Form(None),
    input_error_text: str | None = Form(None),
    next_node_code_success: str | None = Form(None),
    next_node_code_cancel: str | None = Form(None),
    next_node_code: str | None = Form(None),
    cond_var_key: str | None = Form(None),
    cond_operator: str | None = Form(None),
    cond_value: str | None = Form(None),
    next_node_code_true: str | None = Form(None),
    next_node_code_false: str | None = Form(None),
    condition_type: str | None = Form(None),
    cond_sub_channels: str | None = Form(None),
    cond_sub_on_success: str | None = Form(None),
    cond_sub_on_fail: str | None = Form(None),
    cond_sub_fail_message: str | None = Form(None),
    cond_sub_subscribe_url: str | None = Form(None),
    cond_sub_check_button_text: str | None = Form(None),
    cond_sub_subscribe_button_text: str | None = Form(None),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    form = await request.form()
    actions_error, actions = _parse_actions_from_form(form)

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
                "references": {"nodes": [], "buttons": [], "triggers": []},
            },
            status_code=400,
        )

    error, payload = _prepare_node_payload(
        node_code=code,
        title=title,
        message_text=message_text,
        parse_mode=parse_mode,
        image_url=image_url,
        is_enabled=is_enabled,
        clear_chat=clear_chat,
        node_type=node_type,
        input_type=input_type,
        input_var_key=input_var_key,
        input_required=input_required,
        input_min_len=input_min_len,
        input_error_text=input_error_text,
        next_node_code_success=next_node_code_success,
        next_node_code_cancel=next_node_code_cancel,
        next_node_code=next_node_code,
        cond_var_key=cond_var_key,
        cond_operator=cond_operator,
        cond_value=cond_value,
        next_node_code_true=next_node_code_true,
        next_node_code_false=next_node_code_false,
        condition_type=condition_type,
        cond_sub_channels=cond_sub_channels,
        cond_sub_on_success=cond_sub_on_success,
        cond_sub_on_fail=cond_sub_on_fail,
        cond_sub_fail_message=cond_sub_fail_message,
        cond_sub_subscribe_url=cond_sub_subscribe_url,
        cond_sub_check_button_text=cond_sub_check_button_text,
        cond_sub_subscribe_button_text=cond_sub_subscribe_button_text,
    )

    if error or actions_error:
        draft_node = BotNode(code=code, **payload)
        render_actions = _convert_to_action_models(actions, code)
        return TEMPLATES.TemplateResponse(
            "adminbot_node_edit.html",
            {
                "request": request,
                "user": user,
                "node": draft_node,
                "error": error or actions_error,
                "actions": render_actions,
                "actions_json": _serialize_actions(render_actions),
                "references": {"nodes": [], "buttons": [], "triggers": []},
            },
            status_code=400,
        )

    db.add(BotNode(code=code, **payload))
    db.commit()

    if actions:
        _save_node_actions(db, code, actions)

    _bump_runtime(db)
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

    actions = (
        db.query(BotNodeAction)
        .filter(BotNodeAction.node_code == node.code)
        .order_by(BotNodeAction.sort_order, BotNodeAction.id)
        .all()
    )
    actions_json = _serialize_actions(actions)
    references = _find_incoming_links(db, node.code)

    return TEMPLATES.TemplateResponse(
        "adminbot_node_edit.html",
        {
            "request": request,
            "user": user,
            "node": node,
            "error": None,
            "actions": actions,
            "actions_json": actions_json,
            "references": references,
        },
    )


@router.post("/nodes/{node_id}/edit")
async def edit_node(
    request: Request,
    node_id: int,
    title: str = Form(...),
    message_text: str | None = Form(None),
    parse_mode: str = Form("HTML"),
    image_url: str | None = Form(None),
    is_enabled: bool = Form(False),
    clear_chat: bool = Form(False),
    node_type: str = Form("MESSAGE"),
    input_type: str | None = Form(None),
    input_var_key: str | None = Form(None),
    input_required: bool = Form(True),
    input_min_len: str | None = Form(None),
    input_error_text: str | None = Form(None),
    next_node_code_success: str | None = Form(None),
    next_node_code_cancel: str | None = Form(None),
    next_node_code: str | None = Form(None),
    cond_var_key: str | None = Form(None),
    cond_operator: str | None = Form(None),
    cond_value: str | None = Form(None),
    next_node_code_true: str | None = Form(None),
    next_node_code_false: str | None = Form(None),
    condition_type: str | None = Form(None),
    cond_sub_channels: str | None = Form(None),
    cond_sub_on_success: str | None = Form(None),
    cond_sub_on_fail: str | None = Form(None),
    cond_sub_fail_message: str | None = Form(None),
    cond_sub_subscribe_url: str | None = Form(None),
    cond_sub_check_button_text: str | None = Form(None),
    cond_sub_subscribe_button_text: str | None = Form(None),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = db.get(BotNode, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    form = await request.form()
    actions_error, actions = _parse_actions_from_form(form)

    error, payload = _prepare_node_payload(
        node_code=node.code,
        title=title,
        message_text=message_text,
        parse_mode=parse_mode,
        image_url=image_url,
        is_enabled=is_enabled,
        clear_chat=clear_chat,
        node_type=node_type,
        input_type=input_type,
        input_var_key=input_var_key,
        input_required=input_required,
        input_min_len=input_min_len,
        input_error_text=input_error_text,
        next_node_code_success=next_node_code_success,
        next_node_code_cancel=next_node_code_cancel,
        next_node_code=next_node_code,
        cond_var_key=cond_var_key,
        cond_operator=cond_operator,
        cond_value=cond_value,
        next_node_code_true=next_node_code_true,
        next_node_code_false=next_node_code_false,
        condition_type=condition_type,
        cond_sub_channels=cond_sub_channels,
        cond_sub_on_success=cond_sub_on_success,
        cond_sub_on_fail=cond_sub_on_fail,
        cond_sub_fail_message=cond_sub_fail_message,
        cond_sub_subscribe_url=cond_sub_subscribe_url,
        cond_sub_check_button_text=cond_sub_check_button_text,
        cond_sub_subscribe_button_text=cond_sub_subscribe_button_text,
    )

    if error or actions_error:
        draft_node = BotNode(code=node.code, **payload)
        draft_node.id = node.id
        render_actions = _convert_to_action_models(actions, node.code)
        return TEMPLATES.TemplateResponse(
            "adminbot_node_edit.html",
            {
                "request": request,
                "user": user,
                "node": draft_node,
                "error": error or actions_error,
                "actions": render_actions,
                "actions_json": _serialize_actions(render_actions),
                "references": _find_incoming_links(db, node.code),
            },
            status_code=400,
        )

    for field, value in payload.items():
        setattr(node, field, value)

    db.add(node)
    db.commit()

    _save_node_actions(db, node.code, actions)

    _bump_runtime(db)
    db.commit()

    return RedirectResponse(url="/adminbot/nodes", status_code=303)


@router.post("/nodes/{node_id}/delete")
async def delete_node(request: Request, node_id: int, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    node = db.get(BotNode, node_id)
    if not node:
        return RedirectResponse(url="/adminbot/nodes", status_code=303)

    try:
        _cleanup_node_links(db, node.code)
        db.delete(node)
        db.commit()
        _bump_runtime(db)
        db.commit()
        return RedirectResponse(url="/adminbot/nodes", status_code=303)
    except Exception as exc:  # noqa: WPS440
        db.rollback()
        actions = (
            db.query(BotNodeAction)
            .filter(BotNodeAction.node_code == node.code)
            .order_by(BotNodeAction.sort_order, BotNodeAction.id)
            .all()
        )
        return TEMPLATES.TemplateResponse(
            "adminbot_node_edit.html",
            {
                "request": request,
                "user": user,
                "node": node,
                "error": f"Не удалось удалить узел: {exc}",
                "actions": actions,
                "actions_json": _serialize_actions(actions),
                "references": _find_incoming_links(db, node.code),
            },
            status_code=500,
        )
