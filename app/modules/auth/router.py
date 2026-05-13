from fastapi import APIRouter, Depends, Response, Request
from app.modules.auth import service
from datetime import date
from app.modules.auth.schemas import (
    RegisterSchema,
    ResendPinSchema,
    VerifyPinSchema,
    SetPasswordSchema,
    LoginSchema,
    UpdateProfileSchema,
)
from app.modules.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/register")
async def register(data: RegisterSchema, request:Request):
    return await service.register_user(
        name=data.name,
        email=data.email,
        phone=data.phone,
        date=data.birth_date,
        sex=data.sex,
        request=request
    )

@router.post("/resend-pin")
async def resend_pin(data: ResendPinSchema, request:Request):
    return await service.resend_pin(data.email,request)

@router.post("/verify-pin")
async def verify_pin(data: VerifyPinSchema,request:Request):
    return await service.verify_pin(data.email, data.pin, request)

@router.post("/set-password")
async def set_password(
    data: SetPasswordSchema,
    response: Response,
    request: Request,
):
    return await service.set_password(
        response=response,
        email=data.email,
        password=data.password,
        confirm_password=data.confirm_password,
        request=request,
    )

@router.post("/login")
async def login(
    data: LoginSchema,
    response: Response,
    request: Request,
):
    return await service.login(
        response=response,
        email=data.email,
        password=data.password,
        request=request,
    )

@router.get("/me")
async def me(user=Depends(get_current_user)):
    birth_date = user["date"]
    if hasattr(birth_date, "date"):
        birth_date = birth_date.date()
    today = date.today()
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "phone": user["phone"],
        "age": age,
        "sex": user["sex"],
        "role": user["role"]
    }

@router.post("/refresh")
async def refresh(response: Response, request: Request):
    return await service.refresh_token(response, request)

@router.post("/logout")
async def logout(response: Response, request: Request):
    return await service.logout_current(response, request)

@router.post("/logout-all")
async def logout_all(response: Response, request: Request):
    return await service.logout_all(response, request)

@router.post("/start-change")
async def start_change(request: Request, data: ResendPinSchema):
    return await service.start_password_reset(data.email, request)

@router.post("/resend-change")
async def resend_change(request: Request,data: ResendPinSchema):
    return await service.resend_password_reset_pin(data.email, request)

@router.post("/verify-reset-pin")
async def verify_resend_pin(data: VerifyPinSchema, request: Request):
    return await service.verify_password_reset_pin(data.email, data.pin, request)

@router.post("/change-password")
async def change_password(data: SetPasswordSchema,response: Response, request: Request):
    return await service.confirm_password_reset(data.email, data.password, data.confirm_password, response, request)

@router.patch("/users/me")
async def update_user(data: UpdateProfileSchema, user=Depends(get_current_user)):
    return await service.update_user_data(data=data.model_dump(exclude_none=True),user_id=str(user["id"]))