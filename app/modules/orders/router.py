from app.modules.auth.dependencies import is_client,is_staff, get_current_user
from app.modules.orders import services
from fastapi import APIRouter, Depends, Request
from typing import Optional
from app.modules.orders import schemas

router = APIRouter(prefix="/api/checkout", tags=["Checkout"])

@router.post("/anonymous")
async def create_order_guest(data: schemas.CreateOrderGuestRequest):
    return await services.create_order_guest(
        user_name=data.user_name,
        user_email=data.user_email,
        user_phone=data.user_phone,
        items_input=[item.dict() for item in data.items]
    )

@router.post("/")
async def checkout(request:Request,user=Depends(is_client)):
    return await services.checkout(
        user_id=str(user["id"]),
        user_name=user["name"],
        user_email=user["email"],
        user_phone=user["phone"],
        role=user["role"],
        request=request
    )

@router.get("/my")
async def get_my_orders(request:Request,page:int=0, user=Depends(is_client)):
    return await services.get_my_orders(
        request=request,
        page=page,
        user_id=str(user["id"])
    )

@router.patch("/{code}/status")
async def update_status(request:Request, code: str, data: schemas.UpdateStatusRequest,user=Depends(is_staff)):
    return await services.update_order_status(
        user_id=str(user["id"]),
        email=user["email"],
        role=user["role"],
        code=code,
        new_status=data.status,
        request=request
    )

@router.get("/{code}/view")
async def get_order(request:Request,code:str, user=Depends(get_current_user)):
    return await services.get_order(
        request=request,
        user_id=str(user["id"]),
        code=code,
        role=user["role"]
    )

@router.patch("/{code}/cancel")
async def cancel_order(request:Request, code: str, user=Depends(is_client)):
    return await services.cancel_order(
        user_id=str(user["id"]),
        role=user["role"],
        code=code,
        email=user["email"],
        request=request
    )

@router.delete("/{code}/delete")
async def delete_order(code:str, user=Depends(is_client)):
    return await services.erase_order(
        code=code,
        user_id=str(user["id"]),
        user_email=user["email"],
    )

@router.patch("/{code}/restore")
async def restore_order(code:str, user=Depends(is_staff)):
    return await services.restore_order(
        code=code,
        email=user["email"]
    )

@router.get("/orders")
async def get_all_orders(
    request:Request,
    page: int = 0,
    page_size: int = 8,
    email_user: Optional[str] | None = None,
    code: Optional[str] | None = None,
    erased: str = "normal",
    user=Depends(is_staff)
):
    return await services.get_orders(
        request=request,
        page=page,
        page_size=page_size,
        email_user=email_user,
        code=code,
        erased=erased
    )