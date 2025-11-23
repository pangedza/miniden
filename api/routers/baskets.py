from fastapi import APIRouter

from services import products as products_service

router = APIRouter(tags=["catalog"])


@router.get("/baskets")
def api_baskets():
    return products_service.list_products("basket")
