from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional

VALID_ROLES = {"client", "moderator", "admin"}

class ChangeUserRoleRequest(BaseModel):
    target_user_email: EmailStr
    new_role: str

    @field_validator("new_role")
    @classmethod
    def validate_role(cls, v):
        if v not in VALID_ROLES:
            raise ValueError(f"Rol inválido. Permitidos: {', '.join(VALID_ROLES)}")
        return v

class ToggleUserBlockRequest(BaseModel):
    target_user_email: EmailStr
    block: bool
    minutes: Optional[int] = None
    @field_validator("minutes")
    @classmethod
    def validate_minutes(cls, v, info):
        block = info.data.get("block")
        if v is not None and v <= 0:
            raise ValueError("minutes debe ser mayor a 0")
        if not block and v is not None:
            raise ValueError("No debes enviar minutes al desbloquear")
        return v