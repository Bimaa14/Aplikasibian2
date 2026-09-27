"""Dashboard Keuangan: widget pendapatan, laba kotor/bersih, piutang/hutang, grafik 7 hari."""

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends

from lib.auth import require_user
from lib.db import db
from lib.dates import today_iso
from lib.debts import hydrate
from models.dashboard import DashboardStats, DayRevenue
from models.product import Product
from models.transaction import Transaction

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_user)])

IDN_DAYS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


@router.get("", response_model=DashboardStats)
async def dashboard():
    today = today_iso()

    txs = await db.transactions.find({"status": "completed"}, {"_id": 0}).to_list(10000)
    total_revenue = sum(t.get("total_amount", 0) for t in txs)
    total_cost = sum(t.get("total_cost", 0) for t in txs)
    barang_amount = sum(t.get("barang_amount", 0) for t in txs)
    jasa_amount = sum(t.get("jasa_amount", 0) for t in txs)
    service_fee_total = sum(t.get("service_fee", 0) for t in txs)
    total_profit = sum(t.get("total_profit", 0) for t in txs)  # jasa sudah neto komisi montir
    today_revenue = sum(t.get("total_amount", 0) for t in txs if t.get("date_key") == today)

    expenses = await db.expenses.find({}, {"_id": 0}).to_list(10000)
    expenses_total = sum(e.get("amount", 0) for e in expenses)

    receivables_unpaid = [hydrate(d) async for d in db.accounts_receivable.find({"status": {"$in": ["unpaid", "partial"]}}, {"_id": 0})]
    receivables_outstanding = sum(r['remaining'] for r in receivables_unpaid)
    overdue_rx = sorted(
        [r for r in receivables_unpaid if r.get("due_date", "") < today],
        key=lambda r: r.get("due_date", ""),
    )[:5]

    payables_unpaid = [hydrate(d) async for d in db.accounts_payable.find({"status": {"$in": ["unpaid", "partial"]}}, {"_id": 0})]
    payables_outstanding = sum(p['remaining'] for p in payables_unpaid)
    overdue_px = sorted(
        [p for p in payables_unpaid if p.get("due_date", "") < today],
        key=lambda p: p.get("due_date", ""),
    )[:5]

    def aging_buckets(items):
        b = {"upcoming": 0.0, "0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
        for d in items:
            bucket = d.get("aging_bucket")
            if bucket in b:
                b[bucket] += d["remaining"]
            elif d.get("days_remaining", 0) > 0:
                b["upcoming"] += d["remaining"]
        return b

    low_stock_docs = (
        await db.products.find({"type": "barang", "stock": {"$lte": 4}}, {"_id": 0})
        .sort("stock", 1)
        .to_list(5)
    )

    base = datetime.strptime(today, "%Y-%m-%d")
    rev_by_key: dict = {}
    profit_by_key: dict = {}
    for t in txs:
        key = t.get("date_key", "")
        rev_by_key[key] = rev_by_key.get(key, 0) + t.get("total_amount", 0)
        profit_by_key[key] = profit_by_key.get(key, 0) + t.get("total_profit", 0)
    revenue_by_day: List[DayRevenue] = []
    for i in range(6, -1, -1):
        day = base - timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        revenue_by_day.append(
            DayRevenue(date_key=key, label=IDN_DAYS[day.weekday()], revenue=rev_by_key.get(key, 0), profit=profit_by_key.get(key, 0))
        )

    recent_docs = await db.transactions.find({}, {"_id": 0}).sort("date", -1).to_list(5)
    recent = []
    for d in recent_docs:
        d = dict(d)
        d.pop("details", None)
        if d["date"].tzinfo is None:
            d["date"] = d["date"].replace(tzinfo=timezone.utc)
        recent.append(Transaction(**d))

    return DashboardStats(
        today=today,
        total_revenue=total_revenue,
        total_cost=total_cost,
        gross_profit=barang_amount - total_cost,
        jasa_amount=jasa_amount,
        service_fee_total=service_fee_total,
        expenses_total=expenses_total,
        net_profit=total_profit - expenses_total,
        transaction_count=len(txs),
        today_revenue=today_revenue,
        receivables_outstanding=receivables_outstanding,
        receivables_overdue=len([r for r in receivables_unpaid if r.get("due_date", "") < today]),
        payables_outstanding=payables_outstanding,
        payables_overdue=len([p for p in payables_unpaid if p.get("due_date", "") < today]),
        receivables_aging=aging_buckets(receivables_unpaid),
        payables_aging=aging_buckets(payables_unpaid),
        low_stock=[Product(**d) for d in low_stock_docs],
        revenue_by_day=revenue_by_day,
        overdue_receivables=overdue_rx,
        overdue_payables=overdue_px,
        recent_transactions=recent,
    )
