"""Загрузка конфигурации бота (узлы/кнопки) из БД с кэшем по версии."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy.orm import selectinload

from database import get_session
from models import BotButton, BotNode, BotNodeAction, BotRuntime, BotTrigger

logger = logging.getLogger(__name__)


@dataclass
class NodeView:
    code: str
    title: str
    message_text: str
    parse_mode: str
    image_url: str | None
    keyboard: InlineKeyboardMarkup | None
    node_type: str
    input_type: str | None
    input_var_key: str | None
    input_required: bool
    input_min_len: int | None
    input_error_text: str | None
    next_node_code_success: str | None
    next_node_code_cancel: str | None
    cond_var_key: str | None
    cond_operator: str | None
    cond_value: str | None
    next_node_code_true: str | None
    next_node_code_false: str | None
    next_node_code: str | None
    actions: list["NodeActionView"]
    condition_type: str | None
    condition_payload: dict | None
    config_json: dict | None


@dataclass
class NodeActionView:
    action_type: str
    payload: dict
    sort_order: int
    is_enabled: bool


@dataclass
class BotTriggerView:
    id: int
    trigger_type: str
    trigger_value: str | None
    match_mode: str
    target_node_code: str
    priority: int
    is_enabled: bool


_cache: dict[str, object] = {
    "version": None,
    "nodes": {},
    "triggers": [],
    "start_node_code": None,
}


def _get_runtime(session) -> BotRuntime:
    runtime: BotRuntime | None = session.query(BotRuntime).first()
    if not runtime:
        runtime = BotRuntime(config_version=1, start_node_code="MAIN_MENU")
        session.add(runtime)
        session.commit()
        session.refresh(runtime)
    return runtime


def get_config_version(session=None) -> int:
    if session is None:
        with get_session() as db:
            return get_config_version(session=db)

    runtime = _get_runtime(session)
    return runtime.config_version or 1


def _resolve_button_action(button: BotButton) -> InlineKeyboardButton | None:
    action_type = (button.action_type or "NODE").upper()
    if action_type == "NODE":
        target_code = button.target_node_code
        if not target_code and button.type == "callback" and (
            button.payload or ""
        ).startswith("OPEN_NODE:"):
            target_code = (button.payload or "OPEN_NODE:").split(":", maxsplit=1)[1]
        if target_code:
            payload = f"OPEN_NODE:{target_code}"
            return InlineKeyboardButton(text=button.title, callback_data=payload)
        if button.type == "callback" and button.payload:
            # Старый формат callback с произвольным payload
            return InlineKeyboardButton(text=button.title, callback_data=button.payload)
        logger.warning("Не указан узел для кнопки %s", button.id)
        return None

    if action_type == "URL":
        target_url = button.url or button.payload
        if not target_url:
            logger.warning("Не указана ссылка для кнопки %s", button.id)
            return None
        return InlineKeyboardButton(text=button.title, url=target_url)

    if action_type == "WEBAPP":
        webapp_url = button.webapp_url or button.payload
        if not webapp_url:
            logger.warning("Не указана WebApp ссылка для кнопки %s", button.id)
            return None
        return InlineKeyboardButton(text=button.title, web_app=WebAppInfo(url=webapp_url))

    # Совместимость со старыми кнопками
    if button.type == "callback":
        return InlineKeyboardButton(text=button.title, callback_data=button.payload)
    if button.type == "url":
        return InlineKeyboardButton(text=button.title, url=button.payload)
    if button.type == "webapp":
        return InlineKeyboardButton(text=button.title, web_app=WebAppInfo(url=button.payload))

    logger.warning("Неизвестный тип кнопки: %s", button.type)
    return None


def _build_inline_keyboard(buttons: list[BotButton]) -> InlineKeyboardMarkup | None:
    rows: Dict[int, list[InlineKeyboardButton]] = {}
    for button in sorted(buttons, key=lambda btn: (btn.row, btn.pos, btn.id)):
        if not button.is_enabled:
            continue

        inline_button = _resolve_button_action(button)
        if not inline_button:
            continue

        rows.setdefault(button.row or 0, []).append(inline_button)

    if not rows:
        return None

    inline_keyboard = [rows[row] for row in sorted(rows.keys())]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _reload_cache(session, version: int, start_node_code: str | None) -> None:
    nodes = (
        session.query(BotNode)
        .options(selectinload(BotNode.buttons))
        .filter(BotNode.is_enabled.is_(True))
        .all()
    )
    actions = (
        session.query(BotNodeAction)
        .filter(BotNodeAction.is_enabled.is_(True))
        .order_by(BotNodeAction.node_code, BotNodeAction.sort_order, BotNodeAction.id)
        .all()
    )
    actions_map: dict[str, list[NodeActionView]] = {}
    for action in actions:
        actions_map.setdefault(action.node_code, []).append(
            NodeActionView(
                action_type=action.action_type,
                payload=action.action_payload or {},
                sort_order=action.sort_order or 0,
                is_enabled=bool(action.is_enabled),
            )
        )
    prepared: Dict[str, NodeView] = {}
    for node in nodes:
        enabled_buttons = [btn for btn in node.buttons if btn.is_enabled]
        keyboard = _build_inline_keyboard(enabled_buttons)
        config_json: dict | None = node.config_json if isinstance(node.config_json, dict) else None
        prepared[node.code] = NodeView(
            code=node.code,
            title=node.title,
            message_text=node.message_text,
            parse_mode=node.parse_mode or "HTML",
            image_url=node.image_url,
            keyboard=keyboard,
            node_type=node.node_type or "MESSAGE",
            input_type=node.input_type,
            input_var_key=node.input_var_key,
            input_required=bool(node.input_required),
            input_min_len=node.input_min_len,
            input_error_text=node.input_error_text,
            next_node_code_success=node.next_node_code_success,
            next_node_code_cancel=node.next_node_code_cancel,
            cond_var_key=node.cond_var_key,
            cond_operator=node.cond_operator,
            cond_value=node.cond_value,
            next_node_code_true=node.next_node_code_true,
            next_node_code_false=node.next_node_code_false,
            next_node_code=node.next_node_code,
            actions=actions_map.get(node.code, []),
            condition_type=(config_json or {}).get("condition_type"),
            condition_payload=(config_json or {}).get("condition_payload"),
            config_json=config_json,
        )

    triggers = (
        session.query(BotTrigger)
        .filter(BotTrigger.is_enabled.is_(True))
        .order_by(BotTrigger.trigger_type, BotTrigger.priority, BotTrigger.id)
        .all()
    )
    type_order = {"COMMAND": 0, "TEXT": 1, "FALLBACK": 2}
    prepared_triggers = [
        BotTriggerView(
            id=trigger.id,
            trigger_type=trigger.trigger_type or "",
            trigger_value=trigger.trigger_value,
            match_mode=trigger.match_mode or "EXACT",
            target_node_code=trigger.target_node_code or "",
            priority=trigger.priority or 100,
            is_enabled=bool(trigger.is_enabled),
        )
        for trigger in sorted(
            triggers,
            key=lambda t: (type_order.get((t.trigger_type or "").upper(), 99), t.priority or 0, t.id),
        )
    ]

    _cache["version"] = version
    _cache["nodes"] = prepared
    _cache["triggers"] = prepared_triggers
    _cache["start_node_code"] = start_node_code
    logger.info(
        "Bot config cache reloaded (version=%s, nodes=%s, triggers=%s)",
        version,
        len(prepared),
        len(prepared_triggers),
    )


def load_node(code: str) -> Optional[NodeView]:
    with get_session() as session:
        runtime = _get_runtime(session)
        if _cache.get("version") != runtime.config_version:
            _reload_cache(session, runtime.config_version, runtime.start_node_code)

        nodes: Dict[str, NodeView] = _cache.get("nodes", {})  # type: ignore[assignment]
        return nodes.get(code)


def load_triggers() -> list[BotTriggerView]:
    with get_session() as session:
        runtime = _get_runtime(session)
        if _cache.get("version") != runtime.config_version:
            _reload_cache(session, runtime.config_version, runtime.start_node_code)

        return list(_cache.get("triggers", []))  # type: ignore[list-item]


def get_start_node_code() -> str:
    with get_session() as session:
        runtime = _get_runtime(session)
        if _cache.get("version") != runtime.config_version:
            _reload_cache(session, runtime.config_version, runtime.start_node_code)

        cached_start_node = _cache.get("start_node_code") or runtime.start_node_code
        return (cached_start_node or "MAIN_MENU").strip() or "MAIN_MENU"
