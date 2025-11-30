"""
Legacy shim: основной backend — webapi.app.
Файл оставлен только для совместимости с возможными старыми командами.
В продакшене использовать uvicorn webapi:app.
"""

from webapi import app

__all__ = ["app"]
