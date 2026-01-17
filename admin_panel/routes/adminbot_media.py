"""Загрузка и управление медиа в AdminBot."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from admin_panel import TEMPLATES
from admin_panel.dependencies import get_db_session, require_admin
from models.admin_user import AdminRole
from media_paths import ADMIN_BOT_MEDIA_ROOT, MEDIA_ROOT, ensure_media_dirs

router = APIRouter(tags=["AdminBot"])


ALLOWED_ROLES = (AdminRole.superadmin, AdminRole.admin_bot, AdminRole.moderator)
UPLOAD_DIR = ADMIN_BOT_MEDIA_ROOT
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 5 * 1024 * 1024


def _login_redirect(next_url: str | None = None) -> RedirectResponse:
    target = next_url or "/adminbot"
    return RedirectResponse(url=f"/adminbot/login?next={target}", status_code=303)


def _ensure_dir() -> None:
    ensure_media_dirs()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _build_file_url(filename: str) -> str:
    safe_name = filename.lstrip("/")
    return f"/media/{UPLOAD_DIR.relative_to(MEDIA_ROOT).as_posix()}/{safe_name}"


def _list_files() -> list[dict]:
    if not UPLOAD_DIR.exists():
        return []

    files: list[dict] = []
    for item in UPLOAD_DIR.iterdir():
        if not item.is_file():
            continue
        stat = item.stat()
        files.append(
            {
                "name": item.name,
                "size": stat.st_size,
                "url": _build_file_url(item.name),
                "modified": stat.st_mtime,
            }
        )

    return sorted(files, key=lambda f: f["modified"], reverse=True)


@router.get("/media")
async def media_manager(request: Request, db: Session = Depends(get_db_session)):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(request.url.path)

    files = _list_files()
    return TEMPLATES.TemplateResponse(
        "adminbot_media.html",
        {"request": request, "user": user, "files": files},
    )


def _validate_upload(upload: UploadFile) -> str | None:
    filename = upload.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return "Разрешены только изображения (jpg, jpeg, png, webp)."

    content_type = (upload.content_type or "").split(";")[0].strip()
    guessed, _ = mimetypes.guess_type(filename)
    if content_type and content_type not in ALLOWED_MIMES:
        return "Тип файла не похож на изображение."
    if guessed and guessed not in ALLOWED_MIMES:
        return "Файл не похож на изображение."
    return None


@router.post("/media/upload")
async def upload_media(
    request: Request, file: UploadFile = File(...), db: Session = Depends(get_db_session)
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Требуется авторизация"})

    _ensure_dir()
    validation_error = _validate_upload(file)
    if validation_error:
        return JSONResponse(status_code=422, content={"error": validation_error})

    data = await file.read()
    if not data:
        return JSONResponse(status_code=422, content={"error": "Файл пустой"})

    if len(data) > MAX_SIZE_BYTES:
        return JSONResponse(
            status_code=422,
            content={"error": "Файл слишком большой. Лимит 5 МБ."},
        )

    ext = Path(file.filename or "").suffix.lower()
    safe_name = f"{uuid4().hex}{ext}"
    target_path = UPLOAD_DIR / safe_name

    try:
        target_path.write_bytes(data)
    except Exception as exc:  # pragma: no cover - защита от проблем с диском
        return JSONResponse(
            status_code=500,
            content={"error": f"Не удалось сохранить файл: {exc}"},
        )

    return {"url": _build_file_url(safe_name), "filename": safe_name}


@router.post("/media/delete")
async def delete_media(
    request: Request,
    filename: str = Form(...),
    db: Session = Depends(get_db_session),
):
    user = require_admin(request, db, roles=ALLOWED_ROLES)
    if not user:
        return _login_redirect(request.url.path)

    target = (UPLOAD_DIR / filename).resolve()
    if not str(target).startswith(str(UPLOAD_DIR.resolve())):
        return JSONResponse(status_code=422, content={"error": "Неверное имя файла"})

    if target.exists():
        try:
            target.unlink()
        except Exception as exc:  # pragma: no cover - fail-safe
            return JSONResponse(status_code=500, content={"error": str(exc)})

    return RedirectResponse(url="/adminbot/media", status_code=303)
