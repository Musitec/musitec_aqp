from pydantic import BaseModel, Field
from typing import Optional

class AddToCartSchema(BaseModel):
    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    selected_option: Optional[str] = None

class UpdateCartItemSchema(BaseModel):
    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    selected_option: Optional[str] = None

class RemoveCartItemSchema(BaseModel):
    selected_option: Optional[str] = None