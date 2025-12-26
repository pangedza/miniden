from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from database import get_session
from models import (
    AdminSiteCategory,
    MasterclassImage,
    ProductBasket,
    ProductCategory,
    ProductCourse,
    ProductImage,
)

BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_DATA_DIR = BASE_DIR / "docs" / "legacy-data"
BASKETS_JSON = LEGACY_DATA_DIR / "products_baskets.json"
COURSES_JSON = LEGACY_DATA_DIR / "products_courses.json"


def _slugify(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    normalized = raw.lower()
    normalized = (
        normalized.encode("ascii", "ignore").decode("ascii")
        if isinstance(normalized, str)
        else str(normalized)
    )
    normalized = normalized or raw.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug


def _unique_category_slug(session, slug: str, product_type: str, *, current_id: int | None = None) -> str:
    base = slug or "category"
    candidate = base
    suffix = 1

    while True:
        query = select(ProductCategory.id).where(
            ProductCategory.slug == candidate, ProductCategory.type == product_type
        )
        if current_id is not None:
            query = query.where(ProductCategory.id != current_id)

        exists = session.execute(query.limit(1)).scalar()
        if not exists:
            return candidate

        candidate = f"{base}-{suffix}"
        suffix += 1


def _map_category_type_to_adminsite(product_type: str) -> str:
    return "course" if product_type == "course" else "product"


def _unique_adminsite_slug(
    session,
    slug: str,
    page_type: str,
    *,
    current_id: int | None = None,
) -> str:
    base = slug or "category"
    candidate = base
    suffix = 2

    while True:
        query = select(AdminSiteCategory.id).where(
            AdminSiteCategory.slug == candidate,
            AdminSiteCategory.type == page_type,
        )
        if current_id is not None:
            query = query.where(AdminSiteCategory.id != current_id)

        exists = session.execute(query.limit(1)).scalar()
        if not exists:
            return candidate

        candidate = f"{base}-{suffix}"
        suffix += 1


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
        if category_meta:
            category_slug = category_meta.get("slug")
            category_name = category_meta.get("name")
        elif price > 0:
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


def _ensure_category_page(
    session,
    category: ProductCategory,
    *,
    force_create: bool = False,
) -> AdminSiteCategory:
    page_type = _map_category_type_to_adminsite(category.type)
    slug_base = _slugify(category.slug or category.name or f"category-{category.id}") or f"category-{category.id}"
    safe_slug = _unique_adminsite_slug(
        session,
        slug_base,
        page_type,
        current_id=int(category.page_id) if category.page_id else None,
    )

    page: AdminSiteCategory | None = None
    if category.page_id:
        page = session.get(AdminSiteCategory, category.page_id)

    if page is None and not force_create:
        page = (
            session.execute(
                select(AdminSiteCategory)
                .where(AdminSiteCategory.slug == safe_slug)
                .where(AdminSiteCategory.type == page_type)
            )
            .scalars()
            .first()
        )

    if page is None:
        page = AdminSiteCategory(type=page_type, title=category.name, slug=safe_slug)
        session.add(page)
        session.flush()

    if page.title != category.name:
        page.title = category.name
    if page.slug != safe_slug:
        page.slug = safe_slug
    page.is_active = bool(category.is_active)
    page.sort = int(category.sort_order or 0)

    if category.page_id != page.id:
        category.page_id = page.id

    session.add(page)
    session.add(category)
    return page


BASKET_CATEGORY_PRESETS: list[dict[str, Any]] = [
    {
        "id": 1,
        "slug": "basket",
        "name": "Корзинки",
        "description": "Корзинки для дома и организации пространства",
        "image_url": None,
        "type": "basket",
    },
    {
        "id": 2,
        "slug": "cradle",
        "name": "Люльки",
        "description": "Уютные люльки и колыбели ручной работы",
        "image_url": None,
        "type": "basket",
    },
    {
        "id": 3,
        "slug": "set",
        "name": "Наборы",
        "description": "Готовые наборы корзинок и аксессуаров",
        "image_url": None,
        "type": "basket",
    },
    {
        "id": 4,
        "slug": "decor",
        "name": "Декор",
        "description": "Элементы декора и уютные мелочи",
        "image_url": None,
        "type": "basket",
    },
]

COURSE_CATEGORY_PRESETS: list[dict[str, Any]] = [
    {
        "slug": "paid",
        "name": "Платные курсы",
        "description": "Полные мастер-классы и обучающие программы",
        "image_url": None,
        "type": "course",
    },
    {
        "slug": "free",
        "name": "Бесплатные уроки",
        "description": "Бесплатные материалы и полезные советы",
        "image_url": None,
        "type": "course",
    },
]


def _ensure_default_categories(product_type: str) -> None:
    presets_by_type = {
        "basket": BASKET_CATEGORY_PRESETS,
        "course": COURSE_CATEGORY_PRESETS,
    }

    presets = presets_by_type.get(product_type)
    if not presets:
        return

    with get_session() as session:
        for sort_order, preset in enumerate(presets):
            slug = preset.get("slug")
            if not slug:
                continue

            statement = (
                insert(ProductCategory)
                .values(
                    name=preset.get("name"),
                    slug=slug,
                    description=preset.get("description"),
                    image_url=preset.get("image_url"),
                    sort_order=preset.get("sort_order", sort_order),
                    is_active=preset.get("is_active", True),
                    type=preset.get("type", product_type),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                .on_conflict_do_nothing(index_elements=["slug"])
            )
            session.execute(statement)


def _category_meta(row: ProductCategory) -> dict[str, Any]:
    updated_at = getattr(row, "updated_at", None)
    image_version = int(updated_at.timestamp()) if updated_at else None
    return {
        "id": int(row.id),
        "slug": row.slug or f"cat-{row.id}",
        "name": row.name,
        "description": getattr(row, "description", None),
        "image_url": getattr(row, "image_url", None),
        "image_version": image_version,
        "type": row.type,
        "sort_order": int(row.sort_order or 0),
        "is_active": bool(row.is_active),
        "page_id": getattr(row, "page_id", None),
        "page_slug": getattr(row, "slug", None),
        "created_at": row.created_at,
        "updated_at": updated_at,
    }


def _load_category_maps(product_type: str, *, include_mixed: bool = False):
    map_by_id: dict[int, dict[str, Any]] = {}
    map_by_slug: dict[str, dict[str, Any]] = {}

    query_types = [product_type]
    if include_mixed and product_type != "mixed":
        query_types.append("mixed")

    for query_type in query_types:
        _ensure_default_categories(query_type)

    with get_session() as session:
        rows = (
            session.execute(
                select(ProductCategory)
                .where(ProductCategory.type.in_(query_types))
                .order_by(ProductCategory.sort_order, ProductCategory.id)
            )
            .scalars()
            .all()
        for row in rows:
            if getattr(row, "page_id", None) is None:
                _ensure_category_page(session, row)
        )

    for row in rows:
        meta = _category_meta(row)
        if meta["id"] not in map_by_id:
            map_by_id[meta["id"]] = meta
        map_by_slug.setdefault(meta["slug"], meta)

    return map_by_id, map_by_slug


def _basket_category_from_id(category_id: int | None, *, map_by_id: dict[int, dict[str, Any]] | None = None) -> dict[str, Any]:
    map_by_id = map_by_id or {}
    if category_id in map_by_id:
        return map_by_id[category_id]

    presets_map = {item["id"]: item for item in BASKET_CATEGORY_PRESETS if item.get("id") is not None}
    if category_id in presets_map:
        return presets_map[category_id]
    if category_id is None:
        return {
            "id": None,
            "slug": "uncategorized",
            "name": "Без категории",
            "description": None,
            "image_url": None,
            "type": "basket",
        }
    return {
        "id": category_id,
        "slug": f"cat-{category_id}",
        "name": f"Категория {category_id}",
        "description": None,
        "image_url": None,
        "type": "basket",
    }


def _basket_category_by_slug(slug: str, *, map_by_slug: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    map_by_slug = map_by_slug or {}
    if slug in map_by_slug:
        return map_by_slug[slug]

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


def list_categories(product_type: str | None = None, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    """Вернёт список категорий для корзинок или курсов."""

    categories_by_slug: dict[str, dict[str, Any]] = {}

    if product_type:
        types = [product_type]
        if product_type in {"basket", "course"}:
            types.append("mixed")
    else:
        types = ["basket", "course", "mixed"]

    for current_type in types:
        map_by_id, map_by_slug = _load_category_maps(current_type)
        if current_type == "basket":
            grouped: dict[str, dict[str, Any]] = {item["slug"]: item for item in BASKET_CATEGORY_PRESETS}

            with get_session() as session:
                rows = session.execute(select(func.distinct(ProductBasket.category_id))).scalars().all()
                for cat_id in rows:
                    meta = _basket_category_from_id(cat_id, map_by_id=map_by_id)
                    grouped.setdefault(meta["slug"], meta)

            for _, meta in map_by_id.items():
                grouped.setdefault(meta["slug"], meta)

            for slug, meta in grouped.items():
                categories_by_slug.setdefault(slug, meta)
        else:
            for slug, meta in map_by_slug.items():
                categories_by_slug.setdefault(slug, meta)

    filtered = [item for item in categories_by_slug.values() if include_inactive or item.get("is_active", True)]
    return sorted(filtered, key=lambda item: (item.get("sort_order", 0), item.get("id") or 0, item.get("slug", "")))


def list_product_categories_admin(product_type: str = "basket") -> list[dict[str, Any]]:
    map_by_id, _ = _load_category_maps(product_type, include_mixed=True)
    categories = [
        {
            "id": meta.get("id"),
            "name": meta.get("name"),
            "slug": meta.get("slug"),
            "description": meta.get("description"),
            "image_url": meta.get("image_url"),
            "image_version": meta.get("image_version"),
            "sort_order": meta.get("sort_order", 0),
            "is_active": meta.get("is_active", True),
            "type": meta.get("type"),
            "page_id": meta.get("page_id"),
            "page_slug": meta.get("page_slug"),
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
        }
        for meta in map_by_id.values()
    ]
    return sorted(categories, key=lambda item: (item.get("sort_order", 0), item.get("id") or 0))


def create_product_category(
    name: str,
    *,
    slug: str | None = None,
    description: str | None = None,
    image_url: str | None = None,
    sort_order: int = 0,
    is_active: bool = True,
    product_type: str = "basket",
) -> int:
    with get_session() as session:
        generated_slug = _slugify(slug or name) or f"category-{uuid4().hex[:8]}"
        safe_slug = _unique_category_slug(session, generated_slug, product_type)
        category = ProductCategory(
            name=name,
            slug=safe_slug,
            description=description,
            image_url=image_url,
            sort_order=sort_order,
            is_active=is_active,
            type=product_type,
        )
        session.add(category)
        session.flush()
        _ensure_category_page(session, category)
        return int(category.id)


def update_product_category(
    category_id: int,
    *,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    image_url: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
    product_type: str | None = None,
) -> bool:
    with get_session() as session:
        category = session.get(ProductCategory, category_id)
        if not category:
            return False

        if name is not None:
            category.name = name
        if slug is not None:
            generated_slug = _slugify(slug or name or category.name) or f"category-{category.id}"  # type: ignore[arg-type]
            category.slug = _unique_category_slug(
                session, generated_slug, product_type or category.type, current_id=category.id
            )
        if description is not None:
            category.description = description
        if image_url is not None:
            category.image_url = image_url
        if sort_order is not None:
            category.sort_order = sort_order
        if is_active is not None:
            category.is_active = is_active
        if product_type is not None:
            category.type = product_type
        _ensure_category_page(session, category)
        return True


def get_product_category_by_id(category_id: int) -> dict[str, Any] | None:
    with get_session() as session:
        category = session.get(ProductCategory, category_id)
        if not category:
            return None
        return {
            "id": int(category.id),
            "name": category.name,
            "slug": category.slug or f"cat-{category.id}",
            "description": category.description,
            "image_url": category.image_url,
            "image_version": int(category.updated_at.timestamp()) if getattr(category, "updated_at", None) else None,
            "sort_order": int(category.sort_order or 0),
            "is_active": bool(category.is_active),
            "type": category.type,
            "page_id": category.page_id,
            "page_slug": category.page.slug if getattr(category, "page", None) else None,
            "created_at": category.created_at,
            "updated_at": getattr(category, "updated_at", None),
        }


def ensure_category_page(category_id: int, *, force_create: bool = False) -> dict[str, Any] | None:
    with get_session() as session:
        category = session.get(ProductCategory, category_id)
        if not category:
            return None

        page = _ensure_category_page(session, category, force_create=force_create)
        return {"id": int(page.id), "slug": page.slug, "type": page.type}


def delete_product_category(category_id: int) -> str | None:
    with get_session() as session:
        category = session.get(ProductCategory, category_id)
        if not category:
            return None
        image_url = category.image_url
        session.delete(category)
        return image_url


def get_category_by_slug(slug: str, *, include_inactive: bool = False) -> dict[str, Any] | None:
    normalized_slug = (slug or "").strip()
    if not normalized_slug:
        return None

    for product_type in ("basket", "course", "mixed"):
        _, map_by_slug = _load_category_maps(
            product_type, include_mixed=product_type in {"basket", "course"}
        )
        meta = map_by_slug.get(normalized_slug)
        if meta and (include_inactive or meta.get("is_active", True)):
            return meta

    return None


def get_category_with_items(slug: str) -> dict[str, Any] | None:
    category = get_category_by_slug(slug)
    if not category:
        return None

    products: list[dict[str, Any]] = []
    masterclasses: list[dict[str, Any]] = []

    if category.get("type") in {"basket", "mixed"}:
        products = list_products("basket", category_slug=category.get("slug"), is_active=True)
    if category.get("type") in {"course", "mixed"}:
        masterclasses = list_products("course", category_slug=category.get("slug"), is_active=True)

    return {
        "category": {
            "id": category.get("id"),
            "slug": category.get("slug"),
            "name": category.get("name"),
            "description": category.get("description"),
            "image_url": category.get("image_url"),
            "image_version": category.get("image_version"),
            "type": category.get("type"),
            "sort_order": category.get("sort_order"),
            "is_active": category.get("is_active"),
            "page_id": category.get("page_id"),
            "page_slug": category.get("page_slug"),
            "created_at": category.get("created_at"),
            "updated_at": category.get("updated_at"),
        },
        "products": products,
        "masterclasses": masterclasses,
        "items": products + masterclasses,
    }


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

    basket_map_by_id: dict[int, dict[str, Any]] = {}
    basket_map_by_slug: dict[str, dict[str, Any]] = {}
    course_map_by_id: dict[int, dict[str, Any]] = {}
    course_map_by_slug: dict[str, dict[str, Any]] = {}

    if product_type != "course":
        basket_map_by_id, basket_map_by_slug = _load_category_maps("basket", include_mixed=True)
    if product_type != "basket":
        course_map_by_id, course_map_by_slug = _load_category_maps("course", include_mixed=True)

    results: list[dict[str, Any]] = []
    for model, p_type in models:
        with get_session() as session:
            query = select(model)
            if is_active is not None:
                query = query.where(model.is_active == (1 if is_active else 0))

            current_category_id = category_id
            category_meta = None

            if p_type == "basket" and category_slug:
                category_info = _basket_category_by_slug(category_slug, map_by_slug=basket_map_by_slug)
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

            course_category_meta = None
            if p_type == "course" and category_slug:
                if category_slug in {"paid", "free"}:
                    if category_slug == "paid":
                        query = query.where(model.price > 0)
                    elif category_slug == "free":
                        query = query.where(model.price <= 0)
                    course_category_meta = course_map_by_slug.get(category_slug)
                else:
                    course_category_meta = course_map_by_slug.get(category_slug)
                    if course_category_meta is None:
                        continue
                    current_category_id = course_category_meta.get("id")
                    if current_category_id is not None:
                        query = query.where(model.category_id == current_category_id)
                    else:
                        query = query.where(model.category_id.is_(None))

            rows = session.scalars(query.order_by(model.id)).all()
            for row in rows:
                meta = category_meta
                if p_type == "basket" and meta is None:
                    meta = _basket_category_from_id(getattr(row, "category_id", None), map_by_id=basket_map_by_id)
                if p_type == "course":
                    meta = course_category_meta or course_map_by_id.get(getattr(row, "category_id", None))
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
    payload = {
        "title": name,
        "description": description,
        "short_description": short_description,
        "price": price,
        "detail_url": detail_url,
        "is_active": 1,
        "category_id": category_id,
        "masterclass_url": masterclass_url,
        "image": image,
        "image_url": image_url,
    }

    if product_type != "course":
        payload.update(
            {
                "wb_url": wb_url,
                "ozon_url": ozon_url,
                "yandex_url": yandex_url,
                "avito_url": avito_url,
            }
        )

    model = _pick_model(product_type)
    with get_session() as session:
        instance = model(**payload)
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

        payload: dict[str, Any] = {
            "title": name,
            "description": description,
            "short_description": short_description,
            "price": price,
            "detail_url": detail_url,
            "category_id": category_id,
            "wb_url": wb_url,
            "ozon_url": ozon_url,
            "yandex_url": yandex_url,
            "avito_url": avito_url,
            "masterclass_url": masterclass_url,
        }

        if image is not None:
            payload["image"] = image
        if image_url is not None:
            payload["image_url"] = image_url
        if is_active is not None:
            payload["is_active"] = 1 if is_active else 0

        if product_type == "course":
            for field in ("wb_url", "ozon_url", "yandex_url", "avito_url"):
                payload.pop(field, None)

        for key, value in payload.items():
            if not hasattr(instance, key):
                continue
            setattr(instance, key, value)

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
