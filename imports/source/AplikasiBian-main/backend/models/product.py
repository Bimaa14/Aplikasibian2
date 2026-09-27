"""Product (barang / jasa) models. `service_fee` is the montir commission for jasa items."""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["barang", "jasa"]
    sku: str
    name: str
    brand: str = ""
    size: str = ""
    stock: int = 0
    cost_price: float = 0
    selling_price: float = 0
    service_fee: float = 0


class ProductCreate(BaseModel):
    type: Literal["barang", "jasa"]
    sku: str
    name: str
    brand: str = ""
    size: str = ""
    stock: int = 0
    cost_price: float = 0
    selling_price: float = 0
    service_fee: float = 0


class ProductUpdate(BaseModel):
    type: Optional[Literal["barang", "jasa"]] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    size: Optional[str] = None
    stock: Optional[int] = None
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    service_fee: Optional[float] = None
