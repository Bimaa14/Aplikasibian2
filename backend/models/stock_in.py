"""Stok masuk (barang masuk dari distributor) — satu form multi-item.

Efek satu transaksi stok masuk: stok barang naik, cost_price (modal) produk diperbarui,
dan satu baris hutang (accounts_payable) dibuat otomatis.
"""
import uuid
from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, Field


class StockInItemCreate(BaseModel):
    product_id: str
    qty: int = Field(gt=0)
    cost_price: float = Field(ge=0, allow_inf_nan=False)  # modal per unit saat pembelian ini


class StockInCreate(BaseModel):
    invoice_date: Optional[date] = None
    supplier_id: str
    invoice_number: str
    due_date: str  # YYYY-MM-DD — jatuh tempo hutang ke distributor
    items: List[StockInItemCreate] = Field(min_length=1)
    note: str = ""


class StockInItem(BaseModel):
    owner: Optional[str] = None
    tax: Optional[int] = None
    category: Optional[str] = None
    product_id: str
    product_name: str
    sku: str
    qty: int
    cost_price: float
    subtotal: float
    stock_before: int
    stock_after: int


class StockIn(BaseModel):
    invoice_date: Optional[str] = None
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reference: str  # SM-YYMMDD-0001
    date: datetime
    date_key: str
    supplier_id: str
    supplier_name: str
    invoice_number: str
    due_date: str
    total_amount: float
    note: str = ""
    payable_id: Optional[str] = None
    items: List[StockInItem] = []
