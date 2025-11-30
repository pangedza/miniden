"""
LEGACY ROUTER: не используется в продакшене.
Курсы обслуживаются через webapi.py (/api/products, /api/categories).
Файл оставлен только как архив/история.
"""

from fastapi import APIRouter

from services import products as products_service

router = APIRouter(tags=["catalog"])


@router.get("/courses")
def api_courses():
    return products_service.list_products("course")
