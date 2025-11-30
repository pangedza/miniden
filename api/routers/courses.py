"""
LEGACY ROUTER — старый API.
Не используется. Оставлен только как архив.
"""

from fastapi import APIRouter

from services import products as products_service

router = APIRouter(tags=["catalog"])


@router.get("/courses")
def api_courses():
    return products_service.list_products("course")
