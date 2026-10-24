import uuid
from datetime import datetime, timedelta, timezone

import pytest

from lib.dates import today_iso
from routers import books, excel_reports
from tests.test_financial_safety import isolated, product, checkout, assert_clean


async def credit_invoice(db, api, **extra):
    pid = await product(db, stock=20, price=2500000)
    await db.products.update_one({'id': pid}, {'$set': {'cost_price': 2300000, 'category': 'TIRE'}})
    if not await db.customers.find_one({'id': 'customer'}):
        await db.customers.insert_one({'id': 'customer', 'name': 'Customer'})
    response = await api.post('/transactions', json=checkout(
        pid, payment_method='credit', customer_id='customer', due_date='2099-01-01', **extra))
    assert response.status_code == 201, response.text
    tx = response.json()
    return tx, await db.accounts_receivable.find_one({'transaction_id': tx['id']}, {'_id': 0})


async def receipt(api, debt, amount, **extra):
    return await api.post(f"/receivables/{debt['id']}/pay", json={
        'amount': amount, 'payment_date': today_iso(), 'request_id': uuid.uuid4().hex, **extra,
    })


async def test_profit_first_then_capital_reaches_daily_and_monthly_once(isolated, monkeypatch):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    monkeypatch.setattr(books, 'dataset', lambda _: {'daily_inputs': {}})
    tx, debt = await credit_invoice(db, api)
    first = await receipt(api, debt, 500000)
    assert first.status_code == 200, first.text
    assert first.json()['payments'][-1]['profit_amount'] == 200000
    final = await receipt(api, debt, 2000000)
    assert final.status_code == 200, final.text
    assert final.json()['payments'][-1]['profit_amount'] == 0
    assert final.json()['remaining'] == 0 and final.json()['status'] == 'paid'
    events = await excel_reports.live_events()
    actual = [e for e in events if e['kind'] == 'credit_payment' and e.get('transaction_id') == tx['id']]
    assert sum(e['amount'] for e in actual) == 2500000
    assert sum(e['profit'] for e in actual) == 200000
    assert all(e['profit_allocation'] == 'invoice' for e in actual)
    assert all(p['profit_allocation'] == 'invoice' for p in final.json()['payments'])
    daily = (await api.get('/books/daily', params={'date': today_iso()})).json()
    assert daily['laba'] == 200000 and daily['modal'] == 2300000
    monthly = (await api.get('/reports/monthly', params={'month': today_iso()[:7]})).json()
    assert monthly['gross_profit_barang'] == 200000 and monthly['cost_of_goods'] == 2300000
    await assert_clean(db)


async def test_small_down_payment_carries_unrecognized_profit_and_noncash_transfer(isolated, monkeypatch):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    monkeypatch.setattr(books, 'dataset', lambda _: {'daily_inputs': {}})
    tx, debt = await credit_invoice(db, api, down_payment_amount=50000, down_payment_method='qris')
    assert debt['paid_amount'] == 50000 and debt['remaining'] == 2450000
    assert debt['payments'][0]['profit_amount'] == 50000 and debt['payments'][0]['is_down_payment']
    first = await receipt(api, debt, 150000)
    second = await receipt(api, debt, 300000)
    assert first.status_code == second.status_code == 200
    assert [p['profit_amount'] for p in second.json()['payments']] == [50000, 150000, 0]
    assert second.json()['payments'][0]['is_down_payment'] is True
    events = await excel_reports.live_events()
    receipts = [e for e in events if e['kind'] == 'credit_payment' and e.get('transaction_id') == tx['id']]
    transfers = [e for e in events if e['kind'] == 'transfer' and e.get('transaction_id') == tx['id']]
    assert len(receipts) == 3 and sum(e['profit'] for e in receipts) == 200000
    assert all(e['profit_allocation'] == 'invoice' for e in receipts)
    assert len(transfers) == 1 and transfers[0]['amount'] == 50000 and transfers[0]['method'] == 'qris'
    daily = (await api.get('/books/daily', params={'date': today_iso()})).json()
    assert daily['receivable_payments'] == 500000 and daily['transfer_payments'] == 50000
    assert daily['net_cash'] == 450000 and daily['laba'] == 200000


async def test_profit_follows_receipt_month_until_invoice_profit_is_used(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    tx, debt = await credit_invoice(db, api)
    await db.transactions.update_one({'id': tx['id']}, {'$set': {'date_key': '2026-01-31'}})
    await db.accounts_receivable.update_one({'id': debt['id']}, {'$set': {'issued_date': '2026-01-31'}})
    for day, amount, profit in [('2026-02-01', 50000, 50000), ('2026-03-01', 150000, 150000),
                                ('2026-04-01', 300000, 0)]:
        paid = await receipt(api, debt, amount, payment_date=day)
        assert paid.status_code == 200, paid.text
        assert paid.json()['payments'][-1]['profit_amount'] == profit
        monthly = (await api.get('/reports/monthly', params={'month': day[:7]})).json()
        assert monthly['gross_profit_barang'] == profit
        assert monthly['revenue_total'] == amount and monthly['cost_of_goods'] == amount - profit
    january = (await api.get('/reports/monthly', params={'month': '2026-01'})).json()
    assert january['gross_profit_barang'] == january['revenue_total'] == 0


async def test_same_customer_date_invoices_keep_separate_profit(isolated):
    db, api, _, _ = isolated
    _, first = await credit_invoice(db, api)
    _, second = await credit_invoice(db, api)
    first_payment = await receipt(api, first, 500000)
    second_payment = await receipt(api, second, 500000)
    assert first_payment.json()['payments'][-1]['profit_amount'] == 200000
    assert second_payment.json()['payments'][-1]['profit_amount'] == 200000
    assert (await receipt(api, first, 100000)).json()['payments'][-1]['profit_amount'] == 0


@pytest.mark.parametrize('created_after_old_receipt,expected_profit', [(False, 0), (True, 200000)])
async def test_old_group_receipt_does_not_recognize_sibling_profit_twice(isolated, created_after_old_receipt, expected_profit):
    db, api, _, _ = isolated
    _, first = await credit_invoice(db, api)
    second_tx, second = await credit_invoice(db, api)
    recorded_at = datetime.now(timezone.utc)
    historical = dict(id='group-receipt', payment_date=today_iso(), amount=1000, profit_amount=400000,
                      profit_is_manual=False, method='cash', created_at=recorded_at.isoformat())
    await db.accounts_receivable.update_one({'id': first['id']}, {'$set': {
        'payments': [historical], 'paid_amount': 1000, 'status': 'partial',
    }})
    sold_at = recorded_at + timedelta(seconds=1 if created_after_old_receipt else -1)
    await db.transactions.update_one({'id': second_tx['id']}, {'$set': {'date': sold_at}})
    paid = await receipt(api, second, 500000)
    assert paid.status_code == 200, paid.text
    assert paid.json()['payments'][-1]['profit_amount'] == expected_profit
    assert (await db.accounts_receivable.find_one({'id': first['id']}))['payments'][0] == historical


@pytest.mark.parametrize('profit', [-1, 500001, 200001])
async def test_manual_profit_cannot_exceed_payment_or_remaining_profit(isolated, profit):
    db, api, _, _ = isolated
    _, debt = await credit_invoice(db, api)
    rejected = await receipt(api, debt, 500000, profit_amount=profit)
    assert rejected.status_code == 422, rejected.text
    assert (await db.accounts_receivable.find_one({'id': debt['id']}))['paid_amount'] == 0
    rejected = await receipt(api, debt, 50000, profit_amount=50001)
    assert rejected.status_code == 422


async def test_retry_and_excluded_receipts_do_not_recognize_profit_again(isolated):
    db, api, _, _ = isolated
    _, debt = await credit_invoice(db, api)
    request_id = uuid.uuid4().hex
    first = await receipt(api, debt, 500000, request_id=request_id)
    retry = await receipt(api, debt, 500000, request_id=request_id)
    assert retry.json()['payments'] == first.json()['payments']
    assert retry.json()['paid_amount'] == 500000
    payment = first.json()['payments'][0]
    payment['report_excluded'] = True
    await db.accounts_receivable.update_one({'id': debt['id']}, {'$set': {'payments': [payment]}})
    next_payment = await receipt(api, debt, 500000)
    assert next_payment.json()['payments'][-1]['profit_amount'] == 0
    events = await excel_reports.live_events()
    included = [e for e in events if e['kind'] == 'credit_payment']
    assert len(included) == 1 and included[0]['profit'] == 0


async def test_return_reverses_down_payment_profit_and_excludes_customer_balance(isolated):
    db, api, _, _ = isolated
    tx, debt = await credit_invoice(db, api, down_payment_amount=50000, down_payment_method='qris')
    returned = await api.post(f"/transactions/{tx['id']}/return", json={'refund_confirmed': True})
    assert returned.status_code == 200 and returned.json()['refund_amount'] == 50000
    assert (await receipt(api, debt, 100000)).status_code == 409
    assert (await api.get('/receivables/summary/by-customer')).json() == []
    events = await excel_reports.live_events()
    assert sum(e['amount'] for e in events if e['kind'] == 'credit_payment') == 0
    assert sum(e['profit'] for e in events if e['kind'] == 'credit_payment') == 0
    assert sum(e['amount'] for e in events if e['kind'] == 'transfer') == 0
    assert all(e['profit_allocation'] == 'invoice' for e in events if e['kind'] == 'credit_payment')


async def test_unrecorded_legacy_payment_suppresses_new_automatic_profit(isolated):
    db, api, _, _ = isolated
    _, debt = await credit_invoice(db, api)
    await db.accounts_receivable.update_one({'id': debt['id']}, {'$set': {'paid_amount': 100000, 'status': 'partial'}})
    paid = await receipt(api, debt, 500000)
    assert paid.status_code == 200 and paid.json()['payments'][-1]['profit_amount'] == 0


async def test_imported_receipt_profit_is_preserved_and_not_recognized_again(isolated):
    db, api, _, _ = isolated
    tx, debt = await credit_invoice(db, api)
    await db.transactions.update_one({'id': tx['id']}, {'$set': {'import_source': 'legacy'}})
    source = dict(id='source-receipt', kind='credit_payment', date=today_iso(), invoice_date=today_iso(),
                  customer='CUSTOMER', amount=50000, profit=200000)
    await db.excel_events.insert_one(dict(source))
    paid = await receipt(api, debt, 500000)
    assert paid.status_code == 200 and paid.json()['payments'][-1]['profit_amount'] == 0
    stored = await db.excel_events.find_one({'id': source['id']}, {'_id': 0})
    assert stored == source
    assert next(e for e in await excel_reports.live_events() if e.get('id') == source['id'])['profit'] == 200000


async def test_existing_explicit_profit_above_receipt_is_not_rewritten_or_repeated(isolated):
    db, api, _, _ = isolated
    _, debt = await credit_invoice(db, api)
    historical = dict(id='legacy-receipt', payment_date=today_iso(), amount=50000,
                      profit_amount=200000, method='cash')
    await db.accounts_receivable.update_one({'id': debt['id']}, {'$set': {
        'paid_amount': 50000, 'status': 'partial', 'payments': [historical],
    }})
    paid = await receipt(api, debt, 500000)
    assert paid.status_code == 200, paid.text
    assert paid.json()['payments'][0]['profit_amount'] == 200000
    assert paid.json()['payments'][-1]['profit_amount'] == 0
    stored = await db.accounts_receivable.find_one({'id': debt['id']})
    assert stored['payments'][0] == historical
    event = next(e for e in await excel_reports.live_events() if e.get('payment_id') == historical['id'])
    assert event['profit_allocation'] is None


async def test_customer_summary_uses_ids_and_normalized_legacy_names(isolated):
    db, api, _, _ = isolated
    rows = [
        dict(id='a', customer_id='known', customer_name='Known Customer', amount=1000, paid_amount=200, status='partial'),
        dict(id='b', customer_id='known', customer_name='Old name', amount=500, paid_amount=500, status='paid'),
        dict(id='c', customer_name='  Legacy   CUSTOMER ', amount=1000, paid_amount=100, status='partial'),
        dict(id='d', customer_id='', customer_name='legacy customer', amount=2000, paid_amount=100, status='partial'),
        dict(id='e', customer_id='known', customer_name='Known Customer', amount=9999, paid_amount=0, status='void'),
        dict(id='f', customer_id='different', customer_name='Known Customer', amount=100, paid_amount=0, status='unpaid'),
    ]
    await db.accounts_receivable.insert_many([
        dict(transaction_id='', issued_date=today_iso(), due_date='2099-01-01', **row) for row in rows
    ])
    response = await api.get('/receivables/summary/by-customer')
    assert response.status_code == 200, response.text
    summary = response.json()
    assert len(summary) == 3
    legacy, known, different = summary
    assert legacy['customer_id'] is None and legacy['customer_name'] == 'Legacy CUSTOMER'
    assert (legacy['total_credit'], legacy['total_paid'], legacy['outstanding'], legacy['invoice_count']) == (3000, 200, 2800, 2)
    assert (known['customer_id'], known['total_credit'], known['total_paid'], known['outstanding'], known['invoice_count']) == ('known', 1500, 700, 800, 2)
    assert different['customer_id'] == 'different' and different['outstanding'] == 100
    invoices = await api.get('/receivables')
    assert invoices.status_code == 200, invoices.text
    assert next(row for row in invoices.json() if row['id'] == 'c')['customer_id'] == ''
