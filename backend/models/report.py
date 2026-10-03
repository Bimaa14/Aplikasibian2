"""Laporan bulanan laba-rugi (pembukuan bengkel)."""
from typing import List

from pydantic import BaseModel


class ExpenseByCategory(BaseModel):
    category: str
    amount: float


class TopProduct(BaseModel):
    name: str
    sku: str
    qty: int
    revenue: float


class MonthlyReport(BaseModel):
    month: str  # YYYY-MM
    month_label: str  # "September 2026"
    revenue_total: float
    barang_revenue: float
    jasa_revenue: float
    cost_of_goods: float  # REPORT F: modal yang diakui
    gross_profit_barang: float  # REPORT G: laba tanpa oli/spooring
    service_fee_total: float  # komisi montir
    expenses_total: float
    expenses_by_category: List[ExpenseByCategory]
    net_profit: float
    supplier_payments: float = 0
    capital_balance: float = 0
    spooring_net: float = 0
    oil_revenue: float = 0
    transaction_count: int
    returned_count: int
    returned_amount: float
    new_receivables: float  # piutang baru bulan ini
    receivables_paid: float
    stock_in_total: float  # nilai barang masuk bulan ini
    top_products: List[TopProduct]
    available_months: List[str]
