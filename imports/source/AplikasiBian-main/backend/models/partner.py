"""Customer (pelanggan) and Supplier (distributor) models."""
import uuid

from pydantic import BaseModel, Field


class Customer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str = ""
    address: str = ""


class CustomerCreate(BaseModel):
    name: str
    phone: str = ""
    address: str = ""


class Supplier(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str = ""
    address: str = ""


class SupplierCreate(BaseModel):
    name: str
    phone: str = ""
    address: str = ""
