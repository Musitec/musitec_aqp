from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional

from .repository import (
    get_product_by_id,
    increment_clicks,
    increment_search_hits,
    get_active_discounted_products,
    get_catalog_products,
    get_top_popular_products
)
from .similary import get_similar_products
from .utils import serialize_product

router = APIRouter(prefix="/api/products", tags=["Products"])
@router.post("/{product_id}")
async def product_interaction(
    product_id: str,
    request: Request,
    from_search: bool = Query(False)
):
    tz = request.state.tz
    product = await get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if not product.get("is_active", False):
        raise HTTPException(status_code=403, detail="Producto no activo")
    if product.get("is_blocked", False):
        raise HTTPException(status_code=403, detail="Producto bloqueado")
    await increment_clicks(product_id)
    if from_search:
        await increment_search_hits(product_id)
    similar_products = await get_similar_products(product)
    return {
        "product": await serialize_product(product, tz),
        "similar_products": [
            await serialize_product(p, tz) for p in similar_products
        ]
    }

@router.get("/discounts")
async def discounted_products(request: Request):
    tz = request.state.tz
    products = await get_active_discounted_products()
    return {
        "count": len(products),
        "products": [
            await serialize_product(p, tz) for p in products
        ]
    }

@router.get("/catalog")
async def catalog_products(
    request: Request,
    page: int = 0,
    catalog: str = "all",
    discount: str = "all",
    order: str = "popular",
    query_text: Optional[str] = None
):
    tz = request.state.tz
    data = await get_catalog_products(
        query_text=query_text.strip() if query_text else None,
        page=page,
        catalog=catalog,
        discount=discount,
        order=order
    )
    return {
        "products": [
            await serialize_product(p, tz) for p in data["products"]
        ],
        "total_products": data["total"],
        "max_pages": data["max_pages"],
        "catalogs": data["catalogs"]
    }

@router.get("/top/{n}")
async def top_popular_products(n: int, request: Request):
    tz = request.state.tz
    products = await get_top_popular_products(n)
    return {
        "count": len(products),
        "products": [
            await serialize_product(p, tz) for p in products
        ]
    }