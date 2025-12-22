"""Маршруты для шаблонов AdminBot."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotButton, BotNode, BotNodeAction, BotRuntime, BotTemplate, BotTrigger
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _normalize_code(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized.upper() or "NODE"


def _generate_code_map(
    nodes: Iterable[dict], existing_codes: set[str], template_code: str | None = None
) -> dict[str, str]:
    used = {code.upper() for code in existing_codes if code}
    prefix = _normalize_code(template_code or "")
    mapping: dict[str, str] = {}

    for node in nodes:
        source_code = (node.get("code") or "NODE").strip()
        base_code = _normalize_code(source_code)
        candidate = base_code
        suffix = 1
        while candidate.upper() in used:
            if prefix:
                candidate = f"{prefix}_{base_code}"
            else:
                candidate = base_code
            if suffix > 1:
                candidate = f"{candidate}_{suffix}"
            suffix += 1
        used.add(candidate.upper())
        mapping[source_code] = candidate
        if source_code.upper() not in mapping:
            mapping[source_code.upper()] = candidate
    return mapping


def _map_node_code(value: str | None, code_map: dict[str, str]) -> str | None:
    if not value:
        return None
    return code_map.get(value) or code_map.get(value.upper()) or value


def _map_callback_payload(payload: str, code_map: dict[str, str]) -> str:
    prefixes = ["OPEN_NODE:", "INPUT_CANCEL:", "SEND_TEXT:"]
    for prefix in prefixes:
        if payload.startswith(prefix):
            target = payload.split(":", maxsplit=1)[1]
            mapped = _map_node_code(target, code_map) or target
            return f"{prefix}{mapped}"
    return payload


def _map_action_payload(payload: dict | None, code_map: dict[str, str]) -> dict:
    payload = payload or {}
    mapped: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str) and (key.endswith("node_code") or key == "node_code"):
            mapped[key] = _map_node_code(value, code_map)
        elif isinstance(value, str) and value in code_map:
            mapped[key] = code_map[value]
        else:
            mapped[key] = value
    return mapped


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _build_node_payload(node_data: dict, *, code: str, code_map: dict[str, str]) -> dict:
    node_type = (node_data.get("node_type") or "MESSAGE").upper()
    payload = {
        "code": code,
        "title": node_data.get("title") or code,
        "message_text": node_data.get("message_text") or "",
        "parse_mode": node_data.get("parse_mode") or "HTML",
        "image_url": node_data.get("image_url"),
        "node_type": node_type,
        "input_type": node_data.get("input_type"),
        "input_var_key": node_data.get("input_var_key"),
        "input_required": bool(node_data.get("input_required", True)),
        "input_min_len": _to_int(node_data.get("input_min_len"), 0)
        if node_type == "INPUT"
        else None,
        "input_error_text": node_data.get("input_error_text"),
        "next_node_code_success": _map_node_code(
            node_data.get("next_node_code_success"), code_map
        ),
        "next_node_code_cancel": _map_node_code(
            node_data.get("next_node_code_cancel"), code_map
        ),
        "next_node_code": _map_node_code(node_data.get("next_node_code"), code_map),
        "cond_var_key": node_data.get("cond_var_key"),
        "cond_operator": node_data.get("cond_operator"),
        "cond_value": node_data.get("cond_value"),
        "next_node_code_true": _map_node_code(
            node_data.get("next_node_code_true"), code_map
        ),
        "next_node_code_false": _map_node_code(
            node_data.get("next_node_code_false"), code_map
        ),
        "is_enabled": bool(node_data.get("is_enabled", True)),
        "config_json": node_data.get("config_json"),
    }

    if node_type != "INPUT":
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

    if node_type != "CONDITION":
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

    return payload


def _make_trigger_value_unique(
    trigger_type: str, trigger_value: str | None, existing: set[tuple[str, str]], template_code: str
) -> str | None:
    normalized_type = (trigger_type or "").upper()
    if trigger_value is None:
        return None

    base_value = trigger_value.strip()
    candidate = base_value or ""
    suffix = 1
    while (normalized_type, candidate.lower()) in existing:
        suffix += 1
        candidate = f"{base_value}_{template_code}_{suffix}"

    existing.add((normalized_type, candidate.lower()))
    return candidate or None


def _bump_runtime(db: Session) -> None:
    runtime = db.query(BotRuntime).first()
    if not runtime:
        runtime = BotRuntime(config_version=1)
    runtime.config_version = (runtime.config_version or 1) + 1
    db.add(runtime)


def _apply_template(db: Session, template: BotTemplate) -> dict:
    template_data = template.template_json or {}
    nodes_data = template_data.get("nodes") or []
    triggers_data = template_data.get("triggers") or []

    if not nodes_data:
        raise ValueError("В шаблоне нет узлов для применения")

    existing_codes = {code for (code,) in db.query(BotNode.code).all() if code}
    code_map = _generate_code_map(nodes_data, existing_codes, template.code)

    created_nodes: list[dict[str, Any]] = []
    buttons_created = 0
    for node_data in nodes_data:
        source_code = node_data.get("code") or "NODE"
        mapped_code = code_map.get(source_code, _normalize_code(source_code))
        payload = _build_node_payload(node_data, code=mapped_code, code_map=code_map)
        node_model = BotNode(**payload)
        db.add(node_model)
        db.flush()

        for button_data in node_data.get("buttons") or []:
            btn_payload = _map_callback_payload(
                button_data.get("payload", ""), code_map
            )
            action_type = (button_data.get("action_type") or "").upper()
            target_code = button_data.get("target_node_code")
            if target_code:
                target_code = code_map.get(target_code, target_code)

            url_value = button_data.get("url")
            webapp_value = button_data.get("webapp_url")
            legacy_type = button_data.get("type") or "callback"
            legacy_payload = btn_payload

            if action_type == "NODE":
                if not target_code and btn_payload.startswith("OPEN_NODE:"):
                    target_code = btn_payload.split(":", maxsplit=1)[1]
                legacy_type = "callback"
                legacy_payload = (
                    f"OPEN_NODE:{target_code}" if target_code else btn_payload
                )
            elif action_type == "URL":
                legacy_type = "url"
                legacy_payload = url_value or btn_payload
            elif action_type == "WEBAPP":
                legacy_type = "webapp"
                legacy_payload = webapp_value or btn_payload
            elif legacy_type == "url":
                action_type = "URL"
                url_value = url_value or btn_payload
            elif legacy_type == "webapp":
                action_type = "WEBAPP"
                webapp_value = webapp_value or btn_payload
            else:
                action_type = "LEGACY"

            db.add(
                BotButton(
                    node_id=node_model.id,
                    title=button_data.get("title") or "Кнопка",
                    type=legacy_type,
                    payload=legacy_payload,
                    action_type=action_type or "NODE",
                    target_node_code=target_code,
                    url=url_value,
                    webapp_url=webapp_value,
                    row=_to_int(button_data.get("row"), 0),
                    pos=_to_int(button_data.get("pos"), 0),
                    is_enabled=bool(button_data.get("is_enabled", True)),
                )
            )
            buttons_created += 1

        for action_data in node_data.get("actions") or []:
            action_type = action_data.get("action_type")
            if not action_type:
                continue
            db.add(
                BotNodeAction(
                    node_code=node_model.code,
                    action_type=action_type,
                    action_payload=_map_action_payload(action_data.get("payload"), code_map),
                    sort_order=_to_int(action_data.get("sort_order"), 0),
                    is_enabled=bool(action_data.get("is_enabled", True)),
                )
            )

        created_nodes.append({"code": node_model.code, "title": node_model.title})

    existing_triggers = {
        (tr.trigger_type or "", (tr.trigger_value or "").strip().lower())
        for tr in db.query(BotTrigger).all()
    }
    created_triggers: list[dict[str, Any]] = []

    for trigger_data in triggers_data:
        trig_type = (trigger_data.get("trigger_type") or "").upper()
        trig_value = trigger_data.get("trigger_value")
        unique_value = _make_trigger_value_unique(
            trig_type, trig_value, existing_triggers, template.code
        )

        target_node = _map_node_code(trigger_data.get("target_node_code"), code_map)
        trigger = BotTrigger(
            trigger_type=trig_type,
            trigger_value=unique_value,
            match_mode=(trigger_data.get("match_mode") or "EXACT").upper(),
            target_node_code=target_node or "",
            priority=_to_int(trigger_data.get("priority"), 100),
            is_enabled=bool(trigger_data.get("is_enabled", True)),
        )
        db.add(trigger)
        created_triggers.append(
            {
                "trigger_type": trig_type,
                "trigger_value": unique_value,
                "target_node_code": target_node,
            }
        )

    _bump_runtime(db)
    db.commit()

    return {
        "code_map": code_map,
        "nodes": created_nodes,
        "triggers": created_triggers,
        "buttons_created": buttons_created,
    }


def _build_preview(nodes_data: list[dict], triggers_data: list[dict], code_map: dict[str, str]):
    preview_nodes = []
    for node in nodes_data:
        source = node.get("code") or "NODE"
        preview_nodes.append(
            {
                "code": source,
                "new_code": code_map.get(source, source),
                "title": node.get("title") or source,
                "node_type": (node.get("node_type") or "MESSAGE").upper(),
                "buttons": node.get("buttons") or [],
                "actions": node.get("actions") or [],
                "next_node": _map_node_code(node.get("next_node_code"), code_map),
                "next_success": _map_node_code(
                    node.get("next_node_code_success"), code_map
                ),
                "next_cancel": _map_node_code(node.get("next_node_code_cancel"), code_map),
            }
        )

    preview_triggers = []
    for trigger in triggers_data:
        preview_triggers.append(
            {
                "trigger_type": (trigger.get("trigger_type") or "").upper(),
                "trigger_value": trigger.get("trigger_value"),
                "match_mode": (trigger.get("match_mode") or "EXACT").upper(),
                "target_node_code": _map_node_code(
                    trigger.get("target_node_code"), code_map
                ),
            }
        )

    return preview_nodes, preview_triggers


@router.get("/templates")
async def list_templates(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    templates = (
        db.query(BotTemplate)
        .order_by(BotTemplate.created_at.desc(), BotTemplate.id.desc())
        .all()
    )
    return TEMPLATES.TemplateResponse(
        "adminbot_templates_list.html",
        {"request": request, "user": user, "templates": templates},
    )


@router.get("/templates/{template_code}")
async def template_preview(
    request: Request, template_code: str, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    template = db.query(BotTemplate).filter(BotTemplate.code == template_code).first()
    if not template:
        return RedirectResponse(url="/adminbot/templates", status_code=303)

    template_data = template.template_json or {}
    nodes_data = template_data.get("nodes") or []
    triggers_data = template_data.get("triggers") or []
    code_map = _generate_code_map(
        nodes_data,
        {code for (code,) in db.query(BotNode.code).all() if code},
        template.code,
    )
    preview_nodes, preview_triggers = _build_preview(nodes_data, triggers_data, code_map)

    return TEMPLATES.TemplateResponse(
        "adminbot_template_confirm.html",
        {
            "request": request,
            "user": user,
            "template": template,
            "preview_nodes": preview_nodes,
            "preview_triggers": preview_triggers,
            "code_map": code_map,
            "applied": False,
            "result": None,
            "error": None,
        },
    )


@router.post("/templates/{template_code}/apply")
async def apply_template(
    request: Request, template_code: str, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    template = db.query(BotTemplate).filter(BotTemplate.code == template_code).first()
    if not template:
        return RedirectResponse(url="/adminbot/templates", status_code=303)

    template_data = template.template_json or {}
    nodes_data = template_data.get("nodes") or []
    triggers_data = template_data.get("triggers") or []
    code_map = _generate_code_map(
        nodes_data, {code for (code,) in db.query(BotNode.code).all() if code}
    )
    preview_nodes, preview_triggers = _build_preview(nodes_data, triggers_data, code_map)

    try:
        result = _apply_template(db, template)
    except Exception as exc:  # noqa: WPS440
        return TEMPLATES.TemplateResponse(
            "adminbot_template_confirm.html",
            {
                "request": request,
                "user": user,
                "template": template,
                "preview_nodes": preview_nodes,
                "preview_triggers": preview_triggers,
                "code_map": code_map,
                "applied": False,
                "result": None,
                "error": str(exc),
            },
            status_code=400,
        )

    render_triggers = result.get("triggers") or preview_triggers

    return TEMPLATES.TemplateResponse(
        "adminbot_template_confirm.html",
        {
            "request": request,
            "user": user,
            "template": template,
            "preview_nodes": preview_nodes,
            "preview_triggers": render_triggers,
            "code_map": code_map,
            "applied": True,
            "result": result,
            "error": None,
        },
    )
