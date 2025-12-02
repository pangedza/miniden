from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from database import get_session
from models import MasterclassImage, ProductBasket, ProductCourse, ProductImage

BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_DATA_DIR = BASE_DIR / "docs" / "legacy-data"
BASKETS_JSON = LEGACY_DATA_DIR / "products_baskets.json"
COURSES_JSON = LEGACY_DATA_DIR / "products_courses.json"


def _serialize_product(
    product: ProductBasket | ProductCourse,
    product_type: str,
    *,
    category_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    price = int(product.price or 0)

    def _serialize_image_item(item: ProductImage | MasterclassImage) -> dict[str, Any]:
        return {
            "id": int(item.id),
            "image_url": item.image_url,
            "position": int(item.position or 0),
            "is_main": bool(getattr(item, "is_main", False)),
        }

    if product_type == "basket":
        raw_images = getattr(product, "product_images", []) or []
    else:
        raw_images = getattr(product, "masterclass_images", []) or []

    images = [_serialize_image_item(item) for item in raw_images]

    image_url = getattr(product, "image_url", None) or getattr(product, "image", None)
    if not image_url and images:
        # TODO: синхронизировать image_url с основным фото.
        image_url = images[0]["image_url"]

    if product_type == "basket":
        meta = category_meta or {}
        category_slug = meta.get("slug")
        category_name = meta.get("name")
    elif product_type == "course":
        if price > 0:
            category_slug = "paid"
            category_name = "Платные курсы"
        else:
            category_slug = "free"
            category_name = "Бесплатные уроки"
    else:
        category_slug = None
        category_name = None

    return {
        "id": int(product.id),
        "type": product_type,
        "name": product.name,
        "price": price,
        "short_description": getattr(product, "short_description", None),
        "description": product.description or "",
        "detail_url": getattr(product, "detail_url", None),
        "image_file_id": getattr(product, "image", None),
        "image": getattr(product, "image", None),
        "image_url": image_url,
        "images": images,
        "is_active": bool(getattr(product, "is_active", 1)),
        "category_id": getattr(product, "category_id", None),
        "category_name": category_name,
        "category_slug": category_slug,
        "wb_url": getattr(product, "wb_url", None),
        "ozon_url": getattr(product, "ozon_url", None),
        "yandex_url": getattr(product, "yandex_url", None),
        "avito_url": getattr(product, "avito_url", None),
        "masterclass_url": getattr(product, "masterclass_url", None),
        "created_at": product.created_at.isoformat() if getattr(product, "created_at", None) else None,
    }


BASKET_CATEGORY_PRESETS: list[dict[str, Any]] = [
    {"id": 1, "slug": "basket", "name": "Корзинки", "type": "basket"},
    {"id": 2, "slug": "cradle", "name": "Люльки", "type": "basket"},
    {"id": 3, "slug": "set", "name": "Наборы", "type": "basket"},
    {"id": 4, "slug": "decor", "name": "Декор", "type": "basket"},
]


def _basket_category_from_id(category_id: int | None) -> dict[str, Any]:
    presets_map = {item["id"]: item for item in BASKET_CATEGORY_PRESETS if item.get("id") is not None}
    if category_id in presets_map:
        return presets_map[category_id]
    if category_id is None:
        return {"id": None, "slug": "uncategorized", "name": "Без категории", "type": "basket"}
    return {
        "id": category_id,
        "slug": f"cat-{category_id}",
        "name": f"Категория {category_id}",
        "type": "basket",
    }


def _basket_category_by_slug(slug: str) -> dict[str, Any] | None:
    for item in BASKET_CATEGORY_PRESETS:
        if item.get("slug") == slug:
            return item
    if slug == "uncategorized":
        return _basket_category_from_id(None)
    if slug.startswith("cat-"):
        try:
            category_id = int(slug.split("cat-", 1)[1])
            return _basket_category_from_id(category_id)
        except ValueError:
            return None
    return None


def _pick_model(product_type: str):
    if product_type == "basket":
        return ProductBasket
    if product_type == "course":
        return ProductCourse
    raise ValueError("Unknown product type")


def _serialize_image(record: ProductImage | MasterclassImage) -> dict[str, Any]:
    return {
        "id": int(record.id),
        "image_url": record.image_url,
        "position": int(record.position or 0),
        "is_main": bool(getattr(record, "is_main", False)),
    }


def _next_position(session, model, field, entity_id: int) -> int:
    max_position = session.scalar(select(func.max(model.position)).where(field == entity_id))
    return int(max_position or 0) + 1


def list_product_images(product_id: int) -> list[dict[str, Any]]:
    with get_session() as session:
        product = session.get(ProductBasket, product_id)
        if not product:
            raise ValueError("product_not_found")
        images = (
            session.execute(
                select(ProductImage)
                .where(ProductImage.product_id == product_id)
                .order_by(ProductImage.position, ProductImage.id)
            )
            .scalars()
            .all()
        )
        return [_serialize_image(img) for img in images]


def list_masterclass_images(masterclass_id: int) -> list[dict[str, Any]]:
    with get_session() as session:
        masterclass = session.get(ProductCourse, masterclass_id)
        if not masterclass:
            raise ValueError("masterclass_not_found")
        images = (
            session.execute(
                select(MasterclassImage)
                .where(MasterclassImage.masterclass_id == masterclass_id)
                .order_by(MasterclassImage.position, MasterclassImage.id)
            )
            .scalars()
            .all()
        )
        return [_serialize_image(img) for img in images]


def add_product_images(product_id: int, image_urls: list[str]) -> list[dict[str, Any]]:
    with get_session() as session:
        product = session.get(ProductBasket, product_id)
        if not product:
            raise ValueError("product_not_found")

        position = _next_position(session, ProductImage, ProductImage.product_id, product_id)
        created: list[ProductImage] = []
        for url in image_urls:
            image = ProductImage(
                product_id=product_id,
                image_url=url,
                position=position,
                is_main=False,
            )
            position += 1
            session.add(image)
            created.append(image)

        if not product.image_url and created:
            product.image_url = created[0].image_url

        session.flush()
        return [_serialize_image(item) for item in created]


def add_masterclass_images(masterclass_id: int, image_urls: list[str]) -> list[dict[str, Any]]:
    with get_session() as session:
        masterclass = session.get(ProductCourse, masterclass_id)
        if not masterclass:
            raise ValueError("masterclass_not_found")

        position = _next_position(
            session, MasterclassImage, MasterclassImage.masterclass_id, masterclass_id
        )
        created: list[MasterclassImage] = []
        for url in image_urls:
            image = MasterclassImage(
                masterclass_id=masterclass_id,
                image_url=url,
                position=position,
                is_main=False,
            )
            position += 1
            session.add(image)
            created.append(image)

        if not masterclass.image_url and created:
            masterclass.image_url = created[0].image_url

        session.flush()
        return [_serialize_image(item) for item in created]


def delete_product_image(image_id: int) -> str | None:
    with get_session() as session:
        image = session.get(ProductImage, image_id)
        if not image:
            return None
        image_url = image.image_url
        session.delete(image)
        return image_url


def delete_masterclass_image(image_id: int) -> str | None:
    with get_session() as session:
        image = session.get(MasterclassImage, image_id)
        if not image:
            return None
        image_url = image.image_url
        session.delete(image)
        return image_url


def list_categories(product_type: str) -> list[dict[str, Any]]:
    """Вернёт список категорий для корзинок или курсов."""

    if product_type == "course":
        return [
            {"slug": "paid", "name": "Платные курсы", "type": "course"},
            {"slug": "free", "name": "Бесплатные уроки", "type": "course"},
        ]

    if product_type != "basket":
        return []

    categories: dict[str, dict[str, Any]] = {
        item["slug"]: item for item in BASKET_CATEGORY_PRESETS
    }

    with get_session() as session:
        rows = session.execute(select(func.distinct(ProductBasket.category_id))).scalars().all()
        for cat_id in rows:
            meta = _basket_category_from_id(cat_id)
            categories.setdefault(meta["slug"], meta)

    return list(categories.values())


def list_products(
    product_type: str | None = None,
    *,
    is_active: bool | None = True,
    category_id: int | None = None,
    category_slug: str | None = None,
) -> list[dict[str, Any]]:
    """Возвращает список товаров из БД через ORM."""

    models: list[tuple[type[ProductBasket] | type[ProductCourse], str]] = []
    if product_type in {"basket", "course"}:
        models.append((_pick_model(product_type), product_type))
    else:
        models = [(ProductBasket, "basket"), (ProductCourse, "course")]

    results: list[dict[str, Any]] = []
    for model, p_type in models:
        with get_session() as session:
            query = select(model)
            if is_active is not None:
                query = query.where(model.is_active == (1 if is_active else 0))

            current_category_id = category_id
            category_meta = None

            if p_type == "basket" and category_slug:
                category_info = _basket_category_by_slug(category_slug)
                if category_info is None:
                    # неизвестная категория — вернём пустой список
                    continue
                current_category_id = category_info.get("id")
                category_meta = category_info
                if current_category_id is not None:
                    query = query.where(model.category_id == current_category_id)
                else:
                    query = query.where(model.category_id.is_(None))

            if current_category_id is not None and p_type == "basket" and category_meta is None:
                category_meta = _basket_category_from_id(current_category_id)

            if p_type == "course" and category_slug:
                if category_slug == "paid":
                    query = query.where(model.price > 0)
                elif category_slug == "free":
                    query = query.where(model.price <= 0)

            rows = session.scalars(query.order_by(model.id)).all()
            for row in rows:
                meta = category_meta
                if p_type == "basket" and meta is None:
                    meta = _basket_category_from_id(getattr(row, "category_id", None))
                results.append(_serialize_product(row, p_type, category_meta=meta))
    return results


def _get_by_id(
    model: type[ProductBasket] | type[ProductCourse],
    product_type: str,
    item_id: int,
    *,
    include_inactive: bool = False,
) -> dict[str, Any] | None:
    with get_session() as session:
        item = session.get(model, item_id)
        if not item:
            return None
        serialized = _serialize_product(item, product_type)
        if not include_inactive and serialized.get("is_active") != 1:
            return None
        return serialized


def get_basket_by_id(item_id: int, *, include_inactive: bool = False) -> dict[str, Any] | None:
    return _get_by_id(ProductBasket, "basket", item_id, include_inactive=include_inactive)


def get_course_by_id(item_id: int, *, include_inactive: bool = False) -> dict[str, Any] | None:
    return _get_by_id(ProductCourse, "course", item_id, include_inactive=include_inactive)


def get_product_by_id(product_id: int, *, include_inactive: bool = False) -> dict[str, Any] | None:
    return get_basket_by_id(product_id, include_inactive=include_inactive) or get_course_by_id(
        product_id, include_inactive=include_inactive
    )


def create_product(
    product_type: str,
    name: str,
    price: int,
    description: str = "",
    short_description: str | None = None,
    detail_url: str | None = None,
    category_id: int | None = None,
    *,
    wb_url: str | None = None,
    ozon_url: str | None = None,
    yandex_url: str | None = None,
    avito_url: str | None = None,
    masterclass_url: str | None = None,
    image: str | None = None,
    image_url: str | None = None,
) -> int:
    model = _pick_model(product_type)
    with get_session() as session:
        instance = model(
            title=name,
            description=description,
            short_description=short_description,
            price=price,
            detail_url=detail_url,
            is_active=1,
            category_id=category_id,
            wb_url=wb_url,
            ozon_url=ozon_url,
            yandex_url=yandex_url,
            avito_url=avito_url,
            masterclass_url=masterclass_url,
            image=image,
            image_url=image_url,
        )
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


def toggle_product_active(product_id: int, product_type: str | None = None) -> bool:
    models: list[type[ProductBasket] | type[ProductCourse]]

    if product_type:
        models = [_pick_model(product_type)]
    else:
        models = [ProductBasket, ProductCourse]

    for model in models:
        with get_session() as session:
            instance = session.get(model, product_id)
            if instance:
                instance.is_active = 0 if int(getattr(instance, "is_active", 1) or 0) == 1 else 1
                return True
    return False


def soft_delete_product(product_id: int) -> bool:
    return _update_field(product_id, "is_active", 0)


def list_products_by_status(is_active: bool | None = None) -> list[dict[str, Any]]:
    return list_products(is_active=is_active)


def list_products_admin(product_type: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    allowed_status = {"active", "hidden", "all", None}
    if status not in allowed_status:
        status = None

    is_active: bool | None
    if status == "active":
        is_active = True
    elif status == "hidden":
        is_active = False
    else:
        is_active = None

    return list_products(product_type, is_active=is_active)


def update_product_full(
    product_id: int,
    product_type: str,
    name: str,
    price: int,
    description: str = "",
    short_description: str | None = None,
    detail_url: str | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
    *,
    wb_url: str | None = None,
    ozon_url: str | None = None,
    yandex_url: str | None = None,
    avito_url: str | None = None,
    masterclass_url: str | None = None,
    image: str | None = None,
    image_url: str | None = None,
) -> bool:
    model = _pick_model(product_type)
    with get_session() as session:
        instance = session.get(model, product_id)
        if not instance:
            return False

        instance.title = name
        instance.description = description
        instance.short_description = short_description
        instance.price = price
        instance.detail_url = detail_url
        instance.category_id = category_id
        instance.wb_url = wb_url
        instance.ozon_url = ozon_url
        instance.yandex_url = yandex_url
        instance.avito_url = avito_url
        instance.masterclass_url = masterclass_url
        if image is not None:
            instance.image = image
        if image_url is not None:
            instance.image_url = image_url
        if is_active is not None:
            instance.is_active = 1 if is_active else 0
        return True


def _update_field(product_id: int, field: str, value: Any) -> bool:
    for model in (ProductBasket, ProductCourse):
        with get_session() as session:
            instance = session.get(model, product_id)
            if instance:
                setattr(instance, field, value)
                return True
    return False


# Legacy helpers used by admin flows


def get_baskets() -> list[dict[str, Any]]:
    return list_products("basket", is_active=True)


def get_courses() -> list[dict[str, Any]]:
    return list_products("course", is_active=True)


def get_free_courses() -> list[dict[str, Any]]:
    return [course for course in get_courses() if int(course.get("price", 0)) == 0]


def get_paid_courses() -> list[dict[str, Any]]:
    return [course for course in get_courses() if int(course.get("price", 0)) > 0]


def get_product_with_category(product_id: int) -> dict[str, Any] | None:
    return get_product_by_id(product_id)


def seed_products_from_json() -> None:
    """Импорт начальных данных из JSON при пустых таблицах (опционально)."""

    def _load_json(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return []
        return [item for item in data if isinstance(item, dict)]

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
                        short_description=item.get("short_description"),
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
                        short_description=item.get("short_description"),
                        description=item.get("description"),
                        price=item.get("price", 0),
                        detail_url=item.get("detail_url"),
                        is_active=1,
                    )
                )
