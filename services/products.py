from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy import func, select

from database import get_session, init_db
from models import ProductBasket, ProductCourse

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BASKETS_JSON = DATA_DIR / "products_baskets.json"
COURSES_JSON = DATA_DIR / "products_courses.json"


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    return [item for item in data if isinstance(item, dict)]


def _seed_products() -> None:
    init_db()
    baskets = _load_json(BASKETS_JSON)
    courses = _load_json(COURSES_JSON)

    with get_session() as session:
        baskets_count = session.scalar(select(func.count()).select_from(ProductBasket))
        courses_count = session.scalar(select(func.count()).select_from(ProductCourse))

        if baskets_count == 0:
            for item in baskets:
                session.add(
                    ProductBasket(
                        id=item.get("id"),
                        title=item.get("name") or "",
                        description=item.get("description"),
                        price=item.get("price", 0),
                        detail_url=item.get("detail_url"),
                        is_active=1,
                    )
                )

        if courses_count == 0:
            for item in courses:
                session.add(
                    ProductCourse(
                        id=item.get("id"),
                        title=item.get("name") or "",
                        description=item.get("description"),
                        price=item.get("price", 0),
                        detail_url=item.get("detail_url"),
                        is_active=1,
                    )
                )


def _serialize_product(product: ProductBasket | ProductCourse, product_type: str) -> dict[str, Any]:
    return {
        "id": product.id,
        "type": product_type,
        "name": product.name,
        "price": int(product.price or 0),
        "description": product.description or "",
        "detail_url": getattr(product, "detail_url", None),
        "image_file_id": getattr(product, "image", None),
        "is_active": int(getattr(product, "is_active", 1) or 0),
    }


def _fetch_all(model: type[ProductBasket] | type[ProductCourse], product_type: str) -> list[dict[str, Any]]:
    _seed_products()
    with get_session() as session:
        rows = session.scalars(select(model).order_by(model.id)).all()
        return [_serialize_product(row, product_type) for row in rows]


def get_baskets() -> list[dict[str, Any]]:
    return [p for p in _fetch_all(ProductBasket, "basket") if p["is_active"] == 1]


def get_courses() -> list[dict[str, Any]]:
    return [p for p in _fetch_all(ProductCourse, "course") if p["is_active"] == 1]


def _fetch_by_id(model: type[ProductBasket] | type[ProductCourse], item_id: int) -> Optional[dict[str, Any]]:
    _seed_products()
    with get_session() as session:
        item = session.get(model, item_id)
        if not item:
            return None
        product_type = "basket" if model is ProductBasket else "course"
        return _serialize_product(item, product_type)


def get_basket_by_id(item_id: int) -> Optional[dict[str, Any]]:
    prod = _fetch_by_id(ProductBasket, item_id)
    if prod and prod["is_active"] == 1:
        return prod
    return None


def get_course_by_id(item_id: int) -> Optional[dict[str, Any]]:
    prod = _fetch_by_id(ProductCourse, item_id)
    if prod and prod["is_active"] == 1:
        return prod
    return None


def get_product_by_id(product_id: int) -> Optional[dict[str, Any]]:
    return get_basket_by_id(product_id) or get_course_by_id(product_id)


def list_products(product_type: str) -> list[dict[str, Any]]:
    if product_type == "basket":
        return get_baskets()
    if product_type == "course":
        return get_courses()
    return []


def _pick_model(product_type: str):
    if product_type == "basket":
        return ProductBasket
    if product_type == "course":
        return ProductCourse
    raise ValueError("Unknown product type")


def create_product(product_type: str, name: str, price: int, description: str = "", detail_url: str | None = None) -> int:
    model = _pick_model(product_type)
    _seed_products()
    with get_session() as session:
        instance = model(title=name, description=description, price=price, detail_url=detail_url, is_active=1)
        session.add(instance)
        session.flush()
        return int(instance.id)


def update_product_name(product_id: int, name: str) -> bool:
    return _update_field(product_id, "title", name)


def update_product_price(product_id: int, price: int) -> bool:
    return _update_field(product_id, "price", price)


def update_product_description(product_id: int, description: str) -> bool:
    return _update_field(product_id, "description", description)


def update_product_detail_url(product_id: int, detail_url: str | None) -> bool:
    return _update_field(product_id, "detail_url", detail_url)


def update_product_image(product_id: int, image_file_id: str | None) -> bool:
    return _update_field(product_id, "image", image_file_id)


def toggle_product_active(product_id: int) -> bool:
    for model in (ProductBasket, ProductCourse):
        with get_session() as session:
            instance = session.get(model, product_id)
            if instance:
                instance.is_active = 0 if int(getattr(instance, "is_active", 1) or 0) == 1 else 1
                return True
    return False


def soft_delete_product(product_id: int) -> bool:
    return _update_field(product_id, "is_active", 0)


def list_products_by_status(is_active: Optional[bool] = None) -> list[dict[str, Any]]:
    _seed_products()
    results: list[dict[str, Any]] = []
    for model, product_type in ((ProductBasket, "basket"), (ProductCourse, "course")):
        with get_session() as session:
            query = select(model)
            if is_active is not None:
                query = query.where(model.is_active == (1 if is_active else 0))
            rows = session.scalars(query.order_by(model.id)).all()
            results.extend(_serialize_product(row, product_type) for row in rows)
    return results


def _update_field(product_id: int, field: str, value: Any) -> bool:
    for model in (ProductBasket, ProductCourse):
        with get_session() as session:
            instance = session.get(model, product_id)
            if instance:
                setattr(instance, field, value)
                return True
    return False


# Legacy helpers used by admin flows

def get_free_courses() -> list[dict[str, Any]]:
    return [course for course in get_courses() if int(course.get("price", 0)) == 0]


def get_paid_courses() -> list[dict[str, Any]]:
    return [course for course in get_courses() if int(course.get("price", 0)) > 0]


def get_product_with_category(product_id: int) -> Optional[dict[str, Any]]:
    return get_product_by_id(product_id)
