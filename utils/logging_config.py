"""Общая настройка логирования для API и Telegram-бота."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("/opt/miniden/logs")
API_LOG_FILE = LOG_DIR / "app.log"
BOT_LOG_FILE = LOG_DIR / "bot.log"


def _build_file_handler(path: Path, max_bytes: int = 5_000_000, backups: int = 3) -> RotatingFileHandler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    return handler


def setup_logging(level: int = logging.INFO, *, log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    file_handler: RotatingFileHandler | None = None
    if log_file:
        file_handler = _build_file_handler(log_file)
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )

    if file_handler:
        for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)
            logger.addHandler(file_handler)
