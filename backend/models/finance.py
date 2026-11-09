"""Original POS debt contracts extended with installments; amounts allow Rupiah cents."""
import uuid
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator
from lib.dates import today_iso


class PaymentInput(BaseModel):
    amount: float = Field(gt=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    payment_date: date
    method: Literal['cash', 'transfer', 'edc', 'transfer_bca', 'transfer_bri', 'transfer_bni', 'qris', 'mix'] = 'cash'
    cash_amount: Optional[float] = Field(default=None, ge=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    transfer_amount: Optional[float] = Field(default=None, ge=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    transfer_method: Optional[Literal['transfer', 'edc', 'transfer_bca', 'transfer_bri', 'transfer_bni', 'qris']] = None
    note: str = Field(default='', max_length=500)
    request_id: str = Field(min_length=8, max_length=100)
    profit_amount: Optional[float] = Field(default=None, ge=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)

    @model_validator(mode='after')
    def valid_mix(self):
        if self.method == 'mix':
            if not self.cash_amount or self.cash_amount <= 0 or not self.transfer_amount or self.transfer_amount <= 0:
                raise ValueError('Pembayaran mix wajib mengisi nominal tunai dan transfer lebih dari nol')
            if self.transfer_method is None:
                raise ValueError('Metode transfer untuk pembayaran mix wajib dipilih')
            if round(self.cash_amount + self.transfer_amount, 2) != round(self.amount, 2):
                raise ValueError('Jumlah tunai dan transfer harus sama dengan nominal cicilan')
        elif self.cash_amount is not None or self.transfer_amount is not None or self.transfer_method is not None:
            raise ValueError('Rincian pembayaran mix hanya diisi saat memilih metode Mix')
        return self


class Payment(BaseModel):
    id: str
    amount: float
    payment_date: str
    method: str
    cash_amount: Optional[float] = None
    transfer_amount: Optional[float] = None
    transfer_method: Optional[str] = None
    note: str = ''
    request_id: str = ''
    profit_amount: float = 0
    profit_is_manual: Optional[bool] = None
    profit_allocation: Optional[Literal['invoice']] = None
    is_down_payment: bool = False
    recorded_by: str = ''


class DebtBase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    amount: float = Field(gt=0, allow_inf_nan=False)
    due_date: str
    issued_date: str = Field(default_factory=today_iso)
    status: Literal['unpaid', 'partial', 'paid', 'void'] = 'unpaid'
    paid_amount: float = 0
    remaining: float = 0
    payments: list[Payment] = Field(default_factory=list)
    version: int = 0
    days_overdue: int = 0
    days_remaining: int = 0
    due_label: str = ''
    aging_bucket: Optional[str] = None
    legacy_payment_history_missing: bool = False
    refund_amount: float = 0


class AccountsReceivable(DebtBase):
    transaction_id: str
    invoice_number: str = ''
    customer_id: str = ''
    customer_name: str = ''


class CustomerReceivableSummary(BaseModel):
    customer_id: Optional[str] = None
    customer_name: str = ''
    total_credit: float = 0
    total_paid: float = 0
    outstanding: float = 0
    invoice_count: int = 0


class AccountsPayable(DebtBase):
    supplier_id: str
    supplier_name: str = ''
    invoice_number: str


class PayableCreate(BaseModel):
    supplier_id: str
    invoice_number: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    due_date: str

    @model_validator(mode='after')
    def valid_date(self):
        date.fromisoformat(self.due_date)
        return self


class Expense(BaseModel):
    payment_source: str = 'Cashier'
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    amount: float
    category: str
    description: str = ''


class ExpenseCreate(BaseModel):
    payment_source: Literal['Cashier', 'IBU'] = 'Cashier'
    date: Optional[str] = None
    amount: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    category: str
    description: str = ''
