from app.modules.users_control import repository as users_repository
from app.modules.auth import repository as auth_repository
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status, Request
from pydantic import EmailStr
from bson import ObjectId
from bson.errors import InvalidId
from typing import Optional
from app.core.config import settings
from app.core.convert_date import convert_dates

VALID_ROLES = {"client", "moderator", "admin"}

def roles_traductor(role):
    if role=="client":
        return "cliente"
    elif role=="moderator":
        return "moderador"
    else:
        return "administrador"

def preserve_dates(user,tz):
    user = dict(user)
    raw_date = user.get("date")
    user = convert_dates(user, tz)
    if raw_date:
        if isinstance(raw_date, datetime):
            user["date"] = raw_date.date().isoformat()
        else:
            user["date"] = raw_date

    return user

def serialize_users(user):
    user = dict(user)
    user.pop("password_hash", None)
    return user

async def change_user_role(
    request: Request,
    target_user_email: EmailStr,
    new_role: str,
    actor_email: EmailStr,
    actor_role: str
):
    if target_user_email == settings.EMAIL_USER:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Este correo no puede cambiar de rol"
        )
    if target_user_email == actor_email:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Un usuario no puede cambiar de rol por si mismo"
        )
    if new_role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol inválido. Permitidos: {', '.join(VALID_ROLES)}"
        )
    user = await auth_repository.get_user_by_email(target_user_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    old_role = user.get("role")
    if old_role == new_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya tiene ese rol"
        )
    now = datetime.now(timezone.utc)
    updated = await users_repository.update_user_role(
        email=target_user_email,
        new_role=new_role,
        now=now
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el rol"
        )
    await users_repository.add_user_history(
        email=actor_email,
        action="CHANGE_USER_ROLE",
        message=f"Cambió rol de {target_user_email} de {roles_traductor(old_role)} → {roles_traductor(new_role)}",
        request=request,
        role=actor_role,
        entity="user",
        entity_id=target_user_email,
        now=now,
        extra={
            "old_role": old_role,
            "new_role": new_role
        }
    )
    await users_repository.add_user_history(
        email=target_user_email,
        action="ROLE_UPDATED",
        message=f"Tu rol fue cambiado de {roles_traductor(old_role)} → {roles_traductor(new_role)}",
        request=request,
        role=new_role,
        entity="user",
        entity_id=target_user_email,
        now=now,
        extra={
            "changed_by": actor_email,
            "old_role": old_role,
            "new_role": new_role
        }
    )
    return {"message": "Rol actualizado correctamente"}

async def toggle_user_block(
    request: Request,
    target_user_email: EmailStr,
    block: bool,
    actor_email: EmailStr,
    actor_role: str,
    minutes: Optional[int] = None
):
    if block and not minutes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes especificar minutos para bloquear"
        )
    if target_user_email == settings.EMAIL_USER:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Este usuario no puede ser bloqueado"
        )
    if target_user_email == actor_email:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Los usuarios no pueden bloquearse a si mismo"
        )
    user = await auth_repository.get_user_by_email(target_user_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    now = datetime.now(timezone.utc)
    blocked_until = None
    if block and minutes:
        blocked_until = now + timedelta(minutes=minutes)
    updated = await users_repository.update_user_block_status(
        email=target_user_email,
        is_blocked=block,
        now=now,
        blocked_until=blocked_until
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el estado del usuario"
        )
    await users_repository.add_user_history(
        email=actor_email,
        action="BLOCK_USER" if block else "UNBLOCK_USER",
        message=(
            f"Bloqueó al usuario {target_user_email}"
            if block
            else f"Desbloqueó al usuario {target_user_email}"
        ),
        request=request,
        role=actor_role,
        entity="user",
        entity_id=target_user_email,
        now=now,
        extra={
            "blocked_until": (
                blocked_until.isoformat()
                if blocked_until else None
            )
        }
    )
    await users_repository.add_user_history(
        email=target_user_email,
        action="USER_BLOCKED" if block else "USER_UNBLOCKED",
        message=(
            "Tu cuenta fue bloqueada"
            if block
            else "Tu cuenta fue desbloqueada"
        ),
        request=request,
        role=user.get("role", "client"),
        entity="user",
        entity_id=target_user_email,
        now=now,
        extra={
            "blocked_until": (
                blocked_until.isoformat()
                if blocked_until else None
            ),
            "changed_by": actor_email
        }
    )
    return {
        "message": (
            "Usuario bloqueado correctamente"
            if block
            else "Usuario desbloqueado correctamente"
        )
    }

async def get_user_by_id(user_id: str, request:Request):
    try:
        obj_id = ObjectId(user_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID inválido"
        )
    user = await users_repository.get_user_by_id(obj_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    user=serialize_users(user)
    return preserve_dates(user, request.state.tz)

async def get_users(
    request:Request,
    page: int = 0,
    limit: int = 8,
    search: Optional[str] = None,
    is_blocked: Optional[bool] = None,
    role: Optional[str] = None
):
    if page < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Página inválida"
        )
    if limit <= 0 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Límite inválido (1-100)"
        )
    if role and role not in VALID_ROLES and role != "staff":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol inválido"
        )
    result = await users_repository.get_users(
        page=page,
        limit=limit,
        search=search,
        is_blocked=is_blocked,
        role=role
    )
    result["data"] = [
        serialize_users(preserve_dates(user, request.state.tz))
        for user in result.get("data", [])
    ]
    return result