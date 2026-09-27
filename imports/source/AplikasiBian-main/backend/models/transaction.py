"""POS transaction models. Checkout body validates the credit rule (tempo wajib pelanggan + jatuh tempo)."""
import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class CheckoutItem(BaseModel):
    product_id: str
    qty: int = Field(gt=0)


class TransactionCreate(BaseModel):
    items: List[CheckoutItem] = Field(min_length=1)
    payment_method: Literal["cash", "credit"]
    customer_id: Optional[str] = None
    due_date: Optional[date] = None  # serialises to YYYY-MM-DD
    vehicle_plate: Optional[str] = None  # nomor polisi (opsional) — untuk riwayat kendaraan

    @model_validator(mode="after")
    def credit_rule(self):
        if self.payment_method == "credit":
            if not self.customer_id:
                raise ValueError("Pelanggan wajib dipilih untuk pembayaran tempo (credit)")
            if not self.due_date:
                raise ValueError("Jatuh tempo wajib diisi untuk pembayaran tempo (credit)")
        return self


class TransactionDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str = ""
    product_id: str
    product_name: str
    product_type: Literal["barang", "jasa"]
    qty: int
    price: float
    cost_price: float = 0
    service_fee: float = 0
    subtotal: float


class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_number: str
    date: datetime
    date_key: str  # YYYY-MM-DD in APP_TZ, for daily aggregation
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    payment_method: Literal["cash", "credit"]
    total_amount: float
    barang_amount: float = 0
    jasa_amount: float = 0
    total_cost: float = 0
    service_fee: float = 0
    total_profit: float = 0
    status: Literal["completed", "returned"] = "completed"
    due_date: Optional[str] = None
    vehicle_plate: Optional[str] = None  # nomor polisi kendaraan yang diservis
    details: List[TransactionDetail] = []
