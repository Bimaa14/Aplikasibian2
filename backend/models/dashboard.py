"""Dashboard aggregation models (widget Keuangan)."""
from typing import List

from pydantic import BaseModel

from models.finance import AccountsPayable, AccountsReceivable
from models.product import Product
from models.transaction import Transaction


class DayRevenue(BaseModel):
    date_key: str  # YYYY-MM-DD
    label: str  # Sen/Sel/Rab/...
    revenue: float
    profit: float


class DashboardStats(BaseModel):
    today: str
    total_revenue: float
    total_cost: float
    gross_profit: float  # laba kotor barang
    jasa_amount: float
    service_fee_total: float  # komisi montir
    expenses_total: float
    net_profit: float  # laba bersih: total profit (sudah neto komisi) - pengeluaran
    transaction_count: int
    today_revenue: float
    receivables_outstanding: float
    receivables_overdue: int
    payables_outstanding: float
    payables_overdue: int
    receivables_aging: dict
    payables_aging: dict
    low_stock: List[Product]
    revenue_by_day: List[DayRevenue]
    overdue_receivables: List[AccountsReceivable]
    overdue_payables: List[AccountsPayable]
    recent_transactions: List[Transaction]
