from __future__ import annotations

from datetime import datetime
from typing import Any

from database import get_connection


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def set_user_ban_status(
    user_id: int, is_banned: bool, admin_id: int | None = None, reason: str | None = None
) -> None:
    """Создать или обновить статус бана пользователя."""

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO user_status (user_id, is_banned, ban_reason, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            is_banned = excluded.is_banned,
            ban_reason = excluded.ban_reason,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by;
        """,
        (user_id, int(is_banned), reason, _now_iso(), admin_id),
    )

    conn.commit()
    conn.close()


def get_user_ban_status(user_id: int) -> dict[str, Any]:
    """Получить статус бана пользователя. Если записи нет, считаем, что он активен."""

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id, is_banned, ban_reason, updated_at, updated_by
        FROM user_status
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "is_banned": False,
            "ban_reason": None,
            "updated_at": None,
            "updated_by": None,
        }

    return {
        "is_banned": bool(row["is_banned"]),
        "ban_reason": row["ban_reason"],
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by"],
    }


def add_user_note(user_id: int, admin_id: int, note: str) -> None:
    """Добавить заметку по пользователю."""

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO user_notes (user_id, admin_id, note, created_at)
        VALUES (?, ?, ?, ?);
        """,
        (user_id, admin_id, note, _now_iso()),
    )
    conn.commit()
    conn.close()


def get_user_notes(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """Получить заметки по пользователю, отсортированные по времени создания (DESC)."""

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, admin_id, note, created_at
        FROM user_notes
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )

    notes = [dict(row) for row in cur.fetchall()]
    conn.close()
    return notes
