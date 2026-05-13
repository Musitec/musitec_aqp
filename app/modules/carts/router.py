from app.modules.auth.dependencies import is_client
from app.modules.carts import services
from app.modules.carts.schemas import (AddToCartSchema, UpdateCartItemSchema, RemoveCartItemSchema)
from fastapi import APIRouter, Depends, Body

router = APIRouter(prefix="/api/cart", tags=["Cart"])

@router.get("/")
async def get_cart(user=Depends(is_client)):
    return await services.get_my_cart(user_id=str(user["id"]))

@router.post("/items")
async def add_to_cart(
    data: AddToCartSchema,
    user=Depends(is_client)
):
    return await services.add_item_to_cart(
        user_id=str(user["id"]),
        product_id=data.product_id,
        quantity=data.quantity,
        selected_option=data.selected_option
    )

@router.patch("/items")
async def update_cart_item(
    data: UpdateCartItemSchema,
    user=Depends(is_client)
):
    return await services.update_cart_item(
        user_id=str(user["id"]),
        product_id=data.product_id,
        quantity=data.quantity,
        selected_option=data.selected_option
    )

@router.delete("/items/{product_id}")
async def remove_cart_item(
    product_id: str,
    data: RemoveCartItemSchema = Body(...),
    user=Depends(is_client)
):
    return await services.remove_cart_item(
        user_id=str(user["id"]),
        product_id=product_id,
        selected_option=data.selected_option
    )

@router.delete("/clear")
async def clear_cart(user=Depends(is_client)):
    return await services.clear_cart(user_id=str(user["id"]))