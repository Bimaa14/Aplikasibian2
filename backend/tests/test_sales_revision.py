"""Checkout/report regressions using disposable Mongo databases only."""
import uuid
import pytest
from tests.test_financial_safety import isolated, product, checkout, assert_clean
from lib.dates import today_iso


async def test_discount_tax_filters_and_snapshot(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    a, b = await product(db, price=10000), await product(db, price=30000)
    await db.products.update_one({'id': a}, {'$set': {'tax': 1, 'owner': 'bian', 'category': 'OIL'}})
    await db.products.update_one({'id': b}, {'$set': {'tax': 0, 'owner': 'ibu', 'category': 'TIRE'}})
    response = await api.post('/transactions', json=checkout(a, items=[{'product_id': a, 'qty': 1}, {'product_id': b, 'qty': 1}], discount_total=4000))
    assert response.status_code == 201, response.text
    tx = response.json()
    assert tx['total_amount'] == 36000
    assert [d['discount_amount'] for d in tx['details']] == [1000, 3000]
    await db.products.update_one({'id': a}, {'$set': {'tax': 0, 'owner': 'ibu'}})
    month = today_iso()[:7]
    report = (await api.get('/books/sales', params={'month': month, 'page_size': 1})).json()
    assert report['net'] == 36000 and report['line_count'] == 2 and len(report['rows']) == 1
    assert report['tax_base'] == 9000 and report['tax_amount'] == 45
    selected = (await api.get('/books/sales', params={'month': month, 'owner': 'bian', 'category': 'OIL', 'tax': '1'})).json()
    assert selected['net'] == 9000 and selected['line_count'] == 1
    tax = (await api.get('/books/tax', params={'month': month})).json()
    assert tax['pph_final'] == 45 and tax['omzet_base'] == 9000
    csv = await api.get('/books/sales/csv', params={'month': month, 'tax': '1'})
    assert csv.status_code == 200 and '9000.0' in csv.text and '30000.0' not in csv.text
    await assert_clean(db)


async def test_credit_surcharge_discount_and_payment(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db)
    await db.customers.insert_one({'id': 'customer', 'name': 'Customer'})
    body = checkout(pid, items=[{'product_id': pid, 'qty': 2, 'credit_surcharge': 2000}], discount_total=1000, payment_method='credit', customer_id='customer', due_date='2099-01-01')
    response = await api.post('/transactions', json=body)
    assert response.status_code == 201, response.text
    tx = response.json()
    assert tx['total_amount'] == 23000 and tx['details'][0]['price'] == 12000
    assert tx['details'][0]['base_price'] == 10000 and tx['total_profit'] == 13000
    debt = await db.accounts_receivable.find_one({'transaction_id': tx['id']})
    assert debt['amount'] == debt['remaining'] == 23000
    paid = await api.post('/receivables/' + debt['id'] + '/pay', json={'amount': 3000, 'payment_date': today_iso(), 'method': 'qris', 'request_id': uuid.uuid4().hex})
    assert paid.status_code == 200, paid.text
    assert paid.json()['remaining'] == 20000


@pytest.mark.parametrize('method', ['edc', 'transfer_bca', 'transfer_bri', 'transfer_bni', 'qris'])
async def test_non_cash_sale_return_and_daily_cash(isolated, method):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db)
    tx = (await api.post('/transactions', json=checkout(pid, payment_method=method, discount_total=1000))).json()
    assert tx['total_amount'] == 9000
    assert await db.accounts_receivable.count_documents({}) == 0
    daily = (await api.get('/books/daily', params={'date': today_iso()})).json()
    assert daily['cash_sales'] == 0 and daily['non_cash_sales'] == 9000
    url = '/transactions/' + tx['id'] + '/return'
    assert (await api.post(url, json={})).status_code == 422
    returned = await api.post(url, json={'refund_confirmed': True})
    assert returned.status_code == 200 and returned.json()['refund_amount'] == 9000
    report = (await api.get('/books/sales', params={'month': today_iso()[:7]})).json()
    assert report['net'] == 0 and report['line_count'] == 2


async def test_discount_rounding_and_legacy_tax(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    ids = [await product(db, price=1) for _ in range(3)]
    response = await api.post('/transactions', json=checkout(ids[0], items=[{'product_id': pid, 'qty': 1} for pid in ids], discount_total=0.01))
    assert response.status_code == 201, response.text
    assert response.json()['total_amount'] == 2.99
    assert sum(d['discount_amount'] for d in response.json()['details']) == .01
    report = (await api.get('/books/sales', params={'month': today_iso()[:7]})).json()
    assert report['tax_amount'] == 0 and report['unassigned_tax_net'] == 2.99


@pytest.mark.parametrize('extra', [{'discount_total': -1}, {'discount_total': 10001}, {'items': [{'product_id': 'replace', 'qty': 1, 'credit_surcharge': 100}]}])
async def test_invalid_pricing_does_not_change_stock(isolated, extra):
    db, api, _, _ = isolated
    pid = await product(db)
    if 'items' in extra:
        extra = {**extra, 'items': [{**extra['items'][0], 'product_id': pid}]}
    response = await api.post('/transactions', json=checkout(pid, **extra))
    assert response.status_code == 422, response.text
    assert (await db.products.find_one({'id': pid}))['stock'] == 5
    assert await db.transactions.count_documents({}) == 0
    await assert_clean(db)


@pytest.mark.parametrize('month', ['2026-00', '2026-13', '0000-01', 'bad'])
async def test_invalid_month(isolated, month):
    _, api, user, _ = isolated
    user['role'] = 'admin'
    assert (await api.get('/books/sales', params={'month': month})).status_code == 422


async def test_return_adjusts_its_own_month(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db)
    await db.products.update_one({'id': pid}, {'$set': {'tax': 1}})
    tx = (await api.post('/transactions', json=checkout(pid, discount_total=1000))).json()
    await db.transactions.update_one({'id': tx['id']}, {'$set': {'date_key': '2025-01-31', 'status': 'returned', 'return_date': '2025-02-01'}})
    january = (await api.get('/books/sales', params={'month': '2025-01'})).json()
    february = (await api.get('/books/sales', params={'month': '2025-02'})).json()
    assert january['net'] == 9000 and january['tax_amount'] == 45
    assert february['net'] == -9000 and february['tax_amount'] == -45
    assert february['rows'][0]['kind'] == 'return'


async def test_product_tax_edit_filter_and_validation(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db)
    response = await api.put('/products/' + pid, json={'tax': 1, 'owner': 'bian', 'category': 'OIL'})
    assert response.status_code == 200 and response.json()['tax'] == 1
    rows = (await api.get('/products', params={'tax': '1', 'owner': 'bian', 'category': 'OIL'})).json()
    assert [p['id'] for p in rows] == [pid]
    assert (await api.get('/products', params={'tax': '0'})).json() == []
    assert (await api.put('/products/' + pid, json={'tax': 2})).status_code == 422
