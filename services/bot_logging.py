"""Безопасное логирование работы бот-сценариев в БД и в fallback-лог."""

from __future__ import annotations

import json
import logging
from typing import Any

from database import get_session
from models import BotLog
from services.bot_config import get_config_version

logger = logging.getLogger(__name__)


def _serialize_details(details: Any) -> str:
    if details is None:
        return ""
    if isinstance(details, (str, int, float)):
        return str(details)
    try:
        return json.dumps(details, ensure_ascii=False)
    except Exception:
        return str(details)


def log_bot_event(
    event_type: str,
    *,
    user_id: int | None,
    username: str | None = None,
    node_code: str | None = None,
    details: Any = None,
    config_version: int | None = None,
) -> None:
    """Записать событие в bot_logs, не ломая основной поток."""

    if not user_id:
        return

    try:
        with get_session() as session:
            version = config_version
            if version is None:
                version = get_config_version(session)

            log_row = BotLog(
                user_id=user_id,
                username=username,
                event_type=event_type,
                node_code=node_code,
                details=_serialize_details(details),
                config_version=version or 1,
            )
            session.add(log_row)
    except Exception as exc:  # pragma: no cover - безопасность
        logger.warning(
            "Не удалось записать событие %s для пользователя %s: %s",
            event_type,
            user_id,
            exc,
        )


def log_trigger_event(
    *,
    user_id: int,
    username: str | None,
    trigger_type: str,
    trigger_value: str | None,
    target_node: str | None,
) -> None:
    details = {
        "trigger_type": trigger_type,
        "trigger_value": trigger_value,
        "target_node": target_node,
    }
    log_bot_event(
        "TRIGGER",
        user_id=user_id,
        username=username,
        node_code=target_node,
        details=details,
    )


def log_node_event(*, user_id: int, username: str | None, node_code: str) -> None:
    log_bot_event(
        "NODE_ENTER",
        user_id=user_id,
        username=username,
        node_code=node_code,
    )


def log_action_event(
    *,
    user_id: int,
    username: str | None,
    node_code: str,
    action_type: str,
    payload: Any,
) -> None:
    details = {"action_type": action_type, "payload": payload}
    log_bot_event(
        "ACTION",
        user_id=user_id,
        username=username,
        node_code=node_code,
        details=details,
    )


def log_error_event(
    *,
    user_id: int | None,
    username: str | None,
    node_code: str | None,
    details: Any,
) -> None:
    log_bot_event(
        "ERROR",
        user_id=user_id,
        username=username,
        node_code=node_code,
        details=details,
    )
