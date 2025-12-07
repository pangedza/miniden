from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from database import get_session
from models import ProductReview, User
from services import products as products_service
from services import users as users_service

REVIEW_STATUSES = {"pending", "approved", "rejected"}


def _serialize_review(review: ProductReview, user_map: dict[int, User]) -> dict[str, Any]:
    user = user_map.get(int(review.user_id)) if review.user_id is not None else None
    user_name = None
    if user:
        if user.first_name and user.last_name:
            user_name = f"{user.first_name} {user.last_name}".strip()
        else:
            user_name = user.first_name or user.username

    return {
        "id": int(review.id),
        "product_id": int(review.product_id) if review.product_id is not None else None,
        "masterclass_id": int(review.masterclass_id) if review.masterclass_id is not None else None,
        "user_id": int(review.user_id) if review.user_id is not None else None,
        "user_name": user_name,
        "rating": int(review.rating),
        "text": review.text,
        "photos": review.photos_json or [],
        "status": review.status,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        "is_deleted": bool(review.is_deleted),
    }


def _load_users(session, user_ids: set[int]) -> dict[int, User]:
    if not user_ids:
        return {}
    rows = session.scalars(select(User).where(User.telegram_id.in_(user_ids))).all()
    return {int(user.telegram_id): user for user in rows if user.telegram_id is not None}


def _normalize_pagination(page: int, limit: int) -> tuple[int, int]:
    current_page = max(page, 1)
    current_limit = max(min(limit, 100), 1)
    offset = (current_page - 1) * current_limit
    return offset, current_limit


def get_review_by_id(review_id: int) -> ProductReview | None:
    with get_session() as session:
        return session.get(ProductReview, review_id)


def create_review(
    product_id: int | None,
    user: User,
    rating: int,
    text: str,
    photos: list[str] | None = None,
    order_id: int | None = None,
    *,
    masterclass_id: int | None = None,
) -> int:
    if rating < 1 or rating > 5:
        raise ValueError("rating must be between 1 and 5")

    if product_id is None and masterclass_id is None:
        raise ValueError("target_required")
    if product_id is not None and masterclass_id is not None:
        raise ValueError("multiple_targets")

    if product_id is not None:
        product = products_service.get_basket_by_id(product_id)
        if not product or not product.get("is_active", True):
            raise ValueError("product_not_found")
    if masterclass_id is not None:
        masterclass = products_service.get_course_by_id(masterclass_id)
        if not masterclass or not masterclass.get("is_active", True):
            raise ValueError("masterclass_not_found")

    users_service.get_or_create_user_from_telegram({"id": user.telegram_id})

    with get_session() as session:
        review = ProductReview(
            product_id=product_id,
            masterclass_id=masterclass_id,
            user_id=int(user.telegram_id),
            order_id=order_id,
            rating=int(rating),
            text=text,
            photos_json=list(photos) if photos else None,
            status="pending",
        )
        session.add(review)
        session.flush()
        return int(review.id)


def create_masterclass_review(
    masterclass_id: int,
    user: User,
    rating: int,
    text: str,
    photos: list[str] | None = None,
    order_id: int | None = None,
) -> int:
    return create_review(
        None,
        user,
        rating,
        text,
        photos,
        order_id,
        masterclass_id=masterclass_id,
    )


def get_reviews_for_product(
    product_id: int,
    *,
    status: str | None = "approved",
    page: int = 1,
    limit: int = 20,
) -> list[dict[str, Any]]:
    offset, current_limit = _normalize_pagination(page, limit)

    with get_session() as session:
        query = select(ProductReview).where(
            ProductReview.product_id == product_id,
            ProductReview.masterclass_id.is_(None),
            ProductReview.is_deleted.is_(False),
        )
        if status:
            query = query.where(ProductReview.status == status)

        rows = (
            session.scalars(
                query.order_by(ProductReview.created_at.desc()).offset(offset).limit(current_limit)
            )
            .unique()
            .all()
        )

        user_ids = {int(row.user_id) for row in rows if row.user_id is not None}
        user_map = _load_users(session, user_ids)

        return [_serialize_review(row, user_map) for row in rows]


def get_reviews_for_masterclass(
    masterclass_id: int,
    *,
    status: str | None = "approved",
    page: int = 1,
    limit: int = 20,
) -> list[dict[str, Any]]:
    offset, current_limit = _normalize_pagination(page, limit)

    with get_session() as session:
        query = select(ProductReview).where(
            ProductReview.masterclass_id == masterclass_id,
            ProductReview.is_deleted.is_(False),
        )
        if status:
            query = query.where(ProductReview.status == status)

        rows = (
            session.scalars(
                query.order_by(ProductReview.created_at.desc()).offset(offset).limit(current_limit)
            )
            .unique()
            .all()
        )

        user_ids = {int(row.user_id) for row in rows if row.user_id is not None}
        user_map = _load_users(session, user_ids)

        return [_serialize_review(row, user_map) for row in rows]


def admin_list_reviews(
    *,
    status: str | None = None,
    product_id: int | None = None,
    masterclass_id: int | None = None,
    user_id: int | None = None,
    page: int = 1,
    limit: int = 50,
) -> list[dict[str, Any]]:
    offset, current_limit = _normalize_pagination(page, limit)

    with get_session() as session:
        query = select(ProductReview)
        if status:
            query = query.where(ProductReview.status == status)
        if product_id is not None:
            query = query.where(ProductReview.product_id == product_id)
        if masterclass_id is not None:
            query = query.where(ProductReview.masterclass_id == masterclass_id)
        if user_id is not None:
            query = query.where(ProductReview.user_id == user_id)

        rows = (
            session.scalars(
                query.order_by(ProductReview.created_at.desc()).offset(offset).limit(current_limit)
            )
            .unique()
            .all()
        )

        user_ids = {int(row.user_id) for row in rows if row.user_id is not None}
        user_map = _load_users(session, user_ids)

        product_cache: dict[int, dict[str, Any] | None] = {}
        serialized: list[dict[str, Any]] = []
        for row in rows:
            target_id = row.product_id or row.masterclass_id
            product_meta = None
            if target_id is not None:
                cache_key = int(target_id)
                product_meta = product_cache.get(cache_key)
                if product_meta is None:
                    if row.masterclass_id is not None:
                        product_meta = products_service.get_course_by_id(cache_key, include_inactive=True)
                    else:
                        product_meta = products_service.get_product_by_id(
                            cache_key, include_inactive=True
                        )
                    product_cache[cache_key] = product_meta

            serialized.append({
                **_serialize_review(row, user_map),
                "product": product_meta,
            })
        return serialized


def admin_update_review_status(
    review_id: int, *, new_status: str, is_deleted: bool | None = None
) -> ProductReview | None:
    if new_status not in REVIEW_STATUSES:
        raise ValueError("Invalid status")

    with get_session() as session:
        review = session.get(ProductReview, review_id)
        if not review:
            return None

        review.status = new_status
        if is_deleted is not None:
            review.is_deleted = bool(is_deleted)

        session.add(review)
        session.flush()
        session.refresh(review)
        return review


def _generate_review_photo_path(media_root: Path, review_id: int, filename: str) -> Path:
    review_dir = media_root / "reviews" / str(review_id)
    review_dir.mkdir(parents=True, exist_ok=True)
    ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    return review_dir / f"{review_id}_{ProductReview.__tablename__}_{len(list(review_dir.iterdir())) + 1}.{ext}"


def add_review_photo(review_id: int, file, media_root: Path) -> list[str]:
    files = []
    if isinstance(file, (list, tuple)):
        files = [f for f in file if f is not None]
    elif file is not None:
        files = [file]

    if not files:
        raise ValueError("Неверный формат изображения")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}

    with get_session() as session:
        review = session.get(ProductReview, review_id)
        if not review or review.is_deleted:
            raise ValueError("review_not_found")

        existing = list(review.photos_json or [])
        remaining_slots = max(0, 3 - len(existing))

        for upload in files:
            if remaining_slots <= 0:
                break

            content_type = getattr(upload, "content_type", None) or mimetypes.guess_type(upload.filename or "")[0]
            if content_type not in allowed_types:
                raise ValueError("Неверный формат изображения")

            filename = upload.filename or "image.jpg"
            full_path = _generate_review_photo_path(media_root, review_id, filename)

            with full_path.open("wb") as f:
                f.write(upload.file.read())

            relative = full_path.relative_to(media_root).as_posix()
            url = f"/media/{relative}"
            existing.append(url)
            remaining_slots -= 1

        review.photos_json = existing
        session.add(review)
        session.flush()
        session.refresh(review)
        return review.photos_json or []


def get_rating_summary(product_id: int, *, status: str = "approved") -> dict[str, Any]:
    with get_session() as session:
        query = select(
            func.coalesce(func.avg(ProductReview.rating), 0),
            func.count(ProductReview.id),
        ).where(
            ProductReview.product_id == product_id,
            ProductReview.masterclass_id.is_(None),
            ProductReview.is_deleted.is_(False),
        )
        if status:
            query = query.where(ProductReview.status == status)

        avg_rating, total = session.execute(query).one()
        return {"average_rating": float(avg_rating or 0), "reviews_count": int(total or 0)}
