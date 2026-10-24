"""Workbook cache reconciliation and dated accounting in disposable databases."""
from pathlib import Path

import openpyxl
import pytest

from lib.reporting import daily_report, dashboard_report, live_purchases
from lib.workbooks import dataset
from routers import books, dashboard, reports
from tests.test_financial_safety import isolated, product, checkout


def test_requested_workbook_daily_and_dashboard_formulas():
    data = dataset('store_current')
    events = [*data['events'], *[{**e, 'kind': 'transfer'} for e in data['transfers']]]
    inputs = data['daily_inputs']
    actual = daily_report(events, inputs['date'], inputs['modal_bian'], inputs['laba_bian'])
    path = Path(__file__).parents[2] / 'refrensi-spreadsheet' / data['filename']
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook['DAILY REPORT']
    columns = {'cash_sales': 'E6', 'receivable_payments': 'E7', 'transfer_payments': 'E9',
               'expenses': 'E10', 'montir_fee': 'E11', 'net_cash': 'E12', 'final_cash': 'E15',
               'modal': 'H6', 'laba': 'H7', 'spooring': 'H8', 'oil_revenue': 'H9'}
    for key, cell in columns.items():
        assert actual[key] == sheet[cell].value, (key, cell, actual[key], sheet[cell].value)
    sheet = workbook['DASHBOARD']
    year = int(sheet['B4'].value)
    annual = dashboard_report(events, year)
    # D4 is cached as #REF! in the supplied export. Verify its valid formula
    # against raw worksheet columns, and numeric cached cells independently.
    assert sheet['D4'].value == '#REF!'
    source_sales = 0
    for name, category_index, amount_index in [('SELLING CASH', 17, 8), ('SELLING CREDIT', 18, 15)]:
        for row in workbook[name].iter_rows(min_row=2, values_only=True):
            if len(row) <= category_index or not hasattr(row[2], 'year') or row[2].year != year:
                continue
            if str(row[category_index] or '').upper() != 'OIL':
                source_sales += row[amount_index] if isinstance(row[amount_index], (float, int)) else 0
    assert annual['total_revenue'] == source_sales
    for key, cell in {'tire_qty_out': 'E4', 'gross_profit': 'J4',
                      'expenses_total': 'K4', 'net_profit': 'L4'}.items():
        assert annual[key] == sheet[cell].value, (key, cell, annual[key], sheet[cell].value)
    purchases = [p for p in data['purchases'] if p['date'][:4] == str(year) and p['category'] == 'TIRE']
    # Exported SUM cache rounds this Rp3bn total by Rp0.006.
    assert sum(p['amount'] for p in purchases) == pytest.approx(sheet['G4'].value, abs=0.01, rel=0)
    assert sum(p['qty'] for p in purchases) == sheet['H4'].value
    workbook.close()


def test_daily_non_oil_cashier_only_and_bian_draws():
    day = '2026-01-01'
    events = [
        dict(date=day, kind='cash_sale', amount=100000, profit=20000, fee=1000, category='TIRE', method='qris'),
        dict(date=day, kind='cash_sale', amount=10000, profit=6000, fee=0, category='OIL'),
        dict(date=day, kind='credit_sale', amount=30000, profit=10000, fee=2000, category='TIRE'),
        dict(date=day, kind='credit_payment', amount=20000, profit=10000),
        dict(date=day, kind='transfer', amount=100000),
        dict(date=day, kind='expense', amount=3000, payment_source='Cashier'),
        dict(date=day, kind='expense', amount=8000, payment_source='IBU'),
    ]
    result = daily_report(events, day, modal_bian=5000, laba_bian=4000)
    assert result['cash_sales'] == 100000
    assert result['expenses'] == 3000
    assert result['net_cash'] == 14000
    assert result['final_cash'] == 5000
    assert result['laba'] == 21000
    assert result['spooring'] == 2000
    assert result['modal'] == -18000


async def test_cash_return_preserves_original_period_and_reverses_return_period(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db, price=10000)
    await db.products.update_one({'id': pid}, {'$set': {'owner': 'bian', 'category': 'TIRE'}})
    tx = (await api.post('/transactions', json=checkout(pid))).json()
    response = await api.post('/transactions/' + tx['id'] + '/return', json={'refund_confirmed': True})
    assert response.status_code == 200, response.text
    await db.transactions.update_one({'id': tx['id']}, {'$set': {'date_key': '2026-01-31', 'return_date': '2026-02-01'}})
    january = await reports._build_report('2026-01')
    february = await reports._build_report('2026-02')
    assert january.revenue_total == 10000 and january.net_profit == 5000
    assert january.transaction_count == 1 and january.returned_count == 0
    assert february.revenue_total == -10000 and february.net_profit == -5000
    assert february.transaction_count == 0 and february.returned_count == 1
    owners = await books._owner_summary('2026-02')
    bian = next(o for o in owners if o['owner'] == 'bian')
    assert bian['omzet'] == -10000 and bian['laba'] == -5000


async def test_credit_profit_recognition_and_refund_survive_void_status(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db, price=10000)
    await db.products.update_one({'id': pid}, {'$set': {'owner': 'ibu', 'category': 'TIRE'}})
    await db.customers.insert_one({'id': 'customer', 'name': 'Customer'})
    tx = (await api.post('/transactions', json=checkout(pid, payment_method='credit', customer_id='customer', due_date='2099-01-01'))).json()
    debt = await db.accounts_receivable.find_one({'transaction_id': tx['id']})
    await db.transactions.update_one({'id': tx['id']}, {'$set': {'date_key': '2026-01-31', 'status': 'returned', 'return_date': '2026-03-01'}})
    await db.accounts_receivable.update_one({'id': debt['id']}, {'$set': {
        'status': 'void', 'return_date': '2026-03-01', 'refund_amount': 2500,
        'payments': [dict(id='payment', payment_date='2026-02-01', amount=2500, profit_amount=5000, method='cash')],
    }})
    january = await reports._build_report('2026-01')
    february = await reports._build_report('2026-02')
    march = await reports._build_report('2026-03')
    assert january.revenue_total == january.net_profit == 0
    assert january.new_receivables == 10000
    assert february.revenue_total == 2500 and february.net_profit == 5000
    assert february.receivables_paid == 2500
    assert march.revenue_total == -2500 and march.net_profit == -5000
    assert march.receivables_paid == -2500
    ibu = next(o for o in await books._owner_summary('2026-02') if o['owner'] == 'ibu')
    assert ibu['omzet'] == 2500 and ibu['laba'] == 5000


@pytest.mark.parametrize('second_owner,expected_owner', [('ibu', 'unassigned'), ('bian', 'bian')])
@pytest.mark.parametrize('allocation', ['invoice', 'legacy_without_invoice', 'legacy_with_invoice'])
async def test_credit_payment_owner_prefers_invoice_then_legacy_customer_date(second_owner, expected_owner, allocation):
    recognized_profit = 2500 if allocation == 'invoice' else 15000
    events = [
        dict(date='2026-01-31', invoice_date='2026-01-31', kind='credit_sale', amount=10000,
             profit=5000, fee=0, category='TIRE', owner='bian', transaction_id='first', customer='Customer'),
        dict(date='2026-01-31', invoice_date='2026-01-31', kind='credit_sale', amount=20000,
             profit=10000, fee=0, category='TIRE', owner=second_owner, transaction_id='second', customer='CUSTOMER'),
        dict(date='2026-02-01', invoice_date='2026-01-31', kind='credit_payment', amount=2500,
             profit=recognized_profit, customer='customer'),
        dict(date='2026-03-01', invoice_date='2026-01-31', kind='credit_payment', amount=-2500,
             profit=-recognized_profit, customer='Customer', is_return=True),
    ]
    for event in events:
        if event['kind'] != 'credit_payment':
            continue
        if allocation != 'legacy_without_invoice':
            event['transaction_id'] = 'first'
        if allocation == 'invoice':
            event['profit_allocation'] = 'invoice'
    if allocation == 'invoice':
        expected_owner = 'bian'
    for month, amount, profit in [('2026-02', 2500, recognized_profit), ('2026-03', -2500, -recognized_profit)]:
        owners = await books._owner_summary(month, events)
        expected = next(owner for owner in owners if owner['owner'] == expected_owner)
        assert expected['omzet'] == amount and expected['laba'] == profit
        assert sum(owner['omzet'] for owner in owners) == amount
        assert sum(owner['laba'] for owner in owners) == profit


async def test_daily_parameters_and_dashboard_receipt_year_use_isolated_db(isolated, monkeypatch):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    monkeypatch.setattr(books, 'dataset', lambda _: {'daily_inputs': {}})
    await db.excel_events.insert_many([
        dict(date='2025-12-31', kind='cash_sale', amount=999, profit=999, category='TIRE'),
        dict(date='2026-01-01', kind='cash_sale', amount=10000, profit=5000, category='TIRE', qty=1, fee=0),
        dict(date='2026-01-01', kind='cash_sale', amount=5000, profit=3000, category='SERVICE', qty=1, fee=2000),
        dict(date='2026-01-01', kind='credit_sale', amount=20000, profit=6000, category='TIRE', qty=2, fee=1000),
        dict(date='2026-01-01', kind='credit_payment', amount=7000, profit=6000),
        dict(date='2026-01-01', kind='expense', amount=1000, payment_source='IBU'),
    ])
    await db.purchase_history.insert_many([
        dict(date='2026-01-01', invoice_date='2025-12-31', amount=8000, qty=1, category='TIRE'),
        dict(date='2025-12-31', invoice_date='2026-01-01', amount=999, qty=1, category='TIRE'),
    ])
    saved = await api.put('/books/daily/parameters/2026-01-01', json={'modal_bian': 3000, 'laba_bian': 1000})
    assert saved.status_code == 200, saved.text
    daily = (await api.get('/books/daily?date=2026-01-01')).json()
    assert daily['final_cash'] == 15000 and daily['parameters_saved']
    assert (await api.put('/books/daily/parameters/2026-02-30', json={})).status_code == 422
    annual = await dashboard.dashboard(2026)
    assert annual.total_revenue == 35000 and annual.gross_profit == 11000
    assert annual.net_profit == 10000 and annual.purchase_total == 8000
    assert annual.tire_qty_out == 3 and annual.tire_qty_in == 1
    monthly = await books._monthly_data('2026-01')
    assert monthly['funding']['laba']['total'] == monthly['expenses_total'] == 1000
    assert monthly['pph_final'] == 0


async def test_unmapped_purchase_is_not_assumed_to_be_tire(isolated):
    db, _, _, _ = isolated
    await db.stock_in.insert_one(dict(date_key='2026-01-01', items=[
        dict(product_id='missing-product', subtotal=8000, qty=2),
        dict(product_id='snapshot-tire', subtotal=12000, qty=3, category='TIRE'),
    ]))
    purchases = await live_purchases()
    assert next(p for p in purchases if p['amount'] == 8000)['category'] == ''
    tire = [p for p in purchases if p['category'] == 'TIRE']
    assert sum(p['amount'] for p in tire) == 12000
    assert sum(p['qty'] for p in tire) == 3
