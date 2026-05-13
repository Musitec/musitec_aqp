from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class OrderItemGuest(BaseModel):
    product_id: str = Field(...)
    quantity: int = Field(..., gt=0)
    selected_option: Optional[str] = Field(None)


class CreateOrderGuestRequest(BaseModel):
    user_name: str = Field(...)
    user_email: EmailStr = Field(...)
    user_phone: str = Field(...)
    items: List[OrderItemGuest]

class UpdateStatusRequest(BaseModel):
    status: str