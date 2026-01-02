"""Integration test for serving uploaded media from /static/uploads without external HTTP clients."""

from __future__ import annotations

import asyncio
import base64
import os
import sys
from pathlib import Path
import unittest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("BOT_TOKEN", "test-bot-token")

from config import get_settings
from webapi import STATIC_DIR_PUBLIC, app


async def _call_app(path: str) -> tuple[int, dict[str, str], bytes]:
    response_body = bytearray()
    status: int | None = None
    headers: list[tuple[bytes, bytes]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        nonlocal status, headers, response_body
        if message["type"] == "http.response.start":
            status = int(message["status"])
            headers = list(message.get("headers", []))
        elif message["type"] == "http.response.body":
            response_body += message.get("body", b"")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
    }

    await app(scope, receive, send)
    return status or 500, {k.decode(): v.decode() for k, v in headers}, bytes(response_body)


def test_get_settings_accepts_telegram_bot_token(monkeypatch: object) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-from-telegram")

    settings = get_settings()

    assert settings.bot_token == "token-from-telegram"


class StaticUploadsTestCase(unittest.TestCase):
    def test_uploads_are_served(self) -> None:
        upload_dir = Path(STATIC_DIR_PUBLIC) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        sample_path = upload_dir / "test-upload.png"
        sample_content = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PXZo0wAAAABJRU5ErkJggg=="
        )

        sample_path.write_bytes(sample_content)
        try:
            status, headers, body = asyncio.run(
                _call_app(f"/static/uploads/{sample_path.name}")
            )
            self.assertEqual(status, 200)
            self.assertTrue(headers.get("content-type", "").startswith("image/"))
            self.assertEqual(body, sample_content)
        finally:
            sample_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
