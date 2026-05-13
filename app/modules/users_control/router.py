from fastapi import APIRouter, Depends, Request
from app.modules.users_control import schemas,services
from app.modules.auth.dependencies import is_moderator
from typing import Optional

router = APIRouter(prefix="/api/users-control", tags=["users_control"])

@router.patch("/role")
async def change_user_role(request:Request, data:schemas.ChangeUserRoleRequest, user=Depends(is_moderator)):
    return await services.change_user_role(
        request=request,
        target_user_email=data.target_user_email,
        new_role=data.new_role,
        actor_email=user["email"],
        actor_role=user["role"]
    )

@router.patch("/block")
async def toggle_user_block(request:Request,data:schemas.ToggleUserBlockRequest, user=Depends(is_moderator)):
    return await services.toggle_user_block(
        request=request,
        target_user_email=data.target_user_email,
        block=data.block,
        actor_email=user["email"],
        actor_role=user["role"],
        minutes=data.minutes
    )

@router.get("/user/{user_id}")
async def get_user_by_id(request:Request,user_id:str, user=Depends(is_moderator)):
    return await services.get_user_by_id(
        request=request,
        user_id=user_id
    )

@router.get("/users")
async def get_users(
    request:Request,
    page: int = 0,
    limit: int = 8,
    search: Optional[str] = None,
    is_blocked: Optional[bool] = None,
    role: Optional[str] = None,
    user=Depends(is_moderator)
):
    return await services.get_users(
        request=request,
        page=page,
        limit=limit,
        search=search,
        is_blocked=is_blocked,
        role=role
    )