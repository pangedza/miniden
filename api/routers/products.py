from fastapi import APIRouter

from services import products as products_service

router = APIRouter(tags=["catalog"])


@router.get("/products/baskets")
def api_baskets():
    return products_service.get_baskets()


@router.get("/products/courses")
def api_courses():
    return products_service.get_courses()
