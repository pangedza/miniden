from fastapi import APIRouter, HTTPException, Query

from services import products as products_service

router = APIRouter(tags=["catalog"])

ALLOWED_TYPES = {"basket", "course"}


def _validate_type(product_type: str) -> str:
    if product_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="type must be 'basket' or 'course'")
    return product_type


@router.get("/categories")
def api_categories(type: str = Query(..., description="basket или course")):
    product_type = _validate_type(type)
    return products_service.list_categories(product_type)


@router.get("/products")
def api_products(type: str = Query(..., description="basket или course"), category_slug: str | None = None):
    product_type = _validate_type(type)
    return products_service.list_products(product_type, category_slug)


@router.get("/products/{product_id}")
def api_product_detail(product_id: int):
    product = products_service.get_product_with_category(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive")
    return product
