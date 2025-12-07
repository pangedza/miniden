from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from database import get_session
from models import FaqItem


def _ensure_sort_order(value: int | None) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _apply_updates(record: FaqItem, data: dict) -> None:
    for field in ("category", "question", "answer", "sort_order"):
        if field not in data:
            continue
        if field == "sort_order":
            setattr(record, field, _ensure_sort_order(data.get(field)))
        else:
            value = data.get(field)
            if value is not None:
                setattr(record, field, value)


def _serialize(item: FaqItem) -> dict:
    return {
        "id": int(item.id),
        "category": item.category,
        "question": item.question,
        "answer": item.answer,
        "sort_order": int(item.sort_order or 0),
    }


def serialize_many(items: Iterable[FaqItem]) -> list[dict]:
    return [_serialize(item) for item in items]


def get_faq_list(category: str | None = None) -> list[FaqItem]:
    with get_session() as session:
        query = select(FaqItem).order_by(FaqItem.sort_order, FaqItem.id)
        if category:
            query = query.where(FaqItem.category == category)
        return session.scalars(query).all()


def get_faq_item(faq_id: int) -> FaqItem | None:
    with get_session() as session:
        return session.get(FaqItem, faq_id)


def create_faq_item(data: dict) -> FaqItem:
    with get_session() as session:
        record = FaqItem(
            category=data.get("category"),
            question=data.get("question"),
            answer=data.get("answer"),
            sort_order=_ensure_sort_order(data.get("sort_order")),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(record)
        session.flush()
        session.refresh(record)
        return record


def update_faq_item(faq_id: int, data: dict) -> FaqItem | None:
    with get_session() as session:
        record = session.get(FaqItem, faq_id)
        if not record:
            return None
        _apply_updates(record, data)
        session.flush()
        session.refresh(record)
        return record


def delete_faq_item(faq_id: int) -> bool:
    with get_session() as session:
        record = session.get(FaqItem, faq_id)
        if not record:
            return False
        session.delete(record)
        return True
