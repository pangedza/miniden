"""
LEGACY ROUTER: не используется в продакшене.
Весь каталог корзин/наборов обслуживается через webapi.py (/api/products, /api/categories).
Файл оставлен только как архив/история.
"""

from fastapi import APIRouter

from services import products as products_service

router = APIRouter(tags=["catalog"])


@router.get("/baskets")
def api_baskets():
    return products_service.list_products("basket")
