from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import select

from database import get_session
from models import AdminNote


def add_note(user_id: int, note: str, admin_id: int | None = None) -> AdminNote:
    with get_session() as session:
        record = AdminNote(
            user_id=user_id,
            admin_id=admin_id,
            note=note,
            created_at=datetime.utcnow(),
        )
        session.add(record)
        session.flush()
        session.refresh(record)
        return record


def list_notes(user_id: int, limit: int = 20) -> list[dict]:
    with get_session() as session:
        rows: List[AdminNote] = session.scalars(
            select(AdminNote)
            .where(AdminNote.user_id == user_id)
            .order_by(AdminNote.created_at.desc(), AdminNote.id.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "admin_id": row.admin_id,
                "note": row.note,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


def delete_note(note_id: int) -> bool:
    with get_session() as session:
        record = session.get(AdminNote, note_id)
        if not record:
            return False
        session.delete(record)
        return True
