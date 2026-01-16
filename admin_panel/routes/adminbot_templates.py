"""Маршруты для шаблонов AdminBot."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import (
    BotAutomationRule,
    BotButton,
    BotButtonPreset,
    BotNode,
    BotNodeAction,
    BotRuntime,
    BotTemplate,
    BotTrigger,
)
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


def _slugify(value: str | None) -> str:
    normalized = "".join(
        char.lower() if char.isalnum() else "-" for char in (value or "")
    )
    normalized = "-".join(filter(None, normalized.split("-")))
    return normalized or "item"


def _reserve_unique_code(base_code: str, used: set[str]) -> str:
    candidate = base_code
    suffix = 1
    while candidate.upper() in used:
        suffix += 1
        candidate = f"{base_code}_{suffix}"
    used.add(candidate.upper())
    return candidate


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


def _node_slug(node_data: dict) -> str:
    return _slugify(
        node_data.get("slug")
        or node_data.get("code")
        or node_data.get("title")
        or "node"
    )


def _button_slug(button_data: dict) -> str:
    return _slugify(button_data.get("slug") or button_data.get("title") or "button")


def _preset_slug(preset_data: dict) -> str:
    return _slugify(preset_data.get("slug") or preset_data.get("title") or "preset")


def _automation_slug(automation_data: dict) -> str:
    return _slugify(
        automation_data.get("slug") or automation_data.get("title") or "automation"
    )


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


def _build_template_plan(
    db: Session,
    template: BotTemplate,
    replace_items: set[str] | None = None,
) -> dict:
    replace_items = replace_items or set()
    template_data = template.template_json or {}
    nodes_data = template_data.get("nodes") or []
    triggers_data = template_data.get("triggers") or []
    presets_data = template_data.get("presets") or []
    automations_data = template_data.get("automations") or []

    existing_nodes = db.query(BotNode).all()
    existing_codes = {node.code for node in existing_nodes if node.code}
    existing_nodes_by_slug: dict[str, BotNode] = {}
    for node in existing_nodes:
        slug = _slugify(node.code or node.title)
        existing_nodes_by_slug.setdefault(slug, node)

    node_id_map = {node.id: node.code for node in existing_nodes}
    existing_buttons_by_slug: dict[str, list[BotButton]] = {}
    for button in db.query(BotButton).all():
        node_code = node_id_map.get(button.node_id)
        if not node_code:
            continue
        key = f"{node_code}::{_slugify(button.title)}"
        existing_buttons_by_slug.setdefault(key, []).append(button)

    existing_presets_by_slug = {
        _slugify(preset.title): preset
        for preset in db.query(BotButtonPreset).all()
    }
    existing_automations_by_slug = {
        _slugify(rule.title): rule for rule in db.query(BotAutomationRule).all()
    }

    used_codes = {code.upper() for code in existing_codes if code}
    code_map: dict[str, str] = {}
    node_plans: list[dict[str, Any]] = []

    for node in nodes_data:
        source_code = node.get("code") or "NODE"
        slug = _node_slug(node)
        conflict_node = existing_nodes_by_slug.get(slug)
        replace_key = f"node:{slug}"
        if conflict_node:
            target_code = conflict_node.code
            action = "replace" if replace_key in replace_items else "skip"
        else:
            base_code = _normalize_code(source_code)
            target_code = _reserve_unique_code(base_code, used_codes)
            action = "create"

        code_map[source_code] = target_code
        code_map[source_code.upper()] = target_code
        node_plans.append(
            {
                "slug": slug,
                "source_code": source_code,
                "target_code": target_code,
                "title": node.get("title") or source_code,
                "node_type": (node.get("node_type") or "MESSAGE").upper(),
                "buttons": node.get("buttons") or [],
                "actions": node.get("actions") or [],
                "action": action,
                "replace_key": replace_key,
                "conflict": conflict_node is not None,
            }
        )

    button_plans: list[dict[str, Any]] = []
    for node in nodes_data:
        target_code = code_map.get(node.get("code") or "NODE")
        if not target_code:
            continue
        for button in node.get("buttons") or []:
            slug = _button_slug(button)
            key = f"{target_code}::{slug}"
            replace_key = f"button:{key}"
            conflict_buttons = existing_buttons_by_slug.get(key) or []
            if conflict_buttons:
                action = "replace" if replace_key in replace_items else "skip"
            else:
                action = "create"
            button_plans.append(
                {
                    "slug": slug,
                    "node_code": target_code,
                    "title": button.get("title") or "Кнопка",
                    "action": action,
                    "replace_key": replace_key,
                    "conflict": bool(conflict_buttons),
                }
            )

    preset_plans: list[dict[str, Any]] = []
    for preset in presets_data:
        slug = _preset_slug(preset)
        replace_key = f"preset:{slug}"
        conflict_preset = existing_presets_by_slug.get(slug)
        if conflict_preset:
            action = "replace" if replace_key in replace_items else "skip"
        else:
            action = "create"
        preset_plans.append(
            {
                "slug": slug,
                "title": preset.get("title") or "Пресет",
                "scope": preset.get("scope") or "user",
                "action": action,
                "replace_key": replace_key,
                "conflict": conflict_preset is not None,
            }
        )

    automation_plans: list[dict[str, Any]] = []
    for automation in automations_data:
        slug = _automation_slug(automation)
        replace_key = f"automation:{slug}"
        conflict_rule = existing_automations_by_slug.get(slug)
        if conflict_rule:
            action = "replace" if replace_key in replace_items else "skip"
        else:
            action = "create"
        automation_plans.append(
            {
                "slug": slug,
                "title": automation.get("title") or "Автоматизация",
                "trigger_type": automation.get("trigger_type") or "UNSET",
                "action": action,
                "replace_key": replace_key,
                "conflict": conflict_rule is not None,
            }
        )

    preview_nodes = []
    for node in node_plans:
        source = node["source_code"]
        preview_nodes.append(
            {
                "code": source,
                "new_code": node["target_code"],
                "title": node["title"],
                "node_type": node["node_type"],
                "buttons": node["buttons"],
                "actions": node["actions"],
                "next_node": _map_node_code(
                    (next((n for n in nodes_data if (n.get("code") or "NODE") == source), {}) or {}).get("next_node_code"),
                    code_map,
                ),
                "next_success": _map_node_code(
                    (next((n for n in nodes_data if (n.get("code") or "NODE") == source), {}) or {}).get("next_node_code_success"),
                    code_map,
                ),
                "next_cancel": _map_node_code(
                    (next((n for n in nodes_data if (n.get("code") or "NODE") == source), {}) or {}).get("next_node_code_cancel"),
                    code_map,
                ),
                "action": node["action"],
                "replace_key": node["replace_key"],
                "conflict": node["conflict"],
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

    return {
        "template_data": template_data,
        "nodes": node_plans,
        "buttons": button_plans,
        "presets": preset_plans,
        "automations": automation_plans,
        "triggers": triggers_data,
        "preview_nodes": preview_nodes,
        "preview_triggers": preview_triggers,
        "code_map": code_map,
        "existing_presets_by_slug": existing_presets_by_slug,
        "existing_automations_by_slug": existing_automations_by_slug,
    }


def _apply_template(db: Session, template: BotTemplate, plan: dict) -> dict:
    template_data = plan.get("template_data") or {}
    nodes_data = template_data.get("nodes") or []
    triggers_data = template_data.get("triggers") or []
    presets_data = template_data.get("presets") or []
    automations_data = template_data.get("automations") or []
    code_map = plan.get("code_map") or {}

    if not nodes_data:
        raise ValueError("В шаблоне нет узлов для применения")

    node_actions_map = {entry["source_code"]: entry for entry in plan.get("nodes", [])}
    button_actions_map = {
        f"{entry['node_code']}::{entry['slug']}": entry
        for entry in plan.get("buttons", [])
    }
    preset_actions_map = {entry["slug"]: entry for entry in plan.get("presets", [])}
    automation_actions_map = {
        entry["slug"]: entry for entry in plan.get("automations", [])
    }

    existing_nodes_by_code = {
        node.code: node for node in db.query(BotNode).all() if node.code
    }

    created_nodes: list[dict[str, Any]] = []
    buttons_created = 0
    actions_created = 0

    for node_data in nodes_data:
        source_code = node_data.get("code") or "NODE"
        mapped_code = code_map.get(source_code, _normalize_code(source_code))
        plan_entry = node_actions_map.get(source_code, {})
        action = plan_entry.get("action")

        if action == "skip":
            continue

        payload = _build_node_payload(node_data, code=mapped_code, code_map=code_map)
        node_model = existing_nodes_by_code.get(mapped_code)

        if action == "replace" and node_model:
            for field, value in payload.items():
                setattr(node_model, field, value)
            db.add(node_model)
        else:
            node_model = BotNode(**payload)
            db.add(node_model)
            db.flush()

        if action == "replace":
            db.query(BotNodeAction).filter(
                BotNodeAction.node_code == node_model.code
            ).delete()

        for action_data in node_data.get("actions") or []:
            db.add(
                BotNodeAction(
                    node_code=node_model.code,
                    action_type=(action_data.get("action_type") or "").upper(),
                    action_payload=_map_action_payload(
                        action_data.get("payload"), code_map
                    ),
                    sort_order=_to_int(action_data.get("sort_order"), 0),
                    is_enabled=bool(action_data.get("is_enabled", True)),
                )
            )
            actions_created += 1

        for button_data in node_data.get("buttons") or []:
            button_slug = _button_slug(button_data)
            button_key = f"{node_model.code}::{button_slug}"
            button_action = button_actions_map.get(button_key, {}).get("action")
            if button_action == "skip":
                continue

            if button_action == "replace":
                existing_buttons = (
                    db.query(BotButton)
                    .filter(BotButton.node_id == node_model.id)
                    .all()
                )
                for existing_button in existing_buttons:
                    if _slugify(existing_button.title) == button_slug:
                        db.delete(existing_button)

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

            db.add(
                BotButton(
                    node_id=node_model.id,
                    title=button_data.get("title") or "Кнопка",
                    type=legacy_type,
                    payload=legacy_payload,
                    action_type=action_type or "NODE",
                    action_payload=button_data.get("action_payload"),
                    target_node_code=target_code,
                    url=url_value,
                    webapp_url=webapp_value,
                    row=_to_int(button_data.get("row"), 0),
                    pos=_to_int(button_data.get("pos"), 0),
                    is_enabled=bool(button_data.get("is_enabled", True)),
                    render=(button_data.get("render") or "INLINE").upper(),
                )
            )
            buttons_created += 1

        created_nodes.append(
            {
                "code": source_code,
                "new_code": node_model.code,
                "title": node_model.title,
                "node_type": node_model.node_type,
            }
        )

    preset_id_by_slug: dict[str, int] = {}
    for preset_data in presets_data:
        slug = _preset_slug(preset_data)
        action = preset_actions_map.get(slug, {}).get("action")
        if action == "skip":
            existing_preset = plan.get("existing_presets_by_slug", {}).get(slug)
            if existing_preset:
                preset_id_by_slug[slug] = int(existing_preset.id)
            continue

        if action == "replace":
            preset = plan.get("existing_presets_by_slug", {}).get(slug)
            if preset:
                preset.title = preset_data.get("title") or preset.title
                preset.scope = preset_data.get("scope") or preset.scope
                preset.buttons_json = preset_data.get("buttons_json") or preset.buttons_json
                preset.is_enabled = bool(preset_data.get("is_enabled", True))
                db.add(preset)
                preset_id_by_slug[slug] = int(preset.id)
                continue

        new_preset = BotButtonPreset(
            title=preset_data.get("title") or "Пресет",
            scope=preset_data.get("scope") or "user",
            buttons_json=preset_data.get("buttons_json") or [],
            is_enabled=bool(preset_data.get("is_enabled", True)),
        )
        db.add(new_preset)
        db.flush()
        preset_id_by_slug[slug] = int(new_preset.id)

    for automation_data in automations_data:
        slug = _automation_slug(automation_data)
        action = automation_actions_map.get(slug, {}).get("action")
        if action == "skip":
            continue

        actions_json = automation_data.get("actions_json") or []
        resolved_actions: list[dict[str, Any]] = []
        for action_item in actions_json:
            if not isinstance(action_item, dict):
                continue
            item = dict(action_item)
            preset_slug = item.pop("preset_slug", None)
            if preset_slug:
                preset_id = preset_id_by_slug.get(_slugify(preset_slug))
                if preset_id:
                    item["preset_id"] = preset_id
            resolved_actions.append(item)

        if action == "replace":
            rule = plan.get("existing_automations_by_slug", {}).get(slug)
            if rule:
                rule.title = automation_data.get("title") or rule.title
                rule.trigger_type = automation_data.get("trigger_type") or rule.trigger_type
                rule.conditions_json = automation_data.get("conditions_json")
                rule.actions_json = resolved_actions
                rule.is_enabled = bool(automation_data.get("is_enabled", True))
                db.add(rule)
                continue

        db.add(
            BotAutomationRule(
                title=automation_data.get("title") or "Автоматизация",
                trigger_type=automation_data.get("trigger_type") or "UNSET",
                conditions_json=automation_data.get("conditions_json"),
                actions_json=resolved_actions,
                is_enabled=bool(automation_data.get("is_enabled", True)),
            )
        )

    existing_triggers = {
        ((trigger.trigger_type or "").upper(), (trigger.trigger_value or "").lower())
        for trigger in db.query(BotTrigger).all()
    }
    created_triggers = []
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
        "actions_created": actions_created,
    }


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

    plan = _build_template_plan(db, template, replace_items=set())

    return TEMPLATES.TemplateResponse(
        "adminbot_template_confirm.html",
        {
            "request": request,
            "user": user,
            "template": template,
            "preview_nodes": plan["preview_nodes"],
            "preview_triggers": plan["preview_triggers"],
            "preview_presets": plan["presets"],
            "preview_automations": plan["automations"],
            "preview_buttons": plan["buttons"],
            "code_map": plan["code_map"],
            "replace_items": set(),
            "applied": False,
            "result": None,
            "error": None,
        },
    )


@router.post("/templates/{template_code}/delete")
async def delete_template(
    request: Request, template_code: str, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    template = db.query(BotTemplate).filter(BotTemplate.code == template_code).first()
    if template:
        db.delete(template)
        db.commit()

    return RedirectResponse(url="/adminbot/templates", status_code=303)


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

    form = await request.form()
    replace_items = set(form.getlist("replace_items"))
    plan = _build_template_plan(db, template, replace_items=replace_items)

    try:
        result = _apply_template(db, template, plan)
    except Exception as exc:  # noqa: WPS440
        return TEMPLATES.TemplateResponse(
            "adminbot_template_confirm.html",
            {
                "request": request,
                "user": user,
                "template": template,
                "preview_nodes": plan["preview_nodes"],
                "preview_triggers": plan["preview_triggers"],
                "preview_presets": plan["presets"],
                "preview_automations": plan["automations"],
                "preview_buttons": plan["buttons"],
                "code_map": plan["code_map"],
                "replace_items": replace_items,
                "applied": False,
                "result": None,
                "error": str(exc),
            },
            status_code=400,
        )

    render_triggers = result.get("triggers") or plan["preview_triggers"]

    return TEMPLATES.TemplateResponse(
        "adminbot_template_confirm.html",
        {
            "request": request,
            "user": user,
            "template": template,
            "preview_nodes": plan["preview_nodes"],
            "preview_triggers": render_triggers,
            "preview_presets": plan["presets"],
            "preview_automations": plan["automations"],
            "preview_buttons": plan["buttons"],
            "code_map": plan["code_map"],
            "replace_items": replace_items,
            "applied": True,
            "result": result,
            "error": None,
        },
    )
