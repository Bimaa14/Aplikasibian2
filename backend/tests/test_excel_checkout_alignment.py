"""Workbook formulas plus checkout/payments in disposable Mongo databases."""
from pathlib import Path
import uuid

import openpyxl
import pytest

from lib.dates import today_iso
from lib.excel_rules import line_values, line_snapshot_values
from tests.test_financial_safety import isolated, product, checkout, assert_clean


@pytest.mark.parametrize('category,credit,expected_profit', [
    ('TIRE', False, 120000), ('OIL', False, 120000),
    ('COMPLEMENTARY', False, 100000), ('SERVICE', False, 60000),
    ('TIRE', True, 160000), ('OIL', True, 0),
    ('COMPLEMENTARY', True, 140000), ('SERVICE', True, 100000),
])
def test_category_branches_round_modal_and_credit_service_cash_base(category, credit, expected_profit):
    p = dict(name='SERVICE' if category == 'SERVICE' else 'Example', type='jasa' if category in ('SERVICE', 'COMPLEMENTARY') else 'barang',
             category=category, cost_price=39001, selling_price=120000 if credit else 100000,
             base_price=100000, service_fee=10000)
    result = line_values(p, 2, credit)
    assert result['spreadsheet_cost'] == 40000
    assert result['spreadsheet_cost_total'] == (40000 if category == 'SERVICE' else 80000)
    assert result['spreadsheet_fee'] == (100000 if category == 'SERVICE' else 20000)
    assert result['cash_subtotal'] == 200000
    assert result['spreadsheet_profit'] == expected_profit


def test_discount_service_cash_and_tempo_are_different_fee_bases():
    p = dict(name='SERVICE', type='jasa', category='SERVICE', selling_price=100000, base_price=80000, cost_price=20001, service_fee=0)
    cash = line_values(p, 3, discount=30000)
    tempo = line_values(p, 3, credit=True, discount=30000)
    assert (cash['spreadsheet_fee'], cash['spreadsheet_profit'], cash['spreadsheet_cost_total']) == (135000, 110000, 25000)
    assert (tempo['cash_subtotal'], tempo['spreadsheet_fee'], tempo['spreadsheet_profit']) == (240000, 120000, 125000)


def test_service_fee_uses_literal_half_without_rounding_away_half_cent():
    p = dict(name='SERVICE', type='jasa', category='SERVICE', selling_price=0.03, cost_price=0)
    values = line_values(p, 1)
    assert values['spreadsheet_fee'] == values['spreadsheet_profit'] == 0.015


def test_imported_cached_manual_cells_remain_authoritative():
    detail = dict(import_source='store_current', product_name='SERVICE', product_type='jasa',
                  category='SERVICE', qty=3, price=100000, base_price=90000, subtotal=300000,
                  cash_subtotal=260000, cost_price=80000, spreadsheet_cost=80000,
                  service_fee=27000, spreadsheet_fee=81000, spreadsheet_profit=12345)
    result = line_snapshot_values(detail, credit=True)
    assert (result['cash_subtotal'], result['spreadsheet_fee'], result['spreadsheet_profit']) == (260000, 81000, 12345)


def test_formula_replay_matches_actual_workbook_cached_sales():
    path = Path(__file__).resolve().parents[2] / 'refrensi-spreadsheet' / 'Perkasa Jaya - Store information system (1).xlsx'
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    # These saved rows contain manual fixed costs/fees or a cross-row typo,
    # plus row9526's I formula subtracts an additional manual Rp50000. Importing
    # preserves these source values instead of silently recalculating them.
    exceptions = {'SELLING CASH': {5753, 7639, 7926, 7931, 9526, 10369}, 'SELLING CREDIT': {96, 110, 790}}
    compared = 0
    try:
        for sheet, credit in [('SELLING CASH', False), ('SELLING CREDIT', True)]:
            for row_number, row in enumerate(workbook[sheet].iter_rows(min_row=2, max_col=20, values_only=True), 2):
                if row_number in exceptions[sheet] or not row[2]:
                    continue
                qty, name, price, discount, fee, absolute_cost, fixed_cost, amount, profit, category = (
                    (row[6], row[5], row[8], 0, row[10], row[12], row[13], row[15], row[16], row[18]) if credit else
                    (row[5], row[4], row[6], row[7] or 0, row[9], row[11], row[12], row[8], row[13], row[17]))
                if not isinstance(qty, (int, float)) or qty <= 0 or not isinstance(price, (int, float)) or not isinstance(profit, (int, float)):
                    continue
                p = dict(name=name, type='jasa' if str(category).upper() in ('SERVICE', 'COMPLEMENTARY') else 'barang',
                         category=category, selling_price=price, base_price=row[7] if credit else price,
                         cost_price=absolute_cost or 0, service_fee=(fee or 0) / qty)
                values = line_values(p, qty, credit, discount * qty)
                assert values['spreadsheet_cost'] == fixed_cost, (sheet, row_number, 'fixed cost')
                assert values['spreadsheet_fee'] == fee, (sheet, row_number, 'fee')
                assert values['spreadsheet_profit'] == profit, (sheet, row_number, 'profit')
                assert round(price * qty - discount * qty, 2) == amount, (sheet, row_number, 'total')
                compared += 1
    finally:
        workbook.close()
    assert compared > 11000


async def test_checkout_per_unit_discount_rounds_modal_and_preserves_cash_credit_totals(isolated):
    db, api, _, _ = isolated
    pid = await product(db, stock=10, price=100000)
    await db.products.update_one({'id': pid}, {'$set': {'cost_price': 39001, 'category': 'TIRE', 'service_fee': 10000}})
    r = await api.post('/transactions', json=checkout(pid, items=[{'product_id': pid, 'qty': 3, 'discount_per_unit': 5000}]))
    assert r.status_code == 201, r.text
    tx = r.json()
    assert (tx['total_amount'], tx['discount_total'], tx['total_cost'], tx['total_profit'], tx['service_fee']) == (285000, 15000, 120000, 165000, 30000)
    d = tx['details'][0]
    assert (d['discount_per_unit'], d['source_cost_price'], d['cost_price']) == (5000, 39001, 40000)
    assert (await db.products.find_one({'id': pid}))['cost_price'] == 39001
    await db.customers.insert_one({'id': 'c', 'name': 'Customer'})
    r = await api.post('/transactions', json=checkout(pid, items=[{'product_id': pid, 'qty': 2, 'credit_surcharge': 20000, 'discount_per_unit': 5000}],
                                                   payment_method='credit', customer_id='c', due_date='2099-01-01'))
    assert r.status_code == 201, r.text
    tx = r.json()
    assert (tx['total_amount'], tx['total_cost'], tx['total_profit']) == (230000, 80000, 150000)
    assert tx['details'][0]['cash_subtotal'] == 200000
    await assert_clean(db)


async def test_credit_profit_is_bounded_by_receipt_for_each_invoice(isolated):
    db, api, _, _ = isolated
    pid = await product(db, stock=10, price=100000)
    service = await product(db, price=100000)
    await db.products.update_one({'id': service}, {'$set': {'name': 'SERVICE', 'type': 'jasa', 'category': 'SERVICE', 'cost_price': 20001}})
    await db.customers.insert_one({'id': 'c', 'name': 'Customer'})
    debt_ids = []
    for item in [{'product_id': pid, 'qty': 1}, {'product_id': service, 'qty': 2, 'credit_surcharge': 20000}]:
        r = await api.post('/transactions', json=checkout(item['product_id'], items=[item], payment_method='credit', customer_id='c', due_date='2099-01-01'))
        assert r.status_code == 201, r.text
        debt_ids.append((await db.accounts_receivable.find_one({'transaction_id': r.json()['id']}))['id'])
    async def receipt(debt_id):
        return await api.post(f'/receivables/{debt_id}/pay', json={'amount': 1000, 'payment_date': today_iso(), 'request_id': uuid.uuid4().hex})
    first = await receipt(debt_ids[0])
    assert first.status_code == 200, first.text
    assert first.json()['payments'][0]['profit_amount'] == 1000
    assert first.json()['payments'][0]['profit_is_manual'] is False
    for debt_id in debt_ids:
        subsequent = await receipt(debt_id)
        assert subsequent.status_code == 200, subsequent.text
        assert subsequent.json()['payments'][-1]['profit_amount'] == 1000


@pytest.mark.parametrize('source_receipt', [False, True])
async def test_explicit_zero_or_unrelated_imported_receipt_does_not_exhaust_native_profit(isolated, source_receipt):
    db, api, _, _ = isolated
    pid = await product(db, stock=10)
    await db.customers.insert_one({'id': 'c', 'name': 'Customer'})
    tx = (await api.post('/transactions', json=checkout(pid, payment_method='credit', customer_id='c', due_date='2099-01-01'))).json()
    debt_id = (await db.accounts_receivable.find_one({'transaction_id': tx['id']}))['id']
    if source_receipt:
        await db.excel_events.insert_one({'kind': 'credit_payment', 'invoice_date': today_iso(), 'customer': 'customer', 'amount': 100, 'profit': 0})
    else:
        first = await api.post(f'/receivables/{debt_id}/pay', json={'amount': 100, 'profit_amount': 0, 'payment_date': today_iso(), 'request_id': uuid.uuid4().hex})
        assert first.status_code == 200, first.text
        assert first.json()['payments'][0]['profit_is_manual'] is True
    last = await api.post(f'/receivables/{debt_id}/pay', json={'amount': 100, 'payment_date': today_iso(), 'request_id': uuid.uuid4().hex})
    assert last.status_code == 200, last.text
    assert last.json()['payments'][-1]['profit_amount'] == 100


async def test_legacy_native_invoice_reads_recalculate_saved_snapshot_without_writing(isolated):
    db, api, _, _ = isolated
    pid = await product(db, price=100000)
    tx = (await api.post('/transactions', json=checkout(pid))).json()
    await db.transactions.update_one({'id': tx['id']}, {'$set': {'total_profit': 79999, 'total_cost': 20001, 'spreadsheet_profit': 79999}})
    await db.transaction_details.update_one({'transaction_id': tx['id']}, {'$set': {'cost_price': 20001, 'spreadsheet_profit': 79999}, '$unset': {'source_cost_price': ''}})
    # A later master edit must not affect the saved price/cost snapshot.
    await db.products.update_one({'id': pid}, {'$set': {'cost_price': 90000, 'selling_price': 200000}})
    r = await api.get('/transactions/' + tx['id'])
    assert r.status_code == 200, r.text
    assert (r.json()['total_amount'], r.json()['total_cost'], r.json()['total_profit']) == (100000, 25000, 75000)
    assert (await db.transactions.find_one({'id': tx['id']}))['total_profit'] == 79999


async def test_payment_retry_keeps_first_recognition_and_rejects_changed_manual_override(isolated):
    db, api, _, _ = isolated
    pid = await product(db)
    await db.customers.insert_one({'id': 'c', 'name': 'Customer'})
    tx = (await api.post('/transactions', json=checkout(pid, payment_method='credit', customer_id='c', due_date='2099-01-01'))).json()
    debt_id = (await db.accounts_receivable.find_one({'transaction_id': tx['id']}))['id']
    payload = {'amount': 100, 'payment_date': today_iso(), 'request_id': uuid.uuid4().hex}
    first = await api.post(f'/receivables/{debt_id}/pay', json=payload)
    repeat = await api.post(f'/receivables/{debt_id}/pay', json=payload)
    assert first.status_code == repeat.status_code == 200
    assert first.json()['payments'] == repeat.json()['payments']
    assert repeat.json()['payments'][0]['profit_amount'] == 100
    changed = await api.post(f'/receivables/{debt_id}/pay', json={**payload, 'profit_amount': 5000})
    assert changed.status_code == 409
    assert (await db.accounts_receivable.find_one({'id': debt_id}))['paid_amount'] == 100


async def test_native_payment_does_not_include_cached_source_group(isolated):
    db, api, _, _ = isolated
    pid = await product(db)
    await db.customers.insert_one({'id': 'c', 'name': 'Customer'})
    tx = (await api.post('/transactions', json=checkout(pid, payment_method='credit', customer_id='c', due_date='2099-01-01'))).json()
    debt_id = (await db.accounts_receivable.find_one({'transaction_id': tx['id']}))['id']
    source = {'kind': 'credit_sale', 'date': today_iso(), 'customer': 'CUSTOMER', 'profit': 12345, 'fee': 50000}
    await db.excel_events.insert_one(dict(source))
    await db.excel_events.insert_one({**source, 'customer': 'Other customer', 'profit': 999999})
    await db.transactions.insert_one({'id': 'source-invoice', 'date_key': today_iso(), 'customer_name': 'Customer',
                                     'payment_method': 'credit', 'status': 'completed', 'import_source': 'store_current',
                                     'spreadsheet_profit': 12345, 'service_fee': 50000})
    paid = await api.post(f'/receivables/{debt_id}/pay', json={'amount': 100, 'payment_date': today_iso(), 'request_id': uuid.uuid4().hex})
    assert paid.status_code == 200, paid.text
    assert paid.json()['payments'][0]['profit_amount'] == 100
