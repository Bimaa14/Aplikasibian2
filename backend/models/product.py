"""Product (barang / jasa) models. `service_fee` is the montir commission for jasa items."""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Product(BaseModel):
    category: Literal['TIRE', 'OIL', 'SERVICE', 'COMPLEMENTARY'] = 'TIRE'
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["barang", "jasa"]
    sku: str
    name: str
    brand: str = ""
    size: str = ""
    stock: int = Field(default=0, ge=0)
    cost_price: float = Field(default=0, ge=0, allow_inf_nan=False)
    selling_price: float = Field(default=0, ge=0, allow_inf_nan=False)
    service_fee: float = Field(default=0, ge=0, allow_inf_nan=False)


class ProductCreate(BaseModel):
    category: Literal['TIRE', 'OIL', 'SERVICE', 'COMPLEMENTARY'] = 'TIRE'
    type: Literal["barang", "jasa"]
    sku: str
    name: str
    brand: str = ""
    size: str = ""
    stock: int = Field(default=0, ge=0)
    cost_price: float = Field(default=0, ge=0, allow_inf_nan=False)
    selling_price: float = Field(default=0, ge=0, allow_inf_nan=False)
    service_fee: float = Field(default=0, ge=0, allow_inf_nan=False)

    @model_validator(mode='before')
    @classmethod
    def category_default(cls, data):
        if isinstance(data, dict) and 'category' not in data:
            data = {**data, 'category': 'SERVICE' if data.get('type') == 'jasa' else 'TIRE'}
        return data


class ProductUpdate(BaseModel):
    category: Optional[Literal['TIRE', 'OIL', 'SERVICE', 'COMPLEMENTARY']] = None
    type: Optional[Literal["barang", "jasa"]] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    size: Optional[str] = None
    stock: Optional[int] = Field(default=None, ge=0)
    cost_price: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    selling_price: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    service_fee: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
