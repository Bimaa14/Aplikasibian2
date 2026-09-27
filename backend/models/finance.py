"""Original POS debt contracts extended with installments; amounts allow Rupiah cents."""
import uuid
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator
from lib.dates import today_iso


class PaymentInput(BaseModel):
    amount: float = Field(gt=0, le=1e12, allow_inf_nan=False, multiple_of=0.01)
    payment_date: date
    method: Literal['cash', 'transfer'] = 'cash'
    note: str = Field(default='', max_length=500)
    request_id: str = Field(min_length=8, max_length=100)
    profit_amount: Optional[float] = Field(default=None, allow_inf_nan=False)


class Payment(BaseModel):
    id: str
    amount: float
    payment_date: str
    method: str
    note: str = ''
    request_id: str
    profit_amount: float = 0
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
    customer_id: str
    customer_name: str = ''


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
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    amount: float
    category: str
    description: str = ''


class ExpenseCreate(BaseModel):
    date: Optional[str] = None
    amount: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    category: str
    description: str = ''