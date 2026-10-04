"""Compare Get Data with the actual Apps Script source columns, not app formulas."""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import uuid

import openpyxl
import pytest

from lib.custom_report import get_data_report
from lib.sales import GET_DATA_ROW_LIMIT, excel_sale_amount, excel_sales_summary
from tests.test_financial_safety import isolated, product, checkout


REFERENCE = Path(__file__).resolve().parents[2] / 'refrensi-spreadsheet' / 'Perkasa Jaya - Store information system (1).xlsx'
MONTHS = [f'{year}-{month:02d}' for year in (2025, 2026)
          for month in range(1, 13) if (year, month) <= (2026, 9)]


@pytest.fixture(scope='module')
def script_source():
    workbook = openpyxl.load_workbook(REFERENCE, read_only=True, data_only=True)
    selected = {'sales': [], 'purchases': []}
    for sheet in ('SELLING CASH', 'SELLING CREDIT', 'PURCHASE'):
        for values in workbook[sheet].iter_rows(min_row=2, values_only=True):
            credit = sheet == 'SELLING CREDIT'
            purchase = sheet == 'PURCHASE'
            day = values[3] if purchase else values[2]
            if not isinstance(day, (date, datetime)):
                continue
            # These column indexes and conditions are literal Code.gs 689–732/761–771.
            if credit:
                if values[18] != 'Tire':
                    continue
                amount = values[14] or 0
            elif purchase:
                if str(values[5]) not in ('1', '1.0'):
                    continue
                amount = values[13] or 0
            else:
                if str(values[15]) not in ('1', '1.0'):
                    continue
                amount = values[8] or 0
            selected['purchases' if purchase else 'sales'].append(
                (day.strftime('%Y-%m'), Decimal(str(amount))))
    workbook.close()
    return selected


@pytest.mark.parametrize('kind', ['sales', 'purchases'])
@pytest.mark.parametrize('month', MONTHS)
async def test_get_data_matches_script_all_historical_months(script_source, kind, month):
    expected = [amount for period, amount in script_source[kind] if period == month]
    report = await get_data_report(month, kind, origin='preview', page_size=None)
    assert report['filename'] == REFERENCE.name
    assert report['count'] == len(expected)
    assert Decimal(str(report['total'])) == sum(expected[:GET_DATA_ROW_LIMIT], Decimal(0))
    assert Decimal(str(report['full_total'])) == sum(expected, Decimal(0))
    assert all(row['vat_amount'] is None and row['amount_without_vat'] is None
               for row in report['rows'])


def test_credit_eligibility_and_cash_price_are_independent_of_master_tax():
    row = dict(payment_method='credit', category='TIRE', tax=0,
               qty=2, base_price=100000, price=120000, net=230000)
    assert excel_sale_amount(row) == 200000
    assert excel_sale_amount({**row, 'category': 'SERVICE', 'tax': 1}) is None
    assert excel_sale_amount({**row, 'payment_method': 'cash', 'tax': 1}) == 230000
    assert excel_sale_amount({**row, 'payment_method': 'cash', 'tax': 0}) is None


def test_report_u4_range_and_cash_before_credit_order():
    rows = [dict(payment_method='credit', category='TIRE', tax=0,
                 qty=1, cash_subtotal=900000, source_row=2, date='2026-09-01')]
    rows.extend(dict(payment_method='cash', tax=1, net=1000, source_row=index + 2,
                     date='2026-09-01') for index in range(GET_DATA_ROW_LIMIT))
    base, full, count = excel_sales_summary(rows)
    assert base == 996000
    assert full == 1896000
    assert count == 997


async def test_live_get_data_and_tax_use_cash_price_not_tempo_total(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db, price=100000)
    await db.products.update_one({'id': pid}, {'$set': {'tax': 0, 'category': 'TIRE'}})
    await db.customers.insert_one({'id': 'customer', 'name': 'Excel customer'})
    response = await api.post('/transactions', json=checkout(
        pid, items=[{'product_id': pid, 'qty': 2, 'credit_surcharge': 20000}],
        payment_method='credit', customer_id='customer', due_date='2099-01-01',
        request_id=uuid.uuid4().hex))
    assert response.status_code == 201, response.text
    transaction = response.json()
    assert transaction['total_amount'] == 240000
    month = transaction['date_key'][:7]
    get_data = (await api.get('/books/get-data', params={'month': month})).json()
    assert get_data['count'] == 1 and get_data['total'] == 200000
    assert get_data['pph_final'] == 1000
    sales = (await api.get('/books/sales', params={'month': month})).json()
    assert sales['net'] == 240000 and sales['tax_base'] == 200000
    filtered = (await api.get('/books/get-data', params={'month': month, 'tax': '1'})).json()
    assert filtered['count'] == 0


async def test_live_get_data_reversal_uses_original_cash_basis(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db, price=100000)
    await db.products.update_one({'id': pid}, {'$set': {'tax': 0, 'category': 'TIRE'}})
    await db.customers.insert_one({'id': 'customer', 'name': 'Excel customer'})
    response = await api.post('/transactions', json=checkout(
        pid, payment_method='credit', customer_id='customer', due_date='2099-01-01',
        items=[{'product_id': pid, 'qty': 1, 'credit_surcharge': 20000}]))
    transaction = response.json()
    await db.transactions.update_one({'id': transaction['id']}, {'$set': {
        'date_key': '2025-01-31', 'status': 'returned', 'return_date': '2025-02-01'}})
    january = (await api.get('/books/get-data', params={'month': '2025-01'})).json()
    february = (await api.get('/books/get-data', params={'month': '2025-02'})).json()
    assert january['total'] == 100000 and february['total'] == -100000
    assert january['pph_final'] == 500 and february['pph_final'] == -500
