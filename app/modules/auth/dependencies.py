from fastapi import HTTPException, status, Request, Depends
from app.core.security import decode_token, get_token_from_request
from app.modules.auth import repository
from datetime import datetime, timezone

VALID_ROLES = {"client", "moderator", "admin"}

async def get_current_user(request: Request):
    token = get_token_from_request(request)
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    session = await repository.get_session_by_id(session_id)
    if not session or not session.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida")
    user = await repository.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no existe")
    now = datetime.now(timezone.utc)
    if user.get("is_blocked"):
        blocked_until = user.get("blocked_until")
        if blocked_until:
            if now >= blocked_until:
                await repository.update_user_block_status(
                    email=user["email"],
                    is_blocked=False,
                    now=now,
                    blocked_until=None
                )
                user["is_blocked"] = False
                user["blocked_until"] = None
            else:
                await repository.deactivate_all_sessions(user_id)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Usuario bloqueado hasta {blocked_until.isoformat()}"
                )
        else:
            await repository.deactivate_all_sessions(user_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario bloqueado"
            )
    return user

async def is_client(user=Depends(get_current_user)):
    if user["role"]!="client":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apartado solo para clientes")
    return user

async def is_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores")
    return user

async def is_moderator(user=Depends(get_current_user)):
    if user["role"] not in ["moderator", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo moderadores")
    return user

async def is_staff(user=Depends(get_current_user)):
    if user["role"] not in {"admin", "moderator"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
    return user