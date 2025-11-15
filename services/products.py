import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _load_json(filename: str) -> list[dict[str, Any]]:
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_baskets() -> list[dict[str, Any]]:
    return _load_json("products_baskets.json")


def get_courses() -> list[dict[str, Any]]:
    return _load_json("products_courses.json")
