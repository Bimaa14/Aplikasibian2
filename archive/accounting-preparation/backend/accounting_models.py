"""Standalone accounting contracts. Amounts are whole Rupiah, never floats."""
from datetime import date, datetime, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo
import os
from pydantic import BaseModel, Field, ConfigDict, model_validator


def today():
    return datetime.now(ZoneInfo(os.environ['APP_TZ'])).date()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class DebtCreate(Contract):
    kind: Literal['receivable', 'payable']
    party: str = Field(min_length=1, max_length=120)
    reference: str = Field(min_length=1, max_length=60)
    description: str = Field(default='', max_length=500)
    total: int = Field(gt=0, le=1_000_000_000_000, strict=True)
    hpp: int = Field(default=0, ge=0, le=1_000_000_000_000, strict=True)
    issued_date: date
    due_date: date

    @model_validator(mode='after')
    def dates_valid(self):
        if self.issued_date > today():
            raise ValueError('Tanggal transaksi tidak boleh di masa depan.')
        if self.due_date < self.issued_date:
            raise ValueError('Jatuh tempo tidak boleh sebelum tanggal transaksi.')
        if self.kind == 'payable' and self.hpp:
            raise ValueError('HPP hanya dicatat pada penjualan, bukan pembelian supplier.')
        return self


class PaymentCreate(Contract):
    amount: int = Field(gt=0, le=1_000_000_000_000, strict=True)
    method: Literal['cash', 'transfer']
    note: str = Field(default='', max_length=500)
    payment_date: date
    request_id: str = Field(min_length=8, max_length=100)

    @model_validator(mode='after')
    def validate_date(self):
        if self.payment_date > today():
            raise ValueError('Tanggal pembayaran tidak boleh di masa depan.')
        return self


class ReturnCreate(Contract):
    reason: str = Field(min_length=3, max_length=500)
    refund_confirmed: bool = False


class EntryCreate(Contract):
    kind: Literal['sale', 'expense', 'supplier_payment']
    description: str = Field(min_length=3, max_length=300)
    amount: int = Field(gt=0, le=1_000_000_000_000, strict=True)
    hpp: int = Field(default=0, ge=0, le=1_000_000_000_000, strict=True)
    entry_date: date
    request_id: str = Field(min_length=8, max_length=100)

    @model_validator(mode='after')
    def validate_entry(self):
        if self.entry_date > today():
            raise ValueError('Tanggal pencatatan tidak boleh di masa depan.')
        if self.kind != 'sale' and self.hpp:
            raise ValueError('HPP hanya untuk penjualan.')
        return self


class Payment(BaseModel):
    id: str
    amount: int
    method: str
    note: str
    payment_date: str
    created_at: str
    request_id: str


class Debt(BaseModel):
    id: str
    kind: str
    party: str
    reference: str
    description: str
    total: int
    hpp: int
    paid_amount: int
    remaining: int
    status: Literal['unpaid', 'partial', 'paid', 'void']
    issued_date: str
    due_date: str
    created_at: str
    payments: list[Payment]
    days_overdue: int
    days_remaining: int
    due_label: str
    aging_bucket: Optional[str]
    return_date: Optional[str] = None
    return_reason: Optional[str] = None
    refund_amount: int = 0


def enrich_debt(doc):
    result = {k: v for k, v in doc.items() if k != '_id'}
    delta = (date.fromisoformat(doc['due_date']) - today()).days
    active = doc['status'] in ('unpaid', 'partial')
    overdue = max(0, -delta) if active else 0
    result.update(days_overdue=overdue, days_remaining=delta if active else 0,
                  aging_bucket=None,
                  due_label='Dibatalkan' if doc['status'] == 'void' else 'Selesai')
    if active:
        result['due_label'] = f'Telat {overdue} hari' if delta < 0 else ('Jatuh tempo' if delta == 0 else 'Belum jatuh tempo')
        if delta <= 0:
            result['aging_bucket'] = '0-30' if overdue <= 30 else '31-60' if overdue <= 60 else '61-90' if overdue <= 90 else '90+'
    return result