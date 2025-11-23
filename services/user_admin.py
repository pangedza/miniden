from __future__ import annotations

from datetime import datetime
from typing import Any

from services import admin_notes, bans


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def set_user_ban_status(
    user_id: int, is_banned: bool, admin_id: int | None = None, reason: str | None = None
) -> None:
    if is_banned:
        bans.ban_user(user_id, reason=reason)
    else:
        bans.unban_user(user_id)


def get_user_ban_status(user_id: int) -> dict[str, Any]:
    status = bans.is_banned(user_id)
    if status.get("is_banned"):
        return {
            "is_banned": True,
            "ban_reason": status.get("reason"),
            "updated_at": status.get("banned_at"),
            "updated_by": None,
        }
    return {
        "is_banned": False,
        "ban_reason": None,
        "updated_at": None,
        "updated_by": None,
    }


def add_user_note(user_id: int, admin_id: int, note: str) -> None:
    admin_notes.add_note(user_id=user_id, admin_id=admin_id, note=note)


def get_user_notes(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return admin_notes.list_notes(user_id, limit=limit)
