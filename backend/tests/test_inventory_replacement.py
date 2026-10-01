from tools.replace_inventory import plan_inventory
from tests.test_financial_safety import isolated, product, checkout
from lib.excel_rules import line_values
import pytest


@pytest.mark.parametrize('kind,fee', [('jasa', 10000), ('jasa', 0), ('barang', 75000)])
@pytest.mark.parametrize('method', ['cash', 'credit'])
async def test_checkout_mechanic_fee_matches_master(isolated, kind, fee, method):
    db, api, _, _ = isolated
    pid = await product(db, price=200000)
    await db.products.update_one({'id': pid}, {'$set': {
        'type': kind, 'service_fee': fee,
        'category': 'SERVICE' if kind == 'jasa' else 'TIRE',
    }})
    options = {}
    if method == 'credit':
        await db.customers.insert_one({'id': 'customer', 'name': 'Test customer'})
        options = {'customer_id': 'customer', 'due_date': '2099-12-31'}
    response = await api.post('/transactions', json=checkout(
        pid, items=[{'product_id': pid, 'qty': 2}], payment_method=method,
        discount_total=10000, **options,
    ))
    assert response.status_code == 201, response.text
    tx = response.json()
    assert tx['service_fee'] == fee * 2
    assert tx['details'][0]['service_fee'] == fee
    assert tx['details'][0]['spreadsheet_fee'] == fee * 2
    assert tx['total_profit'] == 390000 - fee * 2 - (10000 if kind == 'barang' else 0)
    saved = (await api.get('/transactions/' + tx['id'])).json()
    assert saved['service_fee'] == fee * 2


def test_reference_tax_and_unknown_are_preserved():
    old = [dict(id='old', sku='A', name='Tyre', type='barang', stock=-7, tax=0, owner='bian')]
    reference = [dict(sku='A', name='Tyre', type='barang', tax=1, owner='ibu', row=19)]
    rows = [dict(sku='A', name='Tyre', stock=18, selling_price=100, cost_price=50, source_row=3),
            dict(sku='B', name='New', stock=2, selling_price=200, cost_price=80, source_row=4)]
    products, archive = plan_inventory(rows, old, reference, 'digest')
    assert products[0]['id'] == 'old'
    assert products[0]['stock'] == 18
    assert products[0]['tax'] == 1 and products[0]['owner'] == 'ibu'
    assert products[1]['tax'] is None and products[1]['owner'] is None
    assert products[1]['mapping_status'] == 'unmapped'
    assert not archive
    _, archive = plan_inventory(rows[1:], old, reference, 'digest')
    assert archive == ['old']


def test_service_fee_is_half_after_discount():
    values = line_values({'name': 'SERVICE', 'type': 'jasa', 'category': 'SERVICE',
                          'selling_price': 200000, 'cost_price': 0, 'service_fee': 30000}, 2, discount=100000)
    assert values['spreadsheet_fee'] == 150000
    assert values['spreadsheet_profit'] == 150000


@pytest.mark.parametrize('method', ['cash', 'credit'])
@pytest.mark.parametrize('qty', [1, 3])
async def test_service_commission_after_item_and_invoice_discounts(isolated, method, qty):
    db, api, _, _ = isolated
    service = await product(db, price=150000)
    other = await product(db, price=150000)
    await db.products.update_one({'id': service}, {'$set': {
        'name': ' Service ', 'type': 'jasa', 'category': 'SERVICE', 'cost_price': 0, 'service_fee': 999,
    }})
    await db.products.update_one({'id': other}, {'$set': {
        'name': 'SPOORING', 'type': 'jasa', 'category': 'SERVICE', 'cost_price': 0, 'service_fee': 10000,
    }})
    options = {}
    surcharge = 20000 if method == 'credit' else 0
    if method == 'credit':
        await db.customers.insert_one({'id': 'customer', 'name': 'Test customer'})
        options = {'customer_id': 'customer', 'due_date': '2099-12-31'}
    # Both lines have equal remaining totals, so invoice discount divides equally.
    response = await api.post('/transactions', json={
        'items': [{'product_id': service, 'qty': qty, 'credit_surcharge': surcharge, 'discount_amount': 30000 * qty},
                  {'product_id': other, 'qty': qty, 'credit_surcharge': surcharge, 'discount_amount': 30000 * qty}],
        'payment_method': method, 'discount_total': 10000, **options,
    })
    assert response.status_code == 201, response.text
    tx = response.json()
    net = (120000 + surcharge) * qty - 5000
    fee = net / 2
    assert tx['discount_total'] == 60000 * qty + 10000
    assert tx['service_fee'] == fee + 10000 * qty
    lines = {d['product_id']: d for d in tx['details']}
    assert lines[service]['subtotal'] == net
    assert lines[service]['spreadsheet_fee'] == fee
    assert lines[service]['service_fee'] * qty == pytest.approx(fee)
    assert lines[other]['spreadsheet_fee'] == 10000 * qty
    assert tx['total_profit'] == net * 2 - fee - 10000 * qty
    assert tx['spreadsheet_profit'] == tx['total_profit']
    saved = (await api.get('/transactions/' + tx['id'])).json()
    assert saved['service_fee'] == tx['service_fee']


async def test_item_discount_cannot_exceed_line_total(isolated):
    db, api, _, _ = isolated
    pid = await product(db, price=10000)
    response = await api.post('/transactions', json=checkout(pid, items=[{
        'product_id': pid, 'qty': 1, 'discount_amount': 10000.01,
    }]))
    assert response.status_code == 422
    assert await db.transactions.count_documents({}) == 0


async def test_archived_products_not_available_for_checkout(isolated):
    db, api, user, _ = isolated
    p = await product(db)
    await db.products.update_one({'id': p}, {'$set': {'active': False}})
    assert (await api.get('/products')).json() == []
    assert (await api.get('/products/' + p)).status_code == 404
    response = await api.post('/transactions', json=checkout(p))
    assert response.status_code in (400, 404)
    assert await db.products.count_documents({'id': p}) == 1
    assert await db.transactions.count_documents({}) == 0


async def test_replacement_keeps_history_and_backup(isolated, tmp_path, monkeypatch):
    import openpyxl
    from tools import replace_inventory
    db, api, user, _ = isolated
    old_id = await product(db)
    old = await db.products.find_one({'id': old_id})
    await db.transactions.insert_one({'id': 'history', 'amount': 123})
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Laporan Data Barang'
    sheet.append(['Inventory'])
    sheet.append(['No', 'Nama Barang', 'Kode Barang', 'Stok Barang', 'Harga Jual', 'Harga Beli'])
    sheet.append([1, old['name'], old['sku'], 8, 10000, 5000])
    sheet.append([2, 'New', 'NEW', 3, 20000, 10000])
    path = tmp_path / 'inventory.xlsx'
    workbook.save(path)
    monkeypatch.setattr(replace_inventory, 'db', db)
    monkeypatch.setattr(replace_inventory, 'dataset', lambda _: {'products': [{**old, 'tax': 1, 'owner': 'ibu', 'row': 7}]})
    output = tmp_path / 'backup'
    await replace_inventory.replace(path, output)
    updated = await db.products.find_one({'id': old_id})
    assert updated['stock'] == 8 and updated['tax'] == 1
    assert await db.transactions.count_documents({'id': 'history', 'amount': 123}) == 1
    assert await db.products.count_documents({'active': True}) == 2
    assert (output / 'backup.bson.json').is_file()
    assert await db.financial_operations.count_documents({}) == 0
