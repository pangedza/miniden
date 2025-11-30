"""
Legacy shim: основной backend — webapi.app.
Файл оставлен ради совместимости. В продакшене запускать uvicorn webapi:app.
"""
from webapi import app

__all__ = ["app"]
