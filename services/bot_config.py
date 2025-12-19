"""Загрузка конфигурации бота (узлы/кнопки) из БД с кэшем по версии."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy.orm import selectinload

from database import get_session
from models import BotButton, BotNode, BotRuntime

logger = logging.getLogger(__name__)


@dataclass
class NodeView:
    code: str
    title: str
    message_text: str
    parse_mode: str
    image_url: str | None
    keyboard: InlineKeyboardMarkup | None


_cache: dict[str, object] = {"version": None, "nodes": {}}


def get_config_version(session=None) -> int:
    if session is None:
        with get_session() as db:
            return get_config_version(session=db)

    runtime: BotRuntime | None = session.query(BotRuntime).first()
    if not runtime:
        runtime = BotRuntime(config_version=1)
        session.add(runtime)
        session.commit()
        session.refresh(runtime)
    return runtime.config_version or 1


def _build_inline_keyboard(buttons: list[BotButton]) -> InlineKeyboardMarkup | None:
    rows: Dict[int, list[InlineKeyboardButton]] = {}
    for button in sorted(buttons, key=lambda btn: (btn.row, btn.pos, btn.id)):
        if not button.is_enabled:
            continue

        if button.type == "callback":
            inline_button = InlineKeyboardButton(text=button.title, callback_data=button.payload)
        elif button.type == "url":
            inline_button = InlineKeyboardButton(text=button.title, url=button.payload)
        elif button.type == "webapp":
            inline_button = InlineKeyboardButton(
                text=button.title, web_app=WebAppInfo(url=button.payload)
            )
        else:
            logger.warning("Неизвестный тип кнопки: %s", button.type)
            continue

        rows.setdefault(button.row or 0, []).append(inline_button)

    if not rows:
        return None

    inline_keyboard = [rows[row] for row in sorted(rows.keys())]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def _reload_cache(session, version: int) -> None:
    nodes = (
        session.query(BotNode)
        .options(selectinload(BotNode.buttons))
        .filter(BotNode.is_enabled.is_(True))
        .all()
    )
    prepared: Dict[str, NodeView] = {}
    for node in nodes:
        enabled_buttons = [btn for btn in node.buttons if btn.is_enabled]
        keyboard = _build_inline_keyboard(enabled_buttons)
        prepared[node.code] = NodeView(
            code=node.code,
            title=node.title,
            message_text=node.message_text,
            parse_mode=node.parse_mode or "HTML",
            image_url=node.image_url,
            keyboard=keyboard,
        )

    _cache["version"] = version
    _cache["nodes"] = prepared
    logger.info("Bot config cache reloaded (version=%s, nodes=%s)", version, len(prepared))


def load_node(code: str) -> Optional[NodeView]:
    with get_session() as session:
        db_version = get_config_version(session)
        if _cache.get("version") != db_version:
            _reload_cache(session, db_version)

        nodes: Dict[str, NodeView] = _cache.get("nodes", {})  # type: ignore[assignment]
        return nodes.get(code)
