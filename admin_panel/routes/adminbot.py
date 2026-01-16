"""Маршруты AdminBot."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from admin_panel.routes import auth as auth_routes
from models import (
    BotAutomationRule,
    BotButton,
    BotButtonPreset,
    BotNode,
    BotNodeAction,
    BotRuntime,
    BotTrigger,
    MenuButton,
    ProductBasket,
    ProductCourse,
)
from models.admin_user import AdminRole
from services import automations as automations_service

from . import (
    adminbot_buttons,
    adminbot_admins,
    adminbot_media,
    adminbot_logs,
    adminbot_nodes,
    adminbot_menu_buttons,
    adminbot_runtime,
    adminbot_templates,
    adminbot_triggers,
    adminbot_automations,
)

router = APIRouter(prefix="/adminbot", tags=["AdminBot"])


ALLOWED_ROLES = (
    AdminRole.superadmin,
    AdminRole.admin_bot,
    AdminRole.moderator,
    AdminRole.viewer,
)


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


def _next_from_request(request: Request) -> str:
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{request.url.path}{query}"


def _collect_integrity_issues(db: Session) -> dict:
    node_codes = {code for (code,) in db.query(BotNode.code).all() if code}
    nodes = db.query(BotNode).order_by(BotNode.code.asc()).all()
    buttons = db.query(BotButton).order_by(BotButton.id.asc()).all()
    triggers = db.query(BotTrigger).order_by(BotTrigger.id.asc()).all()
    menu_buttons = db.query(MenuButton).order_by(MenuButton.id.asc()).all()
    actions = db.query(BotNodeAction).order_by(BotNodeAction.id.asc()).all()
    presets = db.query(BotButtonPreset).order_by(BotButtonPreset.id.asc()).all()
    preset_ids = {int(preset.id) for preset in presets}
    rules = db.query(BotAutomationRule).order_by(BotAutomationRule.id.asc()).all()

    missing_node_links: list[dict] = []
    for node in nodes:
        for field_name in (
            "next_node_code",
            "next_node_code_success",
            "next_node_code_cancel",
            "next_node_code_true",
            "next_node_code_false",
        ):
            target = getattr(node, field_name, None)
            if target and target not in node_codes:
                missing_node_links.append(
                    {
                        "node_code": node.code,
                        "field": field_name,
                        "target": target,
                    }
                )

    missing_button_targets: list[dict] = []
    for button in buttons:
        target_code = (button.target_node_code or "").strip()
        if target_code and target_code not in node_codes:
            missing_button_targets.append(
                {
                    "button_id": button.id,
                    "title": button.title,
                    "node_id": button.node_id,
                    "target": target_code,
                }
            )

        payload = (button.payload or "").strip()
        if payload.startswith("OPEN_NODE:"):
            target = payload.split(":", maxsplit=1)[1]
            if target and target not in node_codes:
                missing_button_targets.append(
                    {
                        "button_id": button.id,
                        "title": button.title,
                        "node_id": button.node_id,
                        "target": target,
                    }
                )

    missing_trigger_targets = [
        {
            "trigger_id": trigger.id,
            "trigger_type": trigger.trigger_type,
            "trigger_value": trigger.trigger_value,
            "target": trigger.target_node_code,
        }
        for trigger in triggers
        if trigger.target_node_code not in node_codes
    ]

    missing_menu_targets = []
    for button in menu_buttons:
        if (button.action_type or "").lower() != "node":
            continue
        payload = (button.action_payload or "").strip()
        if payload and payload not in node_codes:
            missing_menu_targets.append(
                {
                    "menu_button_id": button.id,
                    "text": button.text,
                    "target": payload,
                }
            )

    missing_action_targets = []
    for action in actions:
        payload = action.action_payload or {}
        if not isinstance(payload, dict):
            continue
        for key in ("node_code", "target_node_code", "next_node_code"):
            value = payload.get(key)
            if isinstance(value, str) and value and value not in node_codes:
                missing_action_targets.append(
                    {
                        "action_id": action.id,
                        "node_code": action.node_code,
                        "key": key,
                        "target": value,
                    }
                )

    missing_preset_refs = []
    for rule in rules:
        for action in rule.actions_json or []:
            if not isinstance(action, dict):
                continue
            preset_id = action.get("preset_id")
            if preset_id is None:
                continue
            try:
                preset_id_int = int(preset_id)
            except (TypeError, ValueError):
                preset_id_int = None
            if preset_id_int and preset_id_int not in preset_ids:
                missing_preset_refs.append(
                    {
                        "rule_id": rule.id,
                        "rule_title": rule.title,
                        "preset_id": preset_id,
                    }
                )

    return {
        "missing_node_links": missing_node_links,
        "missing_button_targets": missing_button_targets,
        "missing_trigger_targets": missing_trigger_targets,
        "missing_menu_targets": missing_menu_targets,
        "missing_action_targets": missing_action_targets,
        "missing_preset_refs": missing_preset_refs,
    }


def _status_badge(status: str) -> dict:
    mapping = {
        "ok": {"icon": "✅", "label": "Настроено", "class": "ok"},
        "warn": {"icon": "⚠️", "label": "Частично", "class": "warn"},
        "fail": {"icon": "❌", "label": "Не настроено", "class": "fail"},
    }
    return mapping.get(status, mapping["fail"])


def _section_status(
    *, ready: bool, partial: bool = False, missing_hint: str = ""
) -> tuple[str, str]:
    if ready:
        return "ok", "Готово"
    if partial:
        return "warn", "Есть заготовки"
    return "fail", missing_hint or "Нужно настроить"


@router.get("/login")
async def login_form(request: Request):
    return await auth_routes.login_form(request, next="/adminbot")


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_session),
):
    return await auth_routes.login(
        request, username=username, password=password, next="/adminbot", db=db
    )


@router.get("/")
async def dashboard(
    request: Request, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(request.url.path)

    return TEMPLATES.TemplateResponse(
        "adminbot/dashboard.html", {"request": request, "user": user}
    )


@router.get("/builder")
async def builder_dashboard(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    runtime = db.query(BotRuntime).first()
    start_node_code = (runtime.start_node_code or "").strip() if runtime else ""
    start_node_ready = bool(start_node_code and db.query(BotNode).filter(BotNode.code == start_node_code).first())

    menu_buttons_count = db.query(MenuButton).count()
    main_menu_exists = db.query(BotNode).filter(BotNode.code == "MAIN_MENU").first()
    menu_ready = menu_buttons_count > 0
    menu_partial = bool(main_menu_exists)

    products_count = db.query(ProductBasket).count()
    courses_count = db.query(ProductCourse).count()
    catalog_ready = products_count > 0 or courses_count > 0
    catalog_partial = db.query(BotNode).filter(BotNode.code.ilike("%SHOP%")).first() is not None

    cart_ready = (
        db.query(BotAutomationRule)
        .filter(BotAutomationRule.trigger_type == automations_service.TRIGGER_WEBAPP_ORDER)
        .first()
        is not None
    )
    cart_partial = db.query(BotNode).filter(BotNode.code.ilike("%CART%")).first() is not None

    profile_ready = db.query(BotNode).filter(BotNode.code.ilike("%PROFILE%")).first() is not None
    profile_partial = db.query(BotNode).filter(BotNode.title.ilike("%профил%")).first() is not None

    feedback_ready = db.query(BotNode).filter(BotNode.title.ilike("%обратн%")).first() is not None
    feedback_partial = db.query(BotNode).filter(BotNode.title.ilike("%помощ%")).first() is not None

    help_ready = db.query(BotNode).filter(BotNode.title.ilike("%помощ%")).first() is not None
    help_partial = db.query(BotNode).filter(BotNode.title.ilike("%faq%")).first() is not None

    masterclass_ready = db.query(BotNode).filter(BotNode.title.ilike("%мастер-класс%")).first() is not None
    masterclass_partial = courses_count > 0

    automations_ready = db.query(BotAutomationRule).first() is not None

    sections = [
        {
            "title": "Старт / приветствие",
            "description": "Проверьте стартовый узел и приветствие для команды /start.",
            "status": _status_badge(_section_status(ready=start_node_ready, partial=False, missing_hint="Нет стартового узла")[0]),
            "hint": "Назначьте стартовый узел в разделе «Работа бота».",
            "url": "/adminbot/runtime",
        },
        {
            "title": "Меню",
            "description": "Кнопки Reply-меню, которые видны под полем ввода.",
            "status": _status_badge(_section_status(ready=menu_ready, partial=menu_partial, missing_hint="Нет кнопок меню")[0]),
            "hint": "Создайте Reply-кнопки и привяжите их к узлам.",
            "url": "/adminbot/menu-buttons",
        },
        {
            "title": "Каталог / витрина",
            "description": "Товары, категории и точки входа в каталог.",
            "status": _status_badge(_section_status(ready=catalog_ready, partial=catalog_partial, missing_hint="Каталог пуст")[0]),
            "hint": "Добавьте товары/мастер-классы и узлы каталога.",
            "url": "/adminsite/constructor/",
        },
        {
            "title": "Корзина / заказы",
            "description": "Оформление заказа, уведомления клиенту и админу.",
            "status": _status_badge(_section_status(ready=cart_ready, partial=cart_partial, missing_hint="Нет автоматики заказа")[0]),
            "hint": "Создайте автоматизацию обработки заказов WebApp.",
            "url": "/adminbot/automations",
        },
        {
            "title": "Профиль пользователя",
            "description": "Личные данные, история заказов, быстрые настройки.",
            "status": _status_badge(_section_status(ready=profile_ready, partial=profile_partial, missing_hint="Профиль не создан")[0]),
            "hint": "Создайте узел профиля или установите шаблон.",
            "url": "/adminbot/nodes",
        },
        {
            "title": "Обратная связь",
            "description": "Контакт с админом, сбор запросов и обращений.",
            "status": _status_badge(_section_status(ready=feedback_ready, partial=feedback_partial, missing_hint="Нет узла обратной связи")[0]),
            "hint": "Добавьте узел «Написать» или установите шаблон.",
            "url": "/adminbot/nodes",
        },
        {
            "title": "Помощь / FAQ",
            "description": "Частые вопросы, доставка, оплата, правила.",
            "status": _status_badge(_section_status(ready=help_ready, partial=help_partial, missing_hint="Нет раздела помощи")[0]),
            "hint": "Создайте узел помощи или установите шаблон.",
            "url": "/adminbot/nodes",
        },
        {
            "title": "Мастер-классы",
            "description": "Продажа и выдача доступа к мастер-классам.",
            "status": _status_badge(_section_status(ready=masterclass_ready, partial=masterclass_partial, missing_hint="Нет мастер-классов")[0]),
            "hint": "Заполните мастер-классы в каталоге.",
            "url": "/adminsite/constructor/",
        },
        {
            "title": "Автоматизации",
            "description": "Правила для заказов, уведомлений и тегов.",
            "status": _status_badge(_section_status(ready=automations_ready, partial=False, missing_hint="Нет правил")[0]),
            "hint": "Создайте правило или используйте шаблон.",
            "url": "/adminbot/automations",
        },
    ]

    return TEMPLATES.TemplateResponse(
        "adminbot_builder.html",
        {
            "request": request,
            "user": user,
            "sections": sections,
            "start_node_code": start_node_code or "—",
        },
    )


@router.get("/integrity")
async def integrity_check_page(
    request: Request, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(_next_from_request(request))

    issues = _collect_integrity_issues(db)
    total_issues = sum(len(items) for items in issues.values())

    return TEMPLATES.TemplateResponse(
        "adminbot_integrity.html",
        {
            "request": request,
            "user": user,
            "issues": issues,
            "total_issues": total_issues,
        },
    )


@router.get("/api/integrity")
async def integrity_check_api(
    request: Request, db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return {"ok": False, "error": "Authentication required"}

    issues = _collect_integrity_issues(db)
    return {"ok": True, "issues": issues}


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db_session)):
    return await auth_routes.logout(request, db)


router.include_router(adminbot_nodes.router)
router.include_router(adminbot_buttons.router)
router.include_router(adminbot_menu_buttons.router)
router.include_router(adminbot_triggers.router)
router.include_router(adminbot_runtime.router)
router.include_router(adminbot_logs.router)
router.include_router(adminbot_templates.router)
router.include_router(adminbot_admins.router)
router.include_router(adminbot_media.router)
router.include_router(adminbot_automations.router)
