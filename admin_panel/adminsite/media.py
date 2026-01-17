from __future__ import annotations

import mimetypes
from pathlib import Path
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from media_paths import ADMIN_SITE_MEDIA_ROOT, MEDIA_ROOT, ensure_media_dirs


UPLOAD_DIR = ADMIN_SITE_MEDIA_ROOT
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 5 * 1024 * 1024


def _ensure_dir() -> None:
    ensure_media_dirs()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _build_file_url(filename: str) -> str:
    safe_name = filename.lstrip("/")
    return f"/media/{UPLOAD_DIR.relative_to(MEDIA_ROOT).as_posix()}/{safe_name}"


def list_media(query: str | None = None) -> list[dict[str, Any]]:
    _ensure_dir()
    if not UPLOAD_DIR.exists():
        return []

    items: list[dict[str, Any]] = []
    for file_path in UPLOAD_DIR.iterdir():
        if not file_path.is_file():
            continue

        stat = file_path.stat()
        items.append(
            {
                "name": file_path.name,
                "size": stat.st_size,
                "url": _build_file_url(file_path.name),
                "modified": stat.st_mtime,
            }
        )

    filtered = items
    if query:
        needle = query.lower().strip()
        filtered = [item for item in items if needle in item["name"].lower()]

    return sorted(filtered, key=lambda item: item["modified"], reverse=True)


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


async def save_upload(upload: UploadFile) -> dict[str, str]:
    from uuid import uuid4

    _ensure_dir()
    validation_error = _validate_upload(upload)
    if validation_error:
        raise HTTPException(status_code=422, detail=validation_error)

    data = await upload.read()
    if not data:
        raise HTTPException(status_code=422, detail="Файл пустой")

    if len(data) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=422, detail="Файл слишком большой. Лимит 5 МБ.")

    extension = Path(upload.filename or "").suffix.lower()
    target_name = f"{uuid4().hex}{extension}"
    target_path = (UPLOAD_DIR / target_name).resolve()

    try:
        target_path.write_bytes(data)
    except Exception as exc:  # pragma: no cover - защита от проблем с диском
        raise HTTPException(status_code=500, detail=str(exc))

    return {"url": _build_file_url(target_name), "filename": target_name}


def delete_media(filename: str) -> dict[str, str]:
    if not filename:
        raise HTTPException(status_code=422, detail="Не указано имя файла")

    target = (UPLOAD_DIR / filename).resolve()
    if not str(target).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=422, detail="Неверное имя файла")

    if target.exists():
        try:
            target.unlink()
        except Exception as exc:  # pragma: no cover - fail-safe
            raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "deleted"}


__all__ = ["list_media", "save_upload", "delete_media"]
