"""Piutang (accounts receivable), Hutang (accounts payable) and Pengeluaran (expenses) models."""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AccountsReceivable(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str
    invoice_number: str = ""
    customer_id: str
    customer_name: str = ""
    amount: float
    due_date: str  # YYYY-MM-DD (string so pymongo can store it and ISO order == chronological order)
    status: Literal["unpaid", "paid"] = "unpaid"


class AccountsPayable(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    supplier_id: str
    supplier_name: str = ""
    invoice_number: str
    amount: float
    due_date: str
    status: Literal["unpaid", "paid"] = "unpaid"


class PayableCreate(BaseModel):
    supplier_id: str
    invoice_number: str
    amount: float
    due_date: str


class Expense(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str  # YYYY-MM-DD
    amount: float
    category: str
    description: str = ""


class ExpenseCreate(BaseModel):
    date: Optional[str] = None  # defaults to server-side today (APP_TZ)
    amount: float
    category: str
    description: str = ""
