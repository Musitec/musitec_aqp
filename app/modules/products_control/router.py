from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from app.modules.auth.dependencies import is_staff
from app.modules.products_control import services, schemas
from app.core.convert_date import convert_dates
from typing import Optional,List
from app.modules.products.utils import serialize_product

router = APIRouter(prefix="/api/product-control", tags=["Product_Control"])

@router.post("/product")
async def create_product(
    request: Request,
    data: schemas.CreateProduct = Depends(schemas.CreateProduct.as_form),
    files: list[UploadFile] = File(...),
    user=Depends(is_staff)
):
    return await services.create_product(
        user_id=str(user["id"]),
        email=user["email"],
        role=user["role"],
        files=files,
        catalog=data.catalog,
        product_name=data.product_name,
        specifications=data.specifications,
        description=data.description,
        price=data.price,
        stock=data.stock,
        variants=data.variants,
        request=request
    )

@router.get("/product-get/{product_id}")
async def get_product(
    request: Request,
    product_id: str,
    user: dict = Depends(is_staff)
):
    product = await services.get_product_or_404(product_id=product_id)
    product = await serialize_product(product, request.state.tz)
    product = convert_dates(product, request.state.tz)
    return product

@router.put("/product/{product_id}")
async def update_product(
    request: Request,
    product_id: str,
    catalog: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    stock: Optional[str] = Form(None),
    specifications: Optional[str] = Form(None),
    variants: Optional[str] = Form(None),
    remove_images: Optional[str] = Form(None),
    replace_images: Optional[bool] = Form(False),
    image_order: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    tempIds: Optional[List[str]] = Form(None),
    user: dict = Depends(is_staff)
):
    return await services.update_product(
        request=request,
        product_id=product_id,
        email=user["email"],
        role=user["role"],
        name=name,
        description=description,
        catalog=catalog,
        price=price,
        stock=stock,
        specifications=specifications,
        variants=variants,
        removeImages=remove_images,
        replaceImages=replace_images,
        imageOrder=image_order,
        tempIds=tempIds,
        files=files
    )

@router.patch("/product/{product_id}/discount")
async def create_discount(
    request: Request,
    product_id: str,
    data: schemas.CreateDiscount,
    user=Depends(is_staff)
):
    return await services.create_discount(
        role=user["role"],
        email=user["email"],
        user_id=str(user["id"]),
        product_id=product_id,
        discount=data.discount,
        days=data.days,
        hours=data.hours,
        minutes=data.minutes,
        request=request
    )

@router.patch("/product/{product_id}/stock")
async def change_stock(
    request: Request,
    product_id: str,
    data: schemas.ChangeStock,
    user=Depends(is_staff)
):
    return await services.change_stock(
        role=user["role"],
        email=user["email"],
        user_id=str(user["id"]),
        product_id=product_id,
        stock=data.stock,
        request=request
    )

@router.patch("/product/{product_id}/block")
async def block_product(
    request: Request,
    product_id: str,
    user=Depends(is_staff)
):
    return await services.block_product(
        role=user["role"],
        email=user["email"],
        user_id=str(user["id"]),
        product_id=product_id,
        request=request
    )

@router.patch("/product/{product_id}/unblock")
async def unblock_product(
    request: Request,
    product_id: str,
    user=Depends(is_staff)
):
    return await services.unblock_product(
        role=user["role"],
        email=user["email"],
        user_id=str(user["id"]),
        product_id=product_id,
        request=request
    )

@router.patch("/product/{product_id}/deactivate")
async def deactivate_product(
    request: Request,
    product_id: str,
    user=Depends(is_staff)
):
    return await services.deactivate_product(
        role=user["role"],
        email=user["email"],
        user_id=str(user["id"]),
        product_id=product_id,
        request=request
    )

@router.patch("/product/{product_id}/activate")
async def activate_product(
    request: Request,
    product_id: str,
    user=Depends(is_staff)
):
    return await services.activate_product(
        role=user["role"],
        email=user["email"],
        user_id=str(user["id"]),
        product_id=product_id,
        request=request
    )

@router.get("/product/dashboard")
async def get_dashboard(
    request:Request,
    blocked:bool=False,
    active:bool=True,
    low_stock:bool=False,
    out_of_stock:bool=False,
    with_discount:bool=False,
    order:str="popular",
    search:str="",
    page:int=0,
    page_size:int=8,
    user=Depends(is_staff)
):
    return await services.products_dashboard(
        request=request,
        blocked=blocked,
        active=active,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        with_discount=with_discount,
        order=order,
        search=search,
        page=page,
        page_size=page_size
    )