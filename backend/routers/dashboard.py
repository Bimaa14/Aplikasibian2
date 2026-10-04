"""Dashboard Keuangan: widget pendapatan, laba kotor/bersih, piutang/hutang, grafik 7 hari."""

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query

from lib.auth import require_user
from lib.db import db
from lib.dates import today_iso
from lib.debts import hydrate
from lib.reporting import dashboard_report, live_purchases
from routers.excel_reports import live_events
from models.dashboard import DashboardStats, DayRevenue
from models.product import Product
from models.transaction import Transaction

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_user)])

IDN_DAYS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


@router.get("", response_model=DashboardStats)
async def dashboard(year: int | None = Query(default=None, ge=1900, le=9999)):
    today = today_iso()
    selected_year = year if isinstance(year, int) else int(today[:4])
    events = await live_events()
    totals = dashboard_report(events, selected_year)
    txs = await db.transactions.find({'date_key': {'$regex': f'^{selected_year}-'},
                                      'status': {'$in': ['completed', 'returned']},
                                      'report_excluded': {'$ne': True}}, {'_id': 0}).to_list(None)
    purchases = [p for p in await live_purchases() if p.get('date', '')[:4] == str(selected_year)
                 and (p.get('category') or '').upper() == 'TIRE']
    total_cost = sum(e.get('cost', 0) * e.get('qty', 0) for e in events
                     if e.get('date', '')[:4] == str(selected_year)
                     and e['kind'] in ('cash_sale', 'credit_sale') and (e.get('category') or '').upper() == 'TIRE')
    today_revenue = sum(e.get('amount', 0) for e in events if e.get('date') == today
                        and e['kind'] in ('cash_sale', 'credit_sale') and (e.get('category') or '').upper() != 'OIL')

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
        await db.products.find({"active": {"$ne": False}, "type": "barang", "stock": {"$lte": 4}}, {"_id": 0})
        .sort("stock", 1)
        .to_list(5)
    )

    base = datetime.strptime(today, "%Y-%m-%d")
    rev_by_key: dict = {}
    profit_by_key: dict = {}
    for event in events:
        key = event.get('date', '')
        category = (event.get('category') or '').upper()
        if event['kind'] in ('cash_sale', 'credit_sale') and category != 'OIL':
            rev_by_key[key] = rev_by_key.get(key, 0) + event.get('amount', 0)
        if (event['kind'] == 'cash_sale' and category not in ('OIL', 'SERVICE')) or event['kind'] == 'credit_payment':
            profit_by_key[key] = profit_by_key.get(key, 0) + event.get('profit', 0)
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
        year=selected_year,
        years_available=sorted({int(e['date'][:4]) for e in events if e.get('date')} | {int(today[:4]), selected_year}, reverse=True),
        purchase_total=sum(p.get('amount', 0) for p in purchases),
        tire_qty_in=sum(p.get('qty', 0) for p in purchases),
        **totals,
        total_cost=total_cost,
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
