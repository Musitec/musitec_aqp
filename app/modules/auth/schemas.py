from pydantic import BaseModel, EmailStr, Field, validator, field_validator
from typing import Optional, Literal
from datetime import date
from enum import Enum
import re

class SexEnum(str, Enum):
    M = "male"
    F = "female"

class RegisterSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, min_length=6, max_length=20)
    birth_date: date
    sex: SexEnum
    @field_validator("birth_date")
    @classmethod
    def validate_age(cls, birth_date: date):
        today = date.today()
        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
        if age < 18:
            raise ValueError("Debes ser mayor de 18 años para registrarte")
        return birth_date

class ResendPinSchema(BaseModel):
    email: EmailStr

class VerifyPinSchema(BaseModel):
    email: EmailStr
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")

class SetPasswordSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    @validator("password")
    def validate_password(cls, v):
        if " " in v:
            raise ValueError("La contraseña no puede contener espacios")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos un número")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("La contraseña debe contener al menos un símbolo especial")
        return v

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "password" in values and v != values["password"]:
            raise ValueError("Las contraseñas no coinciden")
        return v

class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: Optional[str]
    age: int
    sex: SexEnum
    is_verified: bool

class UpdateProfileSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=5, max_length=20)
    sex: Optional[Literal["male", "female"]] = None
    @field_validator("name")
    @classmethod
    def strip_name(cls, v):
        return v.strip() if v else v
    @field_validator("phone")
    @classmethod
    def strip_phone(cls, v):
        return v.strip() if v else v