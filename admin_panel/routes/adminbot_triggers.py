from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models import BotTrigger
from models.admin_user import AdminRole

router = APIRouter(tags=["AdminBot"])

ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot)
TRIGGER_TYPES = {
    "COMMAND": "Команда (например /start)",
    "TEXT": "Текст (сообщение пользователя)",
    "FALLBACK": "По умолчанию (если ничего не подошло)",
}
MATCH_MODES = {
    "EXACT": "Точно равно",
    "CONTAINS": "Содержит",
    "STARTS_WITH": "Начинается с",
}


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _validate_trigger_payload(
    *,
    trigger_type: str,
    trigger_value: str | None,
    match_mode: str | None,
    target_node_code: str,
    priority: int,
    is_enabled: bool,
) -> tuple[str | None, dict]:
    normalized_type = (trigger_type or "").strip().upper()
    normalized_value = (trigger_value or "").strip()
    normalized_mode = (match_mode or "EXACT").strip().upper() or "EXACT"
    normalized_target = (target_node_code or "").strip()
    normalized_priority = priority if isinstance(priority, int) else 100

    if normalized_type not in TRIGGER_TYPES:
        return "Некорректный тип триггера", {}

    if normalized_type == "COMMAND":
        if not normalized_value:
            return "Для команды укажите значение без символа '/'", {}
        if " " in normalized_value or normalized_value.startswith("/"):
            return "Команда не должна содержать пробелы и символ '/'", {}
    elif normalized_type == "TEXT":
        if not normalized_value:
            return "Для текстового триггера укажите значение", {}
        if normalized_mode not in MATCH_MODES:
            return "Выберите режим совпадения", {}
    elif normalized_type == "FALLBACK":
        if normalized_value:
            return "Для триггера по умолчанию значение должно быть пустым", {}
        normalized_value = None
        normalized_mode = "EXACT"

    if not normalized_target:
        return "Укажите код узла назначения", {}

    payload = {
        "trigger_type": normalized_type,
        "trigger_value": normalized_value,
        "match_mode": normalized_mode if normalized_type == "TEXT" else "EXACT",
        "target_node_code": normalized_target,
        "priority": normalized_priority,
        "is_enabled": bool(is_enabled),
    }

    return None, payload


def _ensure_single_fallback(db: Session, *, current_id: int | None, is_enabled: bool) -> str | None:
    if not is_enabled:
        return None

    existing = (
        db.query(BotTrigger)
        .filter(BotTrigger.trigger_type == "FALLBACK", BotTrigger.is_enabled.is_(True))
        .filter(BotTrigger.id != (current_id or 0))
        .first()
    )
    if existing:
        return "Разрешён только один включённый триггер по умолчанию"
    return None


@router.get("/triggers")
async def list_triggers(
    request: Request,
    trigger_type: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    query = db.query(BotTrigger)
    if trigger_type:
        query = query.filter(BotTrigger.trigger_type == trigger_type.upper())
    if search:
        query = query.filter(BotTrigger.trigger_value.ilike(f"%{search.strip()}%"))

    triggers = query.order_by(BotTrigger.trigger_type, BotTrigger.priority, BotTrigger.id).all()

    return TEMPLATES.TemplateResponse(
        "adminbot_triggers_list.html",
        {
            "request": request,
            "user": user,
            "triggers": triggers,
            "selected_type": trigger_type or "",
            "search": search or "",
            "trigger_types": TRIGGER_TYPES,
            "match_modes": MATCH_MODES,
        },
    )


@router.get("/triggers/new")
async def new_trigger_form(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    return TEMPLATES.TemplateResponse(
        "adminbot_trigger_edit.html",
        {
            "request": request,
            "user": user,
            "trigger": None,
            "trigger_types": TRIGGER_TYPES,
            "match_modes": MATCH_MODES,
            "form": None,
            "error": None,
        },
    )


@router.post("/triggers/new")
async def create_trigger(
    request: Request,
    trigger_type: str = Form(...),
    trigger_value: str | None = Form(None),
    match_mode: str | None = Form("EXACT"),
    target_node_code: str = Form(...),
    priority: int = Form(100),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    try:
        priority_value = int(priority)
    except Exception:
        priority_value = 100

    error, payload = _validate_trigger_payload(
        trigger_type=trigger_type,
        trigger_value=trigger_value,
        match_mode=match_mode,
        target_node_code=target_node_code,
        priority=priority_value,
        is_enabled=is_enabled,
    )
    if not error:
        error = _ensure_single_fallback(
            db, current_id=None, is_enabled=is_enabled and (trigger_type or "").upper() == "FALLBACK"
        )

    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_trigger_edit.html",
            {
                "request": request,
                "user": user,
                "trigger": None,
                "trigger_types": TRIGGER_TYPES,
                "match_modes": MATCH_MODES,
                "error": error,
                "form": {
                    "trigger_type": trigger_type,
                    "trigger_value": trigger_value,
                    "match_mode": match_mode,
                    "target_node_code": target_node_code,
                    "priority": priority_value,
                    "is_enabled": is_enabled,
                },
            },
            status_code=400,
        )

    db.add(BotTrigger(**payload))
    db.commit()

    return RedirectResponse(url="/adminbot/triggers", status_code=303)


@router.get("/triggers/{trigger_id}/edit")
async def edit_trigger_form(
    request: Request,
    trigger_id: int,
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    trigger = db.get(BotTrigger, trigger_id)
    if not trigger:
        return RedirectResponse(url="/adminbot/triggers", status_code=303)

    return TEMPLATES.TemplateResponse(
        "adminbot_trigger_edit.html",
        {
            "request": request,
            "user": user,
            "trigger": trigger,
            "trigger_types": TRIGGER_TYPES,
            "match_modes": MATCH_MODES,
            "form": None,
            "error": None,
        },
    )


@router.post("/triggers/{trigger_id}/edit")
async def update_trigger(
    request: Request,
    trigger_id: int,
    trigger_type: str = Form(...),
    trigger_value: str | None = Form(None),
    match_mode: str | None = Form("EXACT"),
    target_node_code: str = Form(...),
    priority: int = Form(100),
    is_enabled: bool = Form(False),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    trigger = db.get(BotTrigger, trigger_id)
    if not trigger:
        return RedirectResponse(url="/adminbot/triggers", status_code=303)

    try:
        priority_value = int(priority)
    except Exception:
        priority_value = 100

    error, payload = _validate_trigger_payload(
        trigger_type=trigger_type,
        trigger_value=trigger_value,
        match_mode=match_mode,
        target_node_code=target_node_code,
        priority=priority_value,
        is_enabled=is_enabled,
    )
    if not error:
        error = _ensure_single_fallback(
            db, current_id=trigger.id, is_enabled=is_enabled and (trigger_type or "").upper() == "FALLBACK"
        )

    if error:
        return TEMPLATES.TemplateResponse(
            "adminbot_trigger_edit.html",
            {
                "request": request,
                "user": user,
                "trigger": trigger,
                "trigger_types": TRIGGER_TYPES,
                "match_modes": MATCH_MODES,
                "error": error,
                "form": {
                    "trigger_type": trigger_type,
                    "trigger_value": trigger_value,
                    "match_mode": match_mode,
                    "target_node_code": target_node_code,
                    "priority": priority_value,
                    "is_enabled": is_enabled,
                },
            },
            status_code=400,
        )

    for key, value in payload.items():
        setattr(trigger, key, value)
    db.add(trigger)
    db.commit()

    return RedirectResponse(url="/adminbot/triggers", status_code=303)


@router.post("/triggers/{trigger_id}/delete")
async def delete_trigger(request: Request, trigger_id: int, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    trigger = db.get(BotTrigger, trigger_id)
    if trigger:
        db.delete(trigger)
        db.commit()

    return RedirectResponse(url="/adminbot/triggers", status_code=303)
