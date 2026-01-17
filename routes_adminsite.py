"""Роуты админки сайта и административные API."""

from __future__ import annotations

import logging
import mimetypes
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin_panel.adminsite import (
    ADMINSITE_CONSTRUCTOR_PATH,
    ADMINSITE_STATIC_ROOT,
    router as adminsite_api_router,
)
from admin_panel.adminsite import service as adminsite_service
from admin_panel.routes import adminsite
from admin_panel.routes import auth as admin_auth
from admin_panel.routes import users as admin_users
from database import get_db, get_session
from media_paths import ADMIN_SITE_MEDIA_ROOT, MEDIA_ROOT, ensure_media_dirs
from models import User
from models.support import (
    SupportMessage,
    SupportMessageList,
    SupportSessionDetail,
    SupportSessionList,
)
from schemas.home import HomeBlockIn, HomePostIn, HomeSectionIn
from services import admin_notes as admin_notes_service
from services import branding as branding_service
from services import faq_service
from services import home as home_service
from services import menu_catalog
from services import orders as orders_service
from services import products as products_service
from services import promocodes as promocodes_service
from services import reviews as reviews_service
from services import stats as stats_service
from services import users as users_service
from services import webchat_service
from routes_public import (
    STATIC_DIR_PUBLIC,
    _faq_to_dict,
    _get_current_user_from_cookie,
    _validate_category_type,
    _validate_type,
)

router = APIRouter()

logger = logging.getLogger(__name__)

# AdminSite + Admin panel routers
router.include_router(admin_auth.router)
router.include_router(adminsite.router)
router.include_router(admin_users.router)
router.include_router(adminsite_api_router)


class AdminWebChatSendPayload(BaseModel):
    session_id: int
    text: str


class AdminWebChatClosePayload(BaseModel):
    session_id: int


class MenuCategoryPayload(BaseModel):
    title: str
    slug: str | None = None
    type: str = "product"
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = None
    order_index: int = 0
    is_active: bool = True


class MenuCategoryUpdatePayload(BaseModel):
    title: str | None = None
    slug: str | None = None
    type: str | None = None
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = None
    order_index: int | None = None
    is_active: bool | None = None

    class Config:
        extra = "ignore"


class MenuItemPayload(BaseModel):
    category_id: int
    title: str
    slug: str | None = None
    subtitle: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    images: list[str] = []
    image_url: str | None = None
    legacy_link: str | None = None
    order_index: int = 0
    is_active: bool = True
    stock_qty: int | None = None
    type: str = "product"
    meta: dict[str, Any] = {}


class MenuItemUpdatePayload(BaseModel):
    category_id: int | None = None
    title: str | None = None
    slug: str | None = None
    subtitle: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    images: list[str] | None = None
    image_url: str | None = None
    legacy_link: str | None = None
    order_index: int | None = None
    is_active: bool | None = None
    stock_qty: int | None = None
    type: str | None = None
    meta: dict[str, Any] | None = None

    class Config:
        extra = "ignore"


class MenuReorderEntry(BaseModel):
    id: int
    order_index: int


class MenuReorderPayload(BaseModel):
    categories: list[MenuReorderEntry] = []
    items: list[MenuReorderEntry] = []


class SiteSettingsPayload(BaseModel):
    brand_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    background_color: str | None = None
    contacts: dict[str, Any] = {}
    social_links: dict[str, Any] = {}
    hero_enabled: bool | None = None
    hero_title: str | None = None
    hero_subtitle: str | None = None
    hero_image_url: str | None = None


class SiteBlockPayload(BaseModel):
    page: str
    type: str
    title: str | None = None
    subtitle: str | None = None
    image_url: str | None = None
    payload: dict[str, Any] = {}
    order_index: int = 0
    is_active: bool = True


class SiteBlockUpdatePayload(BaseModel):
    page: str | None = None
    type: str | None = None
    title: str | None = None
    subtitle: str | None = None
    image_url: str | None = None
    payload: dict[str, Any] | None = None
    order_index: int | None = None
    is_active: bool | None = None

    class Config:
        extra = "ignore"


class BlockReorderEntry(BaseModel):
    id: int
    order_index: int


class BlockReorderPayload(BaseModel):
    blocks: list[BlockReorderEntry] = []


class AdminWebChatReadPayload(BaseModel):
    last_read_message_id: int | None = None


class AdminWebChatReplyBody(BaseModel):
    text: str


class ReviewStatusUpdatePayload(BaseModel):
    status: str
    is_deleted: bool | None = None


class FaqCreatePayload(BaseModel):
    category: str
    question: str
    answer: str


class FaqUpdatePayload(BaseModel):
    category: str | None = None
    question: str | None = None
    answer: str | None = None
    sort_order: int | None = None


class AdminSupportMessagePayload(BaseModel):
    session_id: int
    text: str


class AdminSupportClosePayload(BaseModel):
    session_id: int


class AdminProductsCreatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    stock: int = Field(default=0, ge=0)
    short_description: str | None = ""
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    image: str | None = None
    image_url: str | None = None
    wb_url: str | None = None
    ozon_url: str | None = None
    yandex_url: str | None = None
    avito_url: str | None = None
    masterclass_url: str | None = None


class AdminProductsUpdatePayload(BaseModel):
    user_id: int
    type: str
    name: str
    price: int
    stock: int | None = Field(default=None, ge=0)
    short_description: str | None = ""
    description: str | None = ""
    detail_url: str | None = None
    category_id: int | None = None
    is_active: bool | None = None
    image: str | None = None
    image_url: str | None = None
    wb_url: str | None = None
    ozon_url: str | None = None
    yandex_url: str | None = None
    avito_url: str | None = None
    masterclass_url: str | None = None


class AdminProductCategoryPayload(BaseModel):
    user_id: int
    name: str
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    sort_order: int = 0
    is_active: bool | None = True
    type: str = "basket"


class AdminProductCategoryUpdatePayload(BaseModel):
    user_id: int
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    type: str | None = None


class AdminCategoryPagePayload(BaseModel):
    user_id: int
    force: bool | None = False


class AdminTogglePayload(BaseModel):
    user_id: int
    type: str


class AdminOrderStatusPayload(BaseModel):
    user_id: int
    status: str


class AdminPromocodeCreatePayload(BaseModel):
    user_id: int
    code: str
    discount_type: str
    discount_value: float
    scope: str = "all"
    target_id: int | None = None
    max_uses: int | None = None
    date_start: str | None = None
    date_end: str | None = None
    expires_at: str | None = None
    active: bool | None = None
    one_per_user: bool | None = None


class AdminPromocodeUpdatePayload(BaseModel):
    user_id: int
    code: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    max_uses: int | None = None
    active: bool | None = None
    scope: str | None = None
    target_id: int | None = None
    date_start: str | None = None
    date_end: str | None = None
    expires_at: str | None = None
    one_per_user: bool | None = None


class AdminNotePayload(BaseModel):
    user_id: int
    target_id: int
    note: str


class AdminImageKind(str, Enum):
    product = "product"
    course = "course"
    home = "home"


def _ensure_admin(user_id: int | None) -> int:
    if user_id is None or not users_service.is_admin(int(user_id)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return int(user_id)


def get_admin_user(request: Request) -> User:
    with get_session() as session:
        user = _get_current_user_from_cookie(session, request)
        if not user or not getattr(user, "is_admin", False):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user


def _save_branding_file(
    file: UploadFile, allowed_extensions: set[str], max_size_mb: int, prefix: str
) -> str:
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=422, detail="Недопустимый формат файла")

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Пустой файл")

    max_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=422, detail=f"Файл слишком большой (до {max_size_mb} МБ)")

    ensure_media_dirs()
    target_dir = MEDIA_ROOT / "branding"
    target_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{prefix}_{uuid4().hex}{ext}"
    full_path = target_dir / unique_name
    with full_path.open("wb") as f:
        f.write(content)

    return f"/media/branding/{unique_name}"


def _delete_media_file(url: str | None) -> None:
    if not url:
        return

    try:
        if url.startswith("/media/"):
            target_path = MEDIA_ROOT / url.split("/media/", 1)[1]
        elif url.startswith("/static/uploads/"):
            target_path = STATIC_DIR_PUBLIC / url.replace("/static/", "")
        else:
            return

        if target_path.is_file():
            target_path.unlink()
    except OSError:
        # тихо игнорируем ошибки удаления, чтобы не ломать основной поток
        pass


def _bool_from_any(value, default: bool | None = None) -> bool | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}
    return default


def _int_from_any(value, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _save_uploaded_image(
    file: UploadFile, base_folder: str, *, scope: str = "adminsite"
) -> dict[str, Any]:
    max_bytes = 5 * 1024 * 1024
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=422, detail="Неверный формат изображения")

    base_folder = (base_folder or "").strip("/") or "uploads"
    if base_folder not in {"products", "courses", "categories", "home", "reviews", "uploads"}:
        base_folder = "uploads"

    ensure_media_dirs()

    ext = (file.filename or "jpg").split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"

    filename = f"{uuid4().hex}.{ext}"
    target_dir = (ADMIN_SITE_MEDIA_ROOT / base_folder) if base_folder else ADMIN_SITE_MEDIA_ROOT
    target_dir.mkdir(parents=True, exist_ok=True)
    full_path = target_dir / filename

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Пустой файл")
    if len(content) > max_bytes:
        raise HTTPException(status_code=422, detail="Файл слишком большой. Лимит 5 МБ.")
    with full_path.open("wb") as f:
        f.write(content)

    if not full_path.exists():
        logger.error("Upload write reported success but file is missing: %s", full_path)
        raise HTTPException(
            status_code=500,
            detail="Не удалось сохранить файл на сервер",
        )

    saved_size = len(content)
    content_type = file.content_type or mimetypes.guess_type(full_path.name)[0]
    relative = full_path.relative_to(MEDIA_ROOT).as_posix()
    url = f"/media/{relative}"

    logger.info(
        "Saved upload to %s (size=%s, content_type=%s)",
        full_path,
        saved_size,
        content_type,
    )

    return {
        "url": url,
        "original_name": file.filename or filename,
        "size": saved_size,
        "content_type": content_type or "application/octet-stream",
    }


def _wrap_home_banner_error(action: str, func):
    try:
        return func()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: WPS430
        logger.exception("Home banner %s failed", action)
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Не удалось {action} блок главной",
                "error": str(exc),
            },
        ) from exc


def _wrap_home_block_error(action: str, func):
    return _wrap_home_banner_error(action, func)


def _resolve_public_base_url() -> str | None:
    settings = menu_catalog.get_site_settings()
    base_url = (settings or {}).get("base_url") if isinstance(settings, dict) else None
    if not base_url:
        return None
    return str(base_url).rstrip("/")


def _build_public_link(base_url: str | None, path: str) -> str:
    if base_url:
        return f"{base_url}{path}"
    return path


@router.get("/api/adminsite/debug/static")
def adminsite_debug_static():
    static_dir = ADMINSITE_STATIC_ROOT.resolve()
    constructor_path = ADMINSITE_CONSTRUCTOR_PATH.resolve()

    return {
        "static_mount": "/static",
        "static_dir": str(static_dir),
        "static_dir_exists": static_dir.exists(),
        "constructor_path": str(constructor_path),
        "constructor_exists": constructor_path.exists(),
    }


@router.get("/api/adminsite/debug/routes")
def adminsite_debug_routes(request: Request):
    return [
        {"path": getattr(route, "path", ""), "name": getattr(route, "name", "")}
        for route in request.app.routes
    ]


@router.put("/api/site-settings")
def update_site_settings(payload: SiteSettingsPayload, request: Request, db: Session = Depends(get_db)):
    adminsite_service.ensure_admin(request, db)
    return menu_catalog.update_site_settings(payload.model_dump())


@router.post("/api/admin/branding")
def admin_update_branding(
    site_title: str | None = Form(None),
    logo_file: UploadFile | None = File(None),
    favicon_file: UploadFile | None = File(None),
    admin_user=Depends(get_admin_user),
):
    logo_url = None
    favicon_url = None
    bump_assets = False

    if logo_file:
        logo_url = _save_branding_file(
            logo_file, {".png", ".jpg", ".jpeg", ".webp", ".svg"}, 5, "logo"
        )
        bump_assets = True

    if favicon_file:
        favicon_url = _save_branding_file(
            favicon_file, {".ico", ".png", ".svg"}, 2, "favicon"
        )
        bump_assets = True

    with get_session() as session:
        branding = branding_service.get_or_create_branding(session)
        branding_service.update_branding_record(
            branding,
            site_title=site_title if site_title is not None else None,
            logo_url=logo_url,
            favicon_url=favicon_url,
            bump_assets=bump_assets,
        )
        session.add(branding)
        session.flush()
    return branding_service.serialize_branding(branding)


@router.get("/api/admin/site-settings")
def admin_get_site_settings(request: Request, db: Session = Depends(get_db)):
    adminsite_service.ensure_admin(request, db)
    return menu_catalog.get_site_settings()


@router.put("/api/admin/site-settings")
def admin_update_site_settings(
    payload: SiteSettingsPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    return menu_catalog.update_site_settings(payload.model_dump())


@router.get("/api/admin/blocks")
def admin_blocks(
    request: Request,
    include_inactive: bool = True,
    page: str | None = None,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    return {"items": menu_catalog.list_blocks(include_inactive=include_inactive, page=page)}


@router.post("/api/admin/blocks")
def admin_create_block(
    payload: SiteBlockPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.create_block(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/api/admin/blocks/{block_id}")
def admin_update_block(
    block_id: int,
    payload: SiteBlockUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.update_block(block_id, payload.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/api/admin/blocks/{block_id}")
def admin_delete_block(
    block_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        menu_catalog.delete_block(block_id)
        return {"status": "ok"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/api/admin/blocks/reorder")
def admin_blocks_reorder(
    payload: BlockReorderPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    menu_catalog.reorder_blocks(payload.model_dump())
    return {"status": "ok"}


@router.get("/api/admin/menu/categories")
def admin_menu_categories(
    request: Request,
    include_inactive: bool = True,
    type: str | None = None,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    base_url = _resolve_public_base_url()
    try:
        categories = menu_catalog.list_categories(
            include_inactive=include_inactive, category_type=type
        )
        for category in categories:
            category["public_url"] = _build_public_link(
                base_url, f"/c/{category.get('slug')}"
            )
        return {"items": categories}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/api/admin/menu/categories")
def admin_menu_create_category(
    payload: MenuCategoryPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.create_category(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/api/admin/menu/categories/{category_id}")
def admin_menu_update_category(
    category_id: int,
    payload: MenuCategoryUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.update_category(category_id, payload.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/api/admin/menu/categories/{category_id}")
def admin_menu_delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        menu_catalog.delete_category(category_id)
        return {"status": "ok"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/api/admin/menu/items")
def admin_menu_items(
    request: Request,
    category_id: int | None = None,
    type: str | None = None,
    include_inactive: bool = True,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        base_url = _resolve_public_base_url()
        items = menu_catalog.list_items(
            include_inactive=include_inactive,
            category_id=category_id,
            item_type=type,
        )
        for item in items:
            item["public_url"] = _build_public_link(
                base_url, f"/i/{item.get('id')}"
            )
        return {"items": items}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/api/admin/menu/items")
def admin_menu_create_item(
    payload: MenuItemPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.create_item(payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/api/admin/menu/items/{item_id}")
def admin_menu_update_item(
    item_id: int,
    payload: MenuItemUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        return menu_catalog.update_item(item_id, payload.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/api/admin/menu/items/{item_id}")
def admin_menu_delete_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    try:
        menu_catalog.delete_item(item_id)
        return {"status": "ok"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/api/admin/menu/reorder")
def admin_menu_reorder(
    payload: MenuReorderPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    adminsite_service.ensure_admin(request, db)
    menu_catalog.reorder_entities(payload.model_dump())
    return {"status": "ok"}


@router.post("/api/admin/upload-image")
def admin_upload_image(
    kind: AdminImageKind = Form(...),
    file: UploadFile = File(...),
    admin_user=Depends(get_admin_user),
):
    """
    Загрузка изображения для товара/курса из админки.
    Сохраняет файл в файловой системе и возвращает URL, который потом пишется в image_url.
    """
    base_folder_by_kind = {
        AdminImageKind.product: "products",
        AdminImageKind.course: "courses",
        AdminImageKind.home: "home",
    }
    base_folder = base_folder_by_kind.get(kind, "products")
    upload = _save_uploaded_image(file, base_folder)

    return {"ok": True, **upload}


@router.post("/api/admin/home/upload_image")
def admin_upload_home_image(file: UploadFile = File(...), admin_user=Depends(get_admin_user)):
    """
    Загрузка изображения для блоков главной страницы.
    Путь отличается от общего upload-image, но сохраняет файл в `/media/adminsite/home/`.
    """
    upload = _save_uploaded_image(file, "home")
    return {"ok": True, **upload}


@router.get("/api/admin/products/{product_id}/images")
def admin_product_images(product_id: int, user_id: int):
    _ensure_admin(user_id)
    try:
        images = products_service.list_product_images(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"items": images}


@router.post("/api/admin/products/{product_id}/images")
def admin_upload_product_images(
    product_id: int,
    files: list[UploadFile] = File(...),
    admin_user=Depends(get_admin_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов для загрузки")

    uploads = [_save_uploaded_image(file, "products") for file in files]
    urls = [item["url"] for item in uploads]
    try:
        images = products_service.add_product_images(product_id, urls)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"items": images, "uploads": uploads}


@router.delete("/api/admin/products/images/{image_id}")
def admin_delete_product_image(image_id: int, user_id: int):
    _ensure_admin(user_id)
    image_url = products_service.delete_product_image(image_id)
    if not image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    _delete_media_file(image_url)
    return {"ok": True}


@router.get("/api/admin/masterclasses/{masterclass_id}/images")
def admin_masterclass_images(masterclass_id: int, user_id: int):
    _ensure_admin(user_id)
    try:
        images = products_service.list_masterclass_images(masterclass_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return {"items": images}


@router.post("/api/admin/masterclasses/{masterclass_id}/images")
def admin_upload_masterclass_images(
    masterclass_id: int,
    files: list[UploadFile] = File(...),
    admin_user=Depends(get_admin_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов для загрузки")

    uploads = [_save_uploaded_image(file, "courses") for file in files]
    urls = [item["url"] for item in uploads]
    try:
        images = products_service.add_masterclass_images(masterclass_id, urls)
    except ValueError:
        raise HTTPException(status_code=404, detail="Masterclass not found")
    return {"items": images, "uploads": uploads}


@router.delete("/api/admin/masterclasses/images/{image_id}")
def admin_delete_masterclass_image(image_id: int, user_id: int):
    _ensure_admin(user_id)
    image_url = products_service.delete_masterclass_image(image_id)
    if not image_url:
        raise HTTPException(status_code=404, detail="Image not found")

    _delete_media_file(image_url)
    return {"ok": True}


@router.get("/api/admin/reviews")
def admin_reviews(
    status: str | None = None,
    product_id: int | None = None,
    user_id: int | None = None,
    page: int = 1,
    limit: int = 50,
    admin_user=Depends(get_admin_user),
):
    reviews = reviews_service.admin_list_reviews(
        status=status, product_id=product_id, user_id=user_id, page=page, limit=limit
    )
    return {"items": reviews, "page": page, "limit": limit}


@router.post("/api/admin/reviews/{review_id}/status")
def admin_update_review_status(
    review_id: int, payload: ReviewStatusUpdatePayload, admin_user=Depends(get_admin_user)
):
    try:
        review = reviews_service.admin_update_review_status(
            review_id, new_status=payload.status, is_deleted=payload.is_deleted
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return {"ok": True, "status": review.status, "is_deleted": review.is_deleted}


@router.get("/api/admin/faq")
def admin_faq_list(user_id: int, category: str | None = None):
    _ensure_admin(user_id)
    items = faq_service.get_faq_list(category)
    return {"items": [_faq_to_dict(item) for item in items]}


@router.post("/api/admin/faq")
def admin_create_faq(payload: FaqCreatePayload, user_id: int):
    _ensure_admin(user_id)
    item = faq_service.create_faq_item(payload.dict())
    return _faq_to_dict(item)


@router.put("/api/admin/faq/{faq_id}")
def admin_update_faq(faq_id: int, payload: FaqUpdatePayload, user_id: int):
    _ensure_admin(user_id)
    data = {key: value for key, value in payload.dict().items() if value is not None}
    item = faq_service.update_faq_item(faq_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return _faq_to_dict(item)


@router.delete("/api/admin/faq/{faq_id}")
def admin_delete_faq(faq_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = faq_service.delete_faq_item(faq_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"ok": True}


@router.get("/api/admin/home/banners")
def admin_home_banners(user_id: int):
    _ensure_admin(user_id)
    items = _wrap_home_banner_error("list", home_service.list_banners)
    return {"items": [item.dict() for item in items]}


@router.post("/api/admin/home/banners")
def admin_create_home_banner(payload: HomeBlockIn, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error("create", lambda: home_service.create_banner(payload))
    return banner.dict()


@router.get("/api/admin/home/banners/{banner_id}")
def admin_get_home_banner(banner_id: int, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error("get", lambda: home_service.get_banner(banner_id))
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    return banner.dict()


@router.put("/api/admin/home/banners/{banner_id}")
def admin_update_home_banner(banner_id: int, payload: HomeBlockIn, user_id: int):
    _ensure_admin(user_id)
    banner = _wrap_home_banner_error(
        "update", lambda: home_service.update_banner(banner_id, payload)
    )
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    return banner.dict()


@router.delete("/api/admin/home/banners/{banner_id}")
def admin_delete_home_banner(banner_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = _wrap_home_banner_error("delete", lambda: home_service.delete_banner(banner_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Banner not found")
    return {"ok": True}


@router.get("/api/admin/home/blocks")
def admin_home_blocks(user_id: int):
    _ensure_admin(user_id)
    items = _wrap_home_block_error("list", home_service.list_blocks)
    return {"items": [item.dict() for item in items]}


@router.post("/api/admin/home/blocks")
def admin_create_home_block(payload: HomeBlockIn, user_id: int):
    _ensure_admin(user_id)
    block = _wrap_home_block_error("create", lambda: home_service.create_block(payload))
    return block.dict()


@router.get("/api/admin/home/blocks/{block_id}")
def admin_get_home_block(block_id: int, user_id: int):
    _ensure_admin(user_id)
    block = _wrap_home_block_error("get", lambda: home_service.get_block(block_id))
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block.dict()


@router.put("/api/admin/home/blocks/{block_id}")
def admin_update_home_block(block_id: int, payload: HomeBlockIn, user_id: int):
    _ensure_admin(user_id)
    block = _wrap_home_block_error("update", lambda: home_service.update_block(block_id, payload))
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block.dict()


@router.delete("/api/admin/home/blocks/{block_id}")
def admin_delete_home_block(block_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = _wrap_home_block_error("delete", lambda: home_service.delete_block(block_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Block not found")
    return {"ok": True}


@router.get("/api/admin/home/sections")
def admin_home_sections(user_id: int):
    _ensure_admin(user_id)
    items = home_service.list_sections()
    return {"items": [item.dict() for item in items]}


@router.post("/api/admin/home/sections")
def admin_create_home_section(payload: HomeSectionIn, user_id: int):
    _ensure_admin(user_id)
    section = home_service.create_section(payload)
    return section.dict()


@router.get("/api/admin/home/sections/{section_id}")
def admin_get_home_section(section_id: int, user_id: int):
    _ensure_admin(user_id)
    section = home_service.get_section(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section.dict()


@router.put("/api/admin/home/sections/{section_id}")
def admin_update_home_section(section_id: int, payload: HomeSectionIn, user_id: int):
    _ensure_admin(user_id)
    section = home_service.update_section(section_id, payload)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section.dict()


@router.delete("/api/admin/home/sections/{section_id}")
def admin_delete_home_section(section_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = home_service.delete_section(section_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Section not found")
    return {"ok": True}


@router.get("/api/admin/home/posts")
def admin_home_posts(user_id: int):
    _ensure_admin(user_id)
    items = home_service.list_posts()
    return {"items": [item.dict() for item in items]}


@router.post("/api/admin/home/posts")
def admin_create_home_post(payload: HomePostIn, user_id: int):
    _ensure_admin(user_id)
    post = home_service.create_post(payload)
    return post.dict()


@router.get("/api/admin/home/posts/{post_id}")
def admin_get_home_post(post_id: int, user_id: int):
    _ensure_admin(user_id)
    post = home_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.dict()


@router.put("/api/admin/home/posts/{post_id}")
def admin_update_home_post(post_id: int, payload: HomePostIn, user_id: int):
    _ensure_admin(user_id)
    post = home_service.update_post(post_id, payload)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.dict()


@router.delete("/api/admin/home/posts/{post_id}")
def admin_delete_home_post(post_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = home_service.delete_post(post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"ok": True}


async def _parse_category_payload(
    request: Request, image_file: UploadFile | None = None, *, is_update: bool = False
) -> tuple[dict[str, Any], UploadFile | None]:
    raw: dict[str, Any] = {}
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("application/json"):
        try:
            raw = await request.json()
        except Exception:
            raw = {}
    else:
        form = await request.form()
        raw = {key: value for key, value in form.items() if not isinstance(value, UploadFile)}
        form_file = form.get("image_file")
        if isinstance(form_file, UploadFile) and image_file is None:
            image_file = form_file

    payload = {
        "user_id": _int_from_any(raw.get("user_id")),
        "name": raw.get("name"),
        "slug": raw.get("slug") or None,
        "description": raw.get("description") or None,
        "image_url": raw.get("image_url") or None,
        "sort_order": _int_from_any(raw.get("sort_order"), 0 if not is_update else None),
        "is_active": _bool_from_any(raw.get("is_active"), None if is_update else True),
        "type": raw.get("type") or ("basket" if not is_update else None),
    }

    if payload["type"] is not None:
        payload["type"] = _validate_category_type(str(payload["type"]))

    if payload["user_id"] is None:
        raise HTTPException(status_code=400, detail="user_id is required")

    if not is_update and not (payload.get("name") and str(payload["name"]).strip()):
        raise HTTPException(status_code=400, detail="name is required")

    return payload, image_file


def _persist_category_image(image_file: UploadFile | None, *, current_url: str | None = None) -> str | None:
    if not image_file:
        return current_url
    upload = _save_uploaded_image(image_file, "categories")
    new_url = upload["url"]
    if current_url and current_url != new_url:
        _delete_media_file(current_url)
    return new_url


# LEGACY ADMIN CATALOG ENDPOINTS (products_baskets/products_courses).
# Используйте /api/admin/menu* для работы с menu_items/menu_categories.
@router.get("/api/admin/products", deprecated=True)
def admin_products(user_id: int, type: str | None = None, status: str | None = None):
    _ensure_admin(user_id)
    if type:
        _validate_type(type)
    items = products_service.list_products_admin(type, status)
    return {"items": items}


@router.post("/api/admin/products", deprecated=True)
def admin_create_product(payload: AdminProductsCreatePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    new_id = products_service.create_product(
        product_type,
        payload.name,
        payload.price,
        payload.stock,
        payload.short_description or None,
        payload.description or "",
        payload.detail_url,
        payload.category_id,
        image=payload.image,
        image_url=payload.image_url,
        wb_url=payload.wb_url,
        ozon_url=payload.ozon_url,
        yandex_url=payload.yandex_url,
        avito_url=payload.avito_url,
        masterclass_url=payload.masterclass_url,
    )
    return {"id": new_id}


@router.put("/api/admin/products/{product_id}", deprecated=True)
def admin_update_product(product_id: int, payload: AdminProductsUpdatePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    updated = products_service.update_product_full(
        product_id,
        product_type,
        payload.name,
        payload.price,
        payload.stock,
        payload.short_description or None,
        payload.description or "",
        payload.detail_url,
        payload.category_id,
        payload.is_active,
        image=payload.image,
        image_url=payload.image_url,
        wb_url=payload.wb_url,
        ozon_url=payload.ozon_url,
        yandex_url=payload.yandex_url,
        avito_url=payload.avito_url,
        masterclass_url=payload.masterclass_url,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@router.patch("/api/admin/products/{product_id}/toggle_active", deprecated=True)
@router.post("/api/admin/products/{product_id}/toggle", deprecated=True)
def admin_toggle_product(product_id: int, payload: AdminTogglePayload):
    _ensure_admin(payload.user_id)
    product_type = _validate_type(payload.type)
    changed = products_service.toggle_product_active(product_id, product_type)
    if not changed:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@router.get("/api/admin/product-categories", deprecated=True)
def admin_product_categories(user_id: int, type: str = "basket"):
    _ensure_admin(user_id)
    product_type = _validate_category_type(type)
    items = products_service.list_product_categories_admin(product_type)
    return {"items": items}


@router.post("/api/admin/product-categories", deprecated=True)
async def admin_create_product_category(request: Request, image_file: UploadFile | None = File(None)):
    payload, image_file = await _parse_category_payload(request, image_file=image_file)
    _ensure_admin(payload["user_id"])

    product_type = payload.get("type") or "basket"
    image_url = payload.get("image_url")
    if image_file:
        image_url = _persist_category_image(image_file)

    new_id = products_service.create_product_category(
        payload.get("name") or "Категория",
        slug=payload.get("slug"),
        description=payload.get("description"),
        image_url=image_url,
        sort_order=payload.get("sort_order") or 0,
        is_active=payload.get("is_active") if payload.get("is_active") is not None else True,
        product_type=product_type,
    )
    created_category = products_service.get_product_category_by_id(new_id)
    return {
        "id": new_id,
        "image_url": image_url,
        "page_id": created_category.get("page_id") if created_category else None,
        "page_slug": created_category.get("page_slug") if created_category else None,
    }


@router.put("/api/admin/product-categories/{category_id}", deprecated=True)
async def admin_update_product_category(
    category_id: int, request: Request, image_file: UploadFile | None = File(None)
):
    payload, image_file = await _parse_category_payload(request, image_file=image_file, is_update=True)
    _ensure_admin(payload["user_id"])
    product_type = payload.get("type")

    current = products_service.get_product_category_by_id(category_id)
    if not current:
        raise HTTPException(status_code=404, detail="Category not found")

    image_url = payload.get("image_url", current.get("image_url"))
    if image_file:
        image_url = _persist_category_image(image_file, current_url=current.get("image_url"))

    updated = products_service.update_product_category(
        category_id,
        name=payload.get("name"),
        slug=payload.get("slug"),
        description=payload.get("description"),
        image_url=image_url,
        sort_order=payload.get("sort_order"),
        is_active=payload.get("is_active"),
        product_type=product_type,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")
    updated_category = products_service.get_product_category_by_id(category_id)
    return {
        "ok": True,
        "image_url": image_url,
        "page_id": updated_category.get("page_id") if updated_category else None,
        "page_slug": updated_category.get("page_slug") if updated_category else None,
    }


@router.post("/api/admin/product-categories/{category_id}/page", deprecated=True)
def admin_ensure_category_page(category_id: int, payload: AdminCategoryPagePayload):
    _ensure_admin(payload.user_id)
    page = products_service.ensure_category_page(category_id, force_create=bool(payload.force))
    if not page:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"page_id": page.get("id"), "page_slug": page.get("slug")}


@router.delete("/api/admin/product-categories/{category_id}", deprecated=True)
def admin_delete_product_category(category_id: int, user_id: int):
    _ensure_admin(user_id)
    image_url = products_service.delete_product_category(category_id)
    if image_url is None:
        raise HTTPException(status_code=404, detail="Category not found")
    _delete_media_file(image_url)
    return {"ok": True}


def _serialize_webchat_message(msg) -> dict:
    return {
        "id": msg.id,
        "text": msg.text,
        "sender": msg.sender,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "is_read_by_manager": getattr(msg, "is_read_by_manager", None),
        "is_read_by_client": getattr(msg, "is_read_by_client", None),
    }


@router.get("/api/admin/webchat/sessions", response_model=SupportSessionList)
def admin_webchat_sessions(
    request: Request,
    status: str = "open",
    search: str | None = None,
    page: int = 1,
    limit: int = 50,
    admin: User = Depends(get_admin_user),
):
    normalized_status = status if status != "all" else None
    sessions = webchat_service.list_sessions(
        status=normalized_status, limit=limit, search=search, page=page
    )

    items = []
    for session, last_message in sessions:
        items.append(
            {
                "session_id": int(session.id),
                "session_key": session.session_key or session.session_id,
                "status": session.status,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "user_identifier": session.user_identifier,
                "client_ip": session.client_ip,
                "last_message": last_message.text if last_message else None,
                "last_sender": last_message.sender if last_message else None,
                "last_message_at": session.last_message_at.isoformat()
                if session.last_message_at
                else None,
                "unread_for_manager": int(session.unread_for_manager or 0),
            }
        )

    return {"items": items}


@router.get("/api/admin/webchat/messages", response_model=SupportMessageList)
def admin_webchat_messages(
    session_id: int,
    after_id: int = 0,
    limit: int | None = None,
    admin: User = Depends(get_admin_user),
):
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = webchat_service.get_messages(
        session, limit=limit, after_id=after_id, mark_read_for="manager"
    )
    return {"items": [_serialize_webchat_message(msg) for msg in messages]}


@router.post("/api/admin/webchat/send", response_model=SupportMessage)
def admin_webchat_send(
    payload: AdminWebChatSendPayload, admin: User = Depends(get_admin_user)
):
    if not payload.text:
        raise HTTPException(status_code=400, detail="text is required")

    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message = webchat_service.add_manager_message(session, payload.text)
    return _serialize_webchat_message(message)


@router.post("/api/admin/webchat/close")
def admin_webchat_close(
    payload: AdminWebChatClosePayload, admin: User = Depends(get_admin_user)
):
    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_closed(session)
    return {"ok": True}


@router.post("/api/admin/webchat/reopen")
def admin_webchat_reopen(
    payload: AdminWebChatClosePayload, admin: User = Depends(get_admin_user)
):
    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_open(session)
    return {"ok": True}


@router.get("/api/webchat/sessions", response_model=SupportSessionList)
def api_admin_webchat_sessions(
    status: str = "open",
    search: str | None = None,
    page: int = 1,
    limit: int = 50,
    admin: User = Depends(get_admin_user),
):
    normalized_status = status if status != "all" else None
    sessions = webchat_service.list_sessions(
        status=normalized_status, limit=limit, search=search, page=page
    )

    items: list[dict[str, Any]] = []
    for session, last_message in sessions:
        items.append(
            {
                "session_id": int(session.id),
                "session_key": session.session_key or session.session_id,
                "status": session.status,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "user_identifier": session.user_identifier,
                "client_ip": session.client_ip,
                "last_message_at": session.last_message_at,
                "last_message": last_message.text if last_message else None,
                "last_sender": last_message.sender if last_message else None,
                "unread_for_manager": int(session.unread_for_manager or 0),
            }
        )

    return {"items": items}


@router.get("/api/webchat/sessions/{session_id}", response_model=SupportSessionDetail)
def api_admin_webchat_session_detail(
    session_id: int,
    after_id: int = 0,
    limit: int | None = None,
    admin: User = Depends(get_admin_user),
):
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = webchat_service.get_messages(
        session,
        limit=limit,
        after_id=after_id,
        mark_read_for="manager",
    )

    return {
        "session": {
            "session_id": int(session.id),
            "session_key": session.session_key or session.session_id,
            "status": session.status,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "last_message_at": session.last_message_at,
            "last_message": messages[-1].text if messages else None,
            "last_sender": messages[-1].sender if messages else None,
            "unread_for_manager": int(session.unread_for_manager or 0),
        },
        "messages": [_serialize_webchat_message(msg) for msg in messages],
    }


@router.post("/api/webchat/sessions/{session_id}/reply", response_model=SupportMessage)
def api_admin_webchat_reply(
    session_id: int,
    payload: AdminWebChatReplyBody,
    admin: User = Depends(get_admin_user),
):
    if not payload.text:
        raise HTTPException(status_code=400, detail="text is required")

    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message = webchat_service.add_manager_message(session, payload.text)
    if session.status == "waiting_manager":
        webchat_service.mark_open(session)

    return _serialize_webchat_message(message)


@router.post("/api/webchat/sessions/{session_id}/read")
def api_admin_webchat_mark_read(
    session_id: int,
    payload: AdminWebChatReadPayload = Body(default=AdminWebChatReadPayload()),
    admin: User = Depends(get_admin_user),
):
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_read_for_manager(
        session.id, last_read_message_id=payload.last_read_message_id
    )
    return {"ok": True}


@router.post("/api/webchat/sessions/{session_id}/close")
def api_admin_webchat_close(
    session_id: int, admin: User = Depends(get_admin_user)
):
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_closed(session)
    return {"ok": True}


@router.get("/api/admin/support/sessions", response_model=SupportSessionList)
def admin_support_sessions(user_id: int, status: str = "open", limit: int = 100):
    _ensure_admin(user_id)
    normalized_status = status if status != "all" else None
    sessions = webchat_service.list_sessions(status=normalized_status, limit=limit)

    items = []
    for session, last_message in sessions:
        items.append(
            {
                "session_id": int(session.id),
                "session_key": session.session_key or session.session_id,
                "status": session.status,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "last_message": last_message.text if last_message else None,
                "last_sender": last_message.sender if last_message else None,
            }
        )

    return {"items": items}


@router.get("/api/admin/support/messages", response_model=SupportMessageList)
def admin_support_messages(user_id: int, session_id: int):
    _ensure_admin(user_id)
    session = webchat_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = webchat_service.get_messages(
        session, limit=None, mark_read_for="manager"
    )
    return {"items": [_serialize_webchat_message(msg) for msg in messages]}


@router.post("/api/admin/support/message", response_model=SupportMessage)
def admin_support_send_message(user_id: int, payload: AdminSupportMessagePayload):
    _ensure_admin(user_id)
    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message = webchat_service.add_manager_message(session, payload.text)
    if session.status == "waiting_manager":
        webchat_service.mark_open(session)

    return _serialize_webchat_message(message)


@router.post("/api/admin/support/close")
def admin_support_close(user_id: int, payload: AdminSupportClosePayload):
    _ensure_admin(user_id)
    session = webchat_service.get_session_by_id(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    webchat_service.mark_closed(session)
    return {"ok": True}


@router.get("/api/admin/orders")
def admin_orders(user_id: int, status: str | None = None, limit: int = 100):
    _ensure_admin(user_id)
    orders = orders_service.list_orders(status=status, limit=limit)
    return {"items": orders}


@router.get("/api/admin/stats")
def admin_stats(user_id: int):
    _ensure_admin(user_id)
    return stats_service.get_admin_dashboard_stats()


@router.get("/api/admin/notes")
def admin_notes(user_id: int, target_id: int):
    _ensure_admin(user_id)
    return {"items": admin_notes_service.list_notes(target_id)}


@router.post("/api/admin/notes")
def admin_add_note(payload: AdminNotePayload):
    _ensure_admin(payload.user_id)
    record = admin_notes_service.add_note(payload.target_id, payload.note, admin_id=payload.user_id)
    return {
        "id": record.id,
        "user_id": record.user_id,
        "admin_id": record.admin_id,
        "note": record.note,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.delete("/api/admin/notes/{note_id}")
def admin_delete_note(note_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = admin_notes_service.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


@router.get("/api/admin/orders/{order_id}")
def admin_order_detail(order_id: int, user_id: int):
    _ensure_admin(user_id)
    order = orders_service.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/api/admin/orders/{order_id}/status")
@router.put("/api/admin/orders/{order_id}/status")
def admin_order_set_status(order_id: int, payload: AdminOrderStatusPayload):
    _ensure_admin(payload.user_id)
    if payload.status not in orders_service.STATUS_TITLES:
        raise HTTPException(status_code=400, detail="Invalid status")
    updated = orders_service.update_order_status(order_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders_service.get_order_by_id(order_id)


@router.get("/api/admin/promocodes")
def admin_promocodes(user_id: int):
    _ensure_admin(user_id)
    promos = promocodes_service.list_promocodes()
    return {"items": promos}


@router.post("/api/admin/promocodes")
def admin_create_promocode(payload: AdminPromocodeCreatePayload):
    _ensure_admin(payload.user_id)
    try:
        promo_data = payload.dict()
        promo_data.pop("user_id", None)
        promo = promocodes_service.create_promocode(promo_data)
    except ValueError as exc:  # noqa: WPS440
        raise HTTPException(status_code=400, detail=str(exc))
    return promo


@router.put("/api/admin/promocodes/{promocode_id}")
def admin_update_promocode(promocode_id: int, payload: AdminPromocodeUpdatePayload):
    _ensure_admin(payload.user_id)
    try:
        update_data = payload.dict()
        update_data.pop("user_id", None)
        updated = promocodes_service.update_promocode(promocode_id, update_data)
    except ValueError as exc:  # noqa: WPS440
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return updated


@router.delete("/api/admin/promocodes/{promocode_id}")
def admin_delete_promocode(promocode_id: int, user_id: int):
    _ensure_admin(user_id)
    deleted = promocodes_service.delete_promocode(promocode_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return {"ok": True}
