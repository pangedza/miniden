"""Утилиты для безопасного чтения хвоста файлов логов."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from utils.logging_config import LOG_DIR


def _validate_within_logs(path: Path) -> Path:
    resolved = path.resolve()
    if LOG_DIR not in resolved.parents and resolved != LOG_DIR:
        raise ValueError("Чтение логов разрешено только из /opt/miniden/logs")
    return resolved


def read_tail(file_path: Path, limit: int = 200, *, max_bytes: int = 1_000_000) -> tuple[list[str], bool]:
    """
    Возвращает последние ``limit`` строк файла.

    Если файл отсутствует, возвращает пустой список и флаг not_found=True.
    Чтение ограничено ``max_bytes`` с конца файла, чтобы не загружать всё целиком.
    """

    normalized_limit = max(1, min(limit, 2000))
    normalized_path = _validate_within_logs(file_path)

    if not normalized_path.exists():
        return [], True

    try:
        with normalized_path.open("rb") as handler:
            handler.seek(0, os.SEEK_END)
            file_size = handler.tell()
            read_size = min(file_size, max_bytes)
            handler.seek(-read_size, os.SEEK_END)
            chunk = handler.read(read_size)
    except OSError:
        return [], True

    text = chunk.decode("utf-8", errors="replace")
    lines: Iterable[str] = text.splitlines()
    tail = list(lines)[-normalized_limit:]
    return tail, False
