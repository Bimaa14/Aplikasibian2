"""Cash uses payment dates; accrual uses sale and return recognition dates."""
from datetime import date
from calendar import monthrange
from fastapi import APIRouter, Query
from accounting_models import enrich_debt, today


def calculate_report(debts, entries, month):
    cash = dict(cash_sales=0, receivable_collections=0, supplier_payments=0, expenses=0, refunds=0)
    accrual = dict(revenue=0, hpp=0, expenses=0)
    paid = 0
    days = monthrange(int(month[:4]), int(month[5:]))[1]
    series = {f'{month}-{i:02d}': {'date': f'{month}-{i:02d}', 'income': 0, 'outgoing': 0} for i in range(1, days + 1)}
    activities = []
    for e in entries:
        if e['entry_date'][:7] != month:
            continue
        amount, kind, day = e['amount'], e['kind'], e['entry_date']
        if kind == 'sale':
            cash['cash_sales'] += amount
            accrual['revenue'] += amount
            accrual['hpp'] += e['hpp']
        elif kind == 'expense':
            cash['expenses'] += amount
            accrual['expenses'] += amount
        else:
            cash['supplier_payments'] += amount
        series[day]['income' if kind == 'sale' else 'outgoing'] += amount
        activities.append({'id': e['id'], 'date': day, 'label': e['description'], 'amount': amount, 'direction': 'in' if kind == 'sale' else 'out', 'type': kind})
    for d in debts:
        receivable = d['kind'] == 'receivable'
        if receivable and d['issued_date'][:7] == month:
            accrual['revenue'] += d['total']
            accrual['hpp'] += d['hpp']
        if receivable and d.get('return_date', '')[:7] == month:
            accrual['revenue'] -= d['total']
            accrual['hpp'] -= d['hpp']
            refund = d.get('refund_amount', 0)
            cash['refunds'] += refund
            series[d['return_date']]['outgoing'] += refund
            if refund:
                activities.append({'id': f"refund-{d['id']}", 'date': d['return_date'], 'label': f"Pengembalian · {d['party']}", 'amount': refund, 'direction': 'out', 'type': 'refund'})
        for p in d['payments']:
            if p['payment_date'][:7] != month:
                continue
            cash['receivable_collections' if receivable else 'supplier_payments'] += p['amount']
            series[p['payment_date']]['income' if receivable else 'outgoing'] += p['amount']
            if receivable and d['status'] != 'void':
                paid += p['amount']
            activities.append({'id': p['id'], 'date': p['payment_date'], 'label': d['party'], 'amount': p['amount'], 'direction': 'in' if receivable else 'out', 'type': 'receivable' if receivable else 'payable'})
    cash['income'] = cash['cash_sales'] + cash['receivable_collections']
    cash['outgoing'] = cash['supplier_payments'] + cash['expenses'] + cash['refunds']
    cash['net'] = cash['income'] - cash['outgoing']
    accrual['gross_profit'] = accrual['revenue'] - accrual['hpp']
    accrual['net'] = accrual['gross_profit'] - accrual['expenses']
    return dict(month=month, cash=cash, accrual=accrual, receivables_paid=paid,
                series=list(series.values()), activities=sorted(activities, key=lambda x: x['date'], reverse=True))


def reports_router(db):
    router = APIRouter(prefix='/api')

    async def records():
        debts = await db.accounting_debts.find({}, {'_id': 0}).to_list(None)
        entries = await db.accounting_entries.find({}, {'_id': 0}).to_list(None)
        return debts, entries

    @router.get('/reports')
    async def report(month: str = Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')):
        debts, entries = await records()
        return calculate_report(debts, entries, month)

    @router.get('/overview')
    async def overview(month: str = Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')):
        debts, entries = await records()
        summary = {}
        for kind in ('receivable', 'payable'):
            rows = [enrich_debt(d) for d in debts if d['kind'] == kind]
            active = [d for d in rows if d['status'] in ('unpaid', 'partial')]
            summary[kind] = dict(total=sum(d['remaining'] for d in active), count=len(active),
                                 overdue=sum(d['remaining'] for d in active if d['days_overdue'] > 0),
                                 due_today=sum(d['remaining'] for d in active if d['days_remaining'] == 0),
                                 buckets={b: sum(d['remaining'] for d in active if d['aging_bucket'] == b) for b in ('0-30', '31-60', '61-90', '90+')})
        alerts = sorted([enrich_debt(d) for d in debts if d['status'] in ('partial', 'unpaid')], key=lambda d: d['due_date'])
        return {'summary': summary, 'report': calculate_report(debts, entries, month), 'upcoming': alerts[:5], 'total_records': len(debts) + len(entries), 'today': today().isoformat()}

    @router.get('/backup')
    async def backup():
        debts, entries = await records()
        return {'schema_version': 1, 'export_date': today().isoformat(), 'debts': debts, 'entries': entries}

    return router