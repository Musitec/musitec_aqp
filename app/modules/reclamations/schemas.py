from pydantic import BaseModel, EmailStr, field_validator, Field
from typing import Optional, List, Dict
from enum import Enum
import re

class ReclamationStatus(str, Enum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    rejected = "rejected"

class DocumentType(str, Enum):
    DNI = "dni"
    CE = "ce"
    PASAPORTE = "pasaporte"
    RUC = "ruc"
    BREVETE = "brevete"

class ReclamationType(str, Enum):
    RECLAMO = "reclamo"
    QUEJA = "queja"

class ReclamationProduct(BaseModel):
    product_id: str = Field(..., description="ID del producto")
    selected_option: Optional[str] = Field(None, description="Opción seleccionada")
    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, v):
        if not v or not v.strip():
            raise ValueError("El product_id es obligatorio")
        return v.strip()

class CreateReclamation(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    lastname: str = Field(min_length=2, max_length=50)
    user_email: EmailStr
    document_type: DocumentType
    document_number: str
    reclamation_type: ReclamationType
    address: str = Field(min_length=5, max_length=150)
    phone: str = Field(min_length=6, max_length=20)
    claimed_amount: Optional[float] = Field(
        default=None,
        ge=0,
        description="Monto reclamado (opcional)"
    )
    customer_request: str = Field(
        min_length=5,
        max_length=500,
        description="Qué solicita el cliente"
    )
    code: str = Field(
        ...,
        description="Código de la orden"
    )
    products: List[ReclamationProduct] = Field(default_factory=list)
    reason: str = Field(
        min_length=5,
        max_length=500,
        description="Motivo del reclamo"
    )
    @field_validator("document_number")
    @classmethod
    def validate_document_number(cls, v, info):
        document_type = info.data.get("document_type")
        if document_type == DocumentType.DNI:
            if len(v) != 8 or not v.isdigit() or v[0] == '0':
                raise ValueError("DNI inválido")
        elif document_type == DocumentType.RUC:
            if len(v) != 11 or not v.isdigit():
                raise ValueError("RUC inválido")
        elif document_type == DocumentType.CE:
            if len(v) > 12 or not re.match(r'^[A-Z0-9]{1,12}$', v, re.IGNORECASE):
                raise ValueError("CE inválido")
        elif document_type == DocumentType.PASAPORTE:
            if not (6 <= len(v) <= 12):
                raise ValueError("Pasaporte inválido")
            if not (re.search(r'[A-Za-z]', v) and re.search(r'\d', v)):
                raise ValueError("Debe tener letras y números")
        elif document_type == DocumentType.BREVETE:
            if not re.match(r'^[A-Z0-9]{6,12}$', v):
                raise ValueError("Brevete inválido")
        return v.strip().upper()
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r'^\+?\d{6,20}$', v):
            raise ValueError("Teléfono inválido")
        return v.strip()
    @field_validator("products")
    @classmethod
    def validate_products(cls, v):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("Products debe ser una lista")
        if len(v) > 20:
            raise ValueError("Máximo 20 productos")
        return v

class UpdateReclamation(BaseModel):
    status: ReclamationStatus
    message: str = Field(min_length=3, max_length=500)
    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El mensaje es obligatorio")
        import re
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("El mensaje debe contener texto válido")

        return v
    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v
