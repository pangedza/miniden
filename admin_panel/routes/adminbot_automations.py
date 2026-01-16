import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotAutomationRule, BotButtonPreset
from models.admin_user import AdminRole
from services import automations as automations_service

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot, AdminRole.moderator)
logger = logging.getLogger(__name__)


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _normalize_actions(actions_raw: str | None) -> tuple[str | None, list[dict[str, Any]]]:
    if not actions_raw:
        return "Добавьте хотя бы одно действие", []

    try:
        data = json.loads(actions_raw)
    except json.JSONDecodeError:
        return "Не удалось разобрать список действий", []

    if not isinstance(data, list) or not data:
        return "Добавьте хотя бы одно действие", []
    return None, data


def _validate_actions(
    actions: list[dict[str, Any]],
    presets_map: dict[int, BotButtonPreset],
) -> tuple[str | None, list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []

    for action in actions:
        action_type = str(action.get("type") or "").strip().upper()
        if action_type not in automations_service.ACTION_LABELS:
            return "Выберите корректный тип действия", []

        if action_type in {
            automations_service.ACTION_SEND_USER_MESSAGE,
            automations_service.ACTION_SEND_ADMIN_MESSAGE,
        }:
            template = action.get("template") or {}
            title = str(template.get("title") or "").strip()
            body = str(template.get("body") or "").strip()
            items_enabled = bool(template.get("items_enabled"))
            items_fields = template.get("items_fields") or []
            if not title and not body and not items_enabled:
                return "Сообщение не может быть пустым", []

            normalized.append(
                {
                    "type": action_type,
                    "template": {
                        "title": title,
                        "body": body,
                        "items_enabled": items_enabled,
                        "items_fields": items_fields,
                        "items_title": str(template.get("items_title") or "Состав заказа").strip(),
                    },
                }
            )
            continue

        if action_type == automations_service.ACTION_ATTACH_BUTTONS:
            target = str(action.get("target") or "").strip().lower()
            if target not in automations_service.BUTTON_SCOPES:
                return "Для кнопок выберите, кому отправлять", []
            preset_id = action.get("preset_id")
            try:
                preset_id_int = int(preset_id)
            except (TypeError, ValueError):
                return "Выберите набор кнопок", []
            preset = presets_map.get(preset_id_int)
            if not preset:
                return "Набор кнопок не найден", []
            if preset.scope != target:
                return "Набор кнопок не соответствует выбранной аудитории", []
            normalized.append(
                {
                    "type": action_type,
                    "target": target,
                    "preset_id": preset_id_int,
                }
            )
            continue

        normalized.append({"type": action_type})

    return None, normalized


def _normalize_buttons(buttons_raw: str | None) -> tuple[str | None, list[dict[str, Any]]]:
    if not buttons_raw:
        return None, []

    try:
        data = json.loads(buttons_raw)
    except json.JSONDecodeError:
        return "Не удалось разобрать список кнопок", []

    if not isinstance(data, list):
        return "Некорректный список кнопок", []

    normalized: list[dict[str, Any]] = []
    for button in data:
        title = str(button.get("title") or "").strip()
        button_type = str(button.get("type") or "").strip().lower() or "callback"
        value = str(button.get("value") or "").strip()
        try:
            row = int(button.get("row") or 0)
        except (TypeError, ValueError):
            row = 0
        if not title or not value:
            continue
        if button_type not in {"callback", "url"}:
            button_type = "callback"
        normalized.append(
            {
                "title": title,
                "type": button_type,
                "value": value,
                "row": row,
            }
        )

    return None, normalized


def _build_presets_payload(presets: list[BotButtonPreset]) -> list[dict[str, Any]]:
    return [
        {"id": int(preset.id), "title": preset.title, "scope": preset.scope}
        for preset in presets
    ]


@router.get("/automations")
async def automations_list(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    rules = db.query(BotAutomationRule).order_by(BotAutomationRule.id.asc()).all()
    presets = db.query(BotButtonPreset).order_by(BotButtonPreset.scope, BotButtonPreset.id).all()
    presets_payload = _build_presets_payload(presets)

    return TEMPLATES.TemplateResponse(
        "adminbot_automations_list.html",
        {
            "request": request,
            "user": user,
            "rules": rules,
            "presets": presets,
            "trigger_labels": automations_service.TRIGGER_LABELS,
            "action_labels": automations_service.ACTION_LABELS,
        },
    )


@router.post("/automations/seed")
async def automations_seed(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    existing = db.query(BotAutomationRule).first()
    if existing:
        return RedirectResponse(url="/adminbot/automations", status_code=303)

    user_preset = db.query(BotButtonPreset).filter(BotButtonPreset.scope == "user").first()
    admin_preset = db.query(BotButtonPreset).filter(BotButtonPreset.scope == "admin").first()

    if not user_preset:
        user_preset = BotButtonPreset(
            title="Пользователь: заказ подтверждён",
            scope="user",
            buttons_json=[
                {"title": "Связаться с админом", "type": "callback", "value": "trigger:contact_manager", "row": 0},
                {"title": "Открыть витрину", "type": "url", "value": "{webapp_url}", "row": 1},
            ],
            is_enabled=True,
        )
        db.add(user_preset)
        db.flush()

    if not admin_preset:
        admin_preset = BotButtonPreset(
            title="Админ: карточка заказа",
            scope="admin",
            buttons_json=[
                {"title": "Написать клиенту", "type": "callback", "value": "admin:order:client:{user_id}", "row": 0},
                {"title": "Открыть витрину", "type": "url", "value": "{webapp_url}", "row": 1},
            ],
            is_enabled=True,
        )
        db.add(admin_preset)
        db.flush()

    rule = BotAutomationRule(
        title="WebApp заказ: сохранить и уведомить",
        trigger_type=automations_service.TRIGGER_WEBAPP_ORDER,
        conditions_json=[{"type": "source", "value": "webapp"}],
        actions_json=[
            {"type": automations_service.ACTION_SAVE_ORDER},
            {
                "type": automations_service.ACTION_ATTACH_BUTTONS,
                "target": "user",
                "preset_id": int(user_preset.id),
            },
            {
                "type": automations_service.ACTION_SEND_USER_MESSAGE,
                "template": {
                    "title": "✅ Заказ #{order_id} принят",
                    "body": "Мы уже получили заказ и скоро свяжемся.",
                    "items_enabled": True,
                    "items_fields": ["title", "qty", "price", "sum"],
                    "items_title": "Состав",
                },
            },
            {
                "type": automations_service.ACTION_ATTACH_BUTTONS,
                "target": "admin",
                "preset_id": int(admin_preset.id),
            },
            {
                "type": automations_service.ACTION_SEND_ADMIN_MESSAGE,
                "template": {
                    "title": "🛒 Новый заказ #{order_id}",
                    "body": "Пользователь: {user_name} (id {user_id}, {phone})",
                    "items_enabled": True,
                    "items_fields": ["title", "qty", "price", "sum"],
                    "items_title": "Состав",
                },
            },
        ],
        is_enabled=True,
    )
    db.add(rule)
    db.commit()

    return RedirectResponse(url="/adminbot/automations", status_code=303)


@router.get("/automations/new")
async def automations_new_form(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    presets = db.query(BotButtonPreset).order_by(BotButtonPreset.scope, BotButtonPreset.id).all()
    presets_payload = _build_presets_payload(presets)

    return TEMPLATES.TemplateResponse(
        "adminbot_automation_edit.html",
        {
            "request": request,
            "user": user,
            "rule": None,
            "form": None,
            "error": None,
            "missing_rule": False,
            "presets": presets,
            "presets_payload": presets_payload,
            "trigger_labels": automations_service.TRIGGER_LABELS,
            "action_labels": automations_service.ACTION_LABELS,
            "button_scopes": automations_service.BUTTON_SCOPES,
            "template_variables": automations_service.TEMPLATE_VARIABLES,
            "item_fields": automations_service.ITEM_FIELDS,
        },
    )


@router.post("/automations/new")
async def automations_create(
    request: Request,
    title: str = Form(...),
    trigger_type: str = Form(...),
    actions_json: str | None = Form(None),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    title_value = title.strip()
    trigger_value = trigger_type.strip().upper()
    if not title_value:
        error = "Введите название правила"
    elif trigger_value not in automations_service.TRIGGER_LABELS:
        error = "Выберите корректный триггер"
    else:
        error = None

    presets = db.query(BotButtonPreset).order_by(BotButtonPreset.scope, BotButtonPreset.id).all()
    presets_payload = _build_presets_payload(presets)
    presets_map = {int(preset.id): preset for preset in presets}

    actions_error, actions_list = _normalize_actions(actions_json)
    if not error:
        error = actions_error
    if not error:
        error, actions_list = _validate_actions(actions_list, presets_map)

    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_automation_edit.html",
            {
                "request": request,
                "user": user,
                "rule": None,
                "error": error,
                "form": {
                    "title": title_value,
                    "trigger_type": trigger_type,
                    "actions": actions_list,
                    "is_enabled": is_enabled,
                },
                "missing_rule": False,
                "presets": presets,
                "presets_payload": presets_payload,
                "trigger_labels": automations_service.TRIGGER_LABELS,
                "action_labels": automations_service.ACTION_LABELS,
                "button_scopes": automations_service.BUTTON_SCOPES,
                "template_variables": automations_service.TEMPLATE_VARIABLES,
                "item_fields": automations_service.ITEM_FIELDS,
            },
            status_code=422,
        )

    rule = BotAutomationRule(
        title=title_value,
        trigger_type=trigger_value,
        conditions_json=[{"type": "source", "value": "webapp"}],
        actions_json=actions_list,
        is_enabled=bool(is_enabled),
    )
    db.add(rule)
    db.commit()

    return RedirectResponse(url="/adminbot/automations", status_code=303)


@router.get("/automations/{rule_id}/edit")
async def automations_edit_form(
    request: Request, rule_id: int, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    logger.info("Adminbot automation edit: request", extra={"rule_id": rule_id})
    rule = db.get(BotAutomationRule, rule_id)
    if not rule:
        logger.info("Adminbot automation edit: rule not found", extra={"rule_id": rule_id})
        return TEMPLATES.TemplateResponse(
            "adminbot_automation_edit.html",
            {
                "request": request,
                "user": user,
                "rule": None,
                "form": None,
                "error": "Правило не найдено",
                "missing_rule": True,
                "presets": [],
                "presets_payload": [],
                "trigger_labels": automations_service.TRIGGER_LABELS,
                "action_labels": automations_service.ACTION_LABELS,
                "button_scopes": automations_service.BUTTON_SCOPES,
                "template_variables": automations_service.TEMPLATE_VARIABLES,
                "item_fields": automations_service.ITEM_FIELDS,
            },
            status_code=404,
        )

    presets = db.query(BotButtonPreset).order_by(BotButtonPreset.scope, BotButtonPreset.id).all()
    presets_payload = _build_presets_payload(presets)
    logger.info(
        "Adminbot automation edit: rule loaded",
        extra={"rule_id": rule_id, "presets_count": len(presets_payload)},
    )

    return TEMPLATES.TemplateResponse(
        "adminbot_automation_edit.html",
        {
            "request": request,
            "user": user,
            "rule": rule,
            "form": None,
            "error": None,
            "missing_rule": False,
            "presets": presets,
            "presets_payload": presets_payload,
            "trigger_labels": automations_service.TRIGGER_LABELS,
            "action_labels": automations_service.ACTION_LABELS,
            "button_scopes": automations_service.BUTTON_SCOPES,
            "template_variables": automations_service.TEMPLATE_VARIABLES,
            "item_fields": automations_service.ITEM_FIELDS,
        },
    )


@router.post("/automations/{rule_id}/edit")
async def automations_update(
    request: Request,
    rule_id: int,
    title: str = Form(...),
    trigger_type: str = Form(...),
    actions_json: str | None = Form(None),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    logger.info("Adminbot automation update: request", extra={"rule_id": rule_id})
    rule = db.get(BotAutomationRule, rule_id)
    if not rule:
        logger.info("Adminbot automation update: rule not found", extra={"rule_id": rule_id})
        return TEMPLATES.TemplateResponse(
            "adminbot_automation_edit.html",
            {
                "request": request,
                "user": user,
                "rule": None,
                "error": "Правило не найдено",
                "form": None,
                "missing_rule": True,
                "presets": [],
                "presets_payload": [],
                "trigger_labels": automations_service.TRIGGER_LABELS,
                "action_labels": automations_service.ACTION_LABELS,
                "button_scopes": automations_service.BUTTON_SCOPES,
                "template_variables": automations_service.TEMPLATE_VARIABLES,
                "item_fields": automations_service.ITEM_FIELDS,
            },
            status_code=404,
        )

    title_value = title.strip()
    trigger_value = trigger_type.strip().upper()
    if not title_value:
        error = "Введите название правила"
    elif trigger_value not in automations_service.TRIGGER_LABELS:
        error = "Выберите корректный триггер"
    else:
        error = None

    presets = db.query(BotButtonPreset).order_by(BotButtonPreset.scope, BotButtonPreset.id).all()
    presets_payload = _build_presets_payload(presets)
    presets_map = {int(preset.id): preset for preset in presets}

    actions_error, actions_list = _normalize_actions(actions_json)
    if not error:
        error = actions_error
    if not error:
        error, actions_list = _validate_actions(actions_list, presets_map)

    if error:
        logger.info(
            "Adminbot automation update: validation error",
            extra={"rule_id": rule_id, "error": error},
        )
        return TEMPLATES.TemplateResponse(
            "adminbot_automation_edit.html",
            {
                "request": request,
                "user": user,
                "rule": rule,
                "error": error,
                "form": {
                    "title": title_value,
                    "trigger_type": trigger_type,
                    "actions": actions_list,
                    "is_enabled": is_enabled,
                },
                "missing_rule": False,
                "presets": presets,
                "presets_payload": presets_payload,
                "trigger_labels": automations_service.TRIGGER_LABELS,
                "action_labels": automations_service.ACTION_LABELS,
                "button_scopes": automations_service.BUTTON_SCOPES,
                "template_variables": automations_service.TEMPLATE_VARIABLES,
                "item_fields": automations_service.ITEM_FIELDS,
            },
            status_code=422,
        )

    rule.title = title_value
    rule.trigger_type = trigger_value
    rule.conditions_json = [{"type": "source", "value": "webapp"}]
    rule.actions_json = actions_list
    rule.is_enabled = bool(is_enabled)
    db.add(rule)
    db.commit()

    return RedirectResponse(url="/adminbot/automations", status_code=303)


@router.post("/automations/{rule_id}/delete")
async def automations_delete(
    request: Request, rule_id: int, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    rule = db.get(BotAutomationRule, rule_id)
    if rule:
        db.delete(rule)
        db.commit()

    return RedirectResponse(url="/adminbot/automations", status_code=303)


@router.get("/automations/button-presets")
async def button_presets_list(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    presets = db.query(BotButtonPreset).order_by(BotButtonPreset.scope, BotButtonPreset.id).all()
    return TEMPLATES.TemplateResponse(
        "adminbot_button_presets_list.html",
        {
            "request": request,
            "user": user,
            "presets": presets,
            "button_scopes": automations_service.BUTTON_SCOPES,
        },
    )


@router.get("/automations/button-presets/new")
async def button_presets_new_form(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    return TEMPLATES.TemplateResponse(
        "adminbot_button_preset_edit.html",
        {
            "request": request,
            "user": user,
            "preset": None,
            "form": None,
            "error": None,
            "button_scopes": automations_service.BUTTON_SCOPES,
        },
    )


@router.post("/automations/button-presets/new")
async def button_presets_create(
    request: Request,
    title: str = Form(...),
    scope: str = Form(...),
    buttons_json: str | None = Form(None),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    title_value = title.strip()
    scope_value = scope.strip().lower()
    if not title_value:
        error = "Введите название набора"
    elif scope_value not in automations_service.BUTTON_SCOPES:
        error = "Выберите аудиторию"
    else:
        error = None

    buttons_error, buttons_list = _normalize_buttons(buttons_json)
    if not error:
        error = buttons_error

    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_button_preset_edit.html",
            {
                "request": request,
                "user": user,
                "preset": None,
                "error": error,
                "form": {
                    "title": title_value,
                    "scope": scope_value,
                    "buttons": buttons_list,
                    "is_enabled": is_enabled,
                },
                "button_scopes": automations_service.BUTTON_SCOPES,
            },
            status_code=400,
        )

    preset = BotButtonPreset(
        title=title_value,
        scope=scope_value,
        buttons_json=buttons_list,
        is_enabled=bool(is_enabled),
    )
    db.add(preset)
    db.commit()

    return RedirectResponse(url="/adminbot/automations/button-presets", status_code=303)


@router.get("/automations/button-presets/{preset_id}/edit")
async def button_presets_edit_form(
    request: Request, preset_id: int, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    preset = db.get(BotButtonPreset, preset_id)
    if not preset:
        return RedirectResponse(url="/adminbot/automations/button-presets", status_code=303)

    return TEMPLATES.TemplateResponse(
        "adminbot_button_preset_edit.html",
        {
            "request": request,
            "user": user,
            "preset": preset,
            "form": None,
            "error": None,
            "button_scopes": automations_service.BUTTON_SCOPES,
        },
    )


@router.post("/automations/button-presets/{preset_id}/edit")
async def button_presets_update(
    request: Request,
    preset_id: int,
    title: str = Form(...),
    scope: str = Form(...),
    buttons_json: str | None = Form(None),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    preset = db.get(BotButtonPreset, preset_id)
    if not preset:
        return RedirectResponse(url="/adminbot/automations/button-presets", status_code=303)

    title_value = title.strip()
    scope_value = scope.strip().lower()
    if not title_value:
        error = "Введите название набора"
    elif scope_value not in automations_service.BUTTON_SCOPES:
        error = "Выберите аудиторию"
    else:
        error = None

    buttons_error, buttons_list = _normalize_buttons(buttons_json)
    if not error:
        error = buttons_error

    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_button_preset_edit.html",
            {
                "request": request,
                "user": user,
                "preset": preset,
                "error": error,
                "form": {
                    "title": title_value,
                    "scope": scope_value,
                    "buttons": buttons_list,
                    "is_enabled": is_enabled,
                },
                "button_scopes": automations_service.BUTTON_SCOPES,
            },
            status_code=400,
        )

    preset.title = title_value
    preset.scope = scope_value
    preset.buttons_json = buttons_list
    preset.is_enabled = bool(is_enabled)
    db.add(preset)
    db.commit()

    return RedirectResponse(url="/adminbot/automations/button-presets", status_code=303)


@router.post("/automations/button-presets/{preset_id}/delete")
async def button_presets_delete(
    request: Request, preset_id: int, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    preset = db.get(BotButtonPreset, preset_id)
    if preset:
        db.delete(preset)
        db.commit()

    return RedirectResponse(url="/adminbot/automations/button-presets", status_code=303)
