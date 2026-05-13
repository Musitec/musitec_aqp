from pydantic import BaseModel, Field,field_validator
from typing import Optional, List, Union
from fastapi import Form

class CreateProduct(BaseModel):
    catalog: str
    product_name: str
    specifications: str
    description: str
    price: Optional[float] = None
    stock: Optional[str] = None
    variants: Optional[str] = None
    @field_validator("price")
    def validate_price(cls, v):
        if v is not None and v < 0:
            raise ValueError("price no puede ser negativo")
        return v
    @field_validator("stock")
    def validate_stock(cls, v):
        if v is None:
            return v
        try:
            value = int(v)
        except:
            raise ValueError("stock debe ser un número")
        if value < 0:
            raise ValueError("stock no puede ser negativo")
        return v
    @classmethod
    def as_form(
        cls,
        catalog: str = Form(...),
        product_name: str = Form(...),
        specifications: str = Form(...),
        description: str = Form(...),
        price: Optional[float] = Form(None),
        stock: Optional[str] = Form(None),
        variants: Optional[str] = Form(None)
    ):
        return cls(
            catalog=catalog,
            product_name=product_name,
            specifications=specifications,
            description=description,
            price=price,
            stock=stock,
            variants=variants
        )

class CreateDiscount(BaseModel):
    discount: int = Field(gt=0, le=40)
    days: int = Field(ge=0, le=7)
    hours: int = Field(ge=0, le=23)
    minutes: int = Field(ge=0, le=59)

class StockChangeItem(BaseModel):
    option: str
    delta: int
    @field_validator("option")
    def validate_option(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("option inválido")
        return v.strip()
    @field_validator("delta")
    def validate_delta(cls, v):
        if not isinstance(v, int):
            raise ValueError("delta debe ser un número")
        if v == 0:
            raise ValueError("delta no puede ser 0")
        return v

class ChangeStock(BaseModel):
    stock: Union[int, List[StockChangeItem]]
    @field_validator("stock")
    def validate_stock(cls, value):
        if isinstance(value, int):
            if value == 0:
                raise ValueError("El cambio de stock no puede ser 0")
            return value
        if isinstance(value, list):
            if not value:
                raise ValueError("El array no puede estar vacío")
            seen = set()
            for i, item in enumerate(value):
                key = item.option.lower()
                if key in seen:
                    raise ValueError(f"option duplicada: {item.option}")
                seen.add(key)
            return value
        raise ValueError("Formato de stock inválido")