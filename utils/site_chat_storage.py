"""Lightweight storage for mapping admin messages to support sessions."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

STORAGE_PATH = Path(__file__).resolve().parent.parent / "data" / "site_chat_sessions.json"
MAX_RECORDS = 500


def _load_storage() -> Dict[str, int]:
    try:
        if not STORAGE_PATH.exists():
            return {}
        with STORAGE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return {str(k): int(v) for k, v in data.items()}
    except Exception:
        logging.exception("Failed to load site chat storage")
        return {}


def _save_storage(data: Dict[str, int]) -> None:
    try:
        STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with STORAGE_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        logging.exception("Failed to persist site chat storage")


def remember_admin_message(message_id: int, session_id: int) -> None:
    storage = _load_storage()
    storage[str(message_id)] = int(session_id)
    if len(storage) > MAX_RECORDS:
        sorted_items = sorted(storage.items(), key=lambda item: int(item[0]))
        storage = dict(sorted_items[-MAX_RECORDS:])
    _save_storage(storage)


def get_session_id_for_message(message_id: int) -> int | None:
    storage = _load_storage()
    try:
        return int(storage.get(str(message_id))) if storage.get(str(message_id)) is not None else None
    except (TypeError, ValueError):
        return None
