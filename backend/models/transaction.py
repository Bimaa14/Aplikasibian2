"""POS transaction models. Checkout body validates the credit rule (tempo wajib pelanggan + jatuh tempo)."""
import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

PaymentMethod = Literal["cash", "credit", "edc", "transfer_bca", "transfer_bri", "transfer_bni", "qris"]


class CheckoutItem(BaseModel):
    discount_amount: float = Field(default=0, ge=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    credit_surcharge: float = Field(default=0, ge=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    product_id: str
    qty: int = Field(gt=0)


class TransactionCreate(BaseModel):
    request_id: Optional[str] = Field(default=None, min_length=8, max_length=100)
    items: List[CheckoutItem] = Field(min_length=1)
    payment_method: PaymentMethod
    discount_total: float = Field(default=0, ge=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    cash_received: Optional[float] = Field(default=None, ge=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    customer_id: Optional[str] = None
    due_date: Optional[date] = None  # serialises to YYYY-MM-DD
    vehicle_plate: Optional[str] = None  # nomor polisi (opsional) — untuk riwayat kendaraan

    @model_validator(mode="after")
    def credit_rule(self):
        if self.payment_method != "cash" and self.cash_received is not None:
            raise ValueError("Uang tunai hanya diisi untuk pembayaran tunai")
        if self.payment_method != "credit" and any(i.credit_surcharge for i in self.items):
            raise ValueError("Tambahan harga hanya tersedia untuk transaksi tempo")
        if self.payment_method == "credit":
            if self.cash_received is not None:
                raise ValueError("Uang tunai hanya diisi untuk pembayaran tunai")
            if not self.customer_id:
                raise ValueError("Pelanggan wajib dipilih untuk pembayaran tempo (credit)")
            if not self.due_date:
                raise ValueError("Jatuh tempo wajib diisi untuk pembayaran tempo (credit)")
        return self


class TransactionDetail(BaseModel):
    product_size: str = ""
    product_brand: str = ""
    tax: Optional[Literal[0, 1]] = None
    base_price: Optional[float] = None
    credit_surcharge: float = 0
    discount_amount: float = 0
    category: str = 'TIRE'
    spreadsheet_cost: float = 0
    spreadsheet_fee: float = 0
    spreadsheet_profit: float = 0
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str = ""
    product_id: str
    product_name: str
    product_sku: Optional[str] = None
    product_type: Literal["barang", "jasa"]
    owner: Optional[str] = None  # ikut pemilik produk saat checkout: 'bian' / 'ibu' / None (produk lama)
    qty: int
    price: float
    cost_price: float = 0
    service_fee: float = 0
    subtotal: float


class Transaction(BaseModel):
    customer_address: str = ""
    spreadsheet_profit: float = 0
    return_date: Optional[str] = None
    return_reason: str = ''
    refund_amount: float = 0
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_number: str
    date: datetime
    date_key: str  # YYYY-MM-DD in APP_TZ, for daily aggregation
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    payment_method: PaymentMethod
    discount_total: float = 0
    total_amount: float
    cash_received: Optional[float] = None
    change_amount: Optional[float] = None
    barang_amount: float = 0
    jasa_amount: float = 0
    total_cost: float = 0
    service_fee: float = 0
    total_profit: float = 0
    status: Literal["completed", "returned"] = "completed"
    due_date: Optional[str] = None
    vehicle_plate: Optional[str] = None  # nomor polisi kendaraan yang diservis
    details: List[TransactionDetail] = []
