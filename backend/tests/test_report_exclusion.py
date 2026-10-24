"""Sheet baseline exclusions affect report totals while preserving transaction history."""
from tests.test_financial_safety import isolated, product, checkout


async def test_excluded_sales_stay_in_history_and_future_unflagged_sales_count(isolated):
    db, api, user, _ = isolated
    user['role'] = 'admin'
    pid = await product(db, stock=5, price=100000)
    await db.products.update_one({'id': pid}, {'$set': {'tax': 1, 'category': 'TIRE'}})
    old = await api.post('/transactions', json=checkout(pid))
    assert old.status_code == 201, old.text
    old = old.json()
    await db.transactions.update_one({'id': old['id']}, {'$set': {'report_excluded': True}})
    month = old['date_key'][:7]
    empty = (await api.get('/books/get-data', params={'month': month})).json()
    assert empty['count'] == 0 and empty['total'] == 0 and empty['pph_final'] == 0

    future = await api.post('/transactions', json=checkout(pid))
    explicit = await api.post('/transactions', json=checkout(pid))
    assert future.status_code == explicit.status_code == 201
    future, explicit = future.json(), explicit.json()
    await db.transactions.update_one({'id': explicit['id']}, {'$set': {'report_excluded': False}})
    report = (await api.get('/books/sales', params={'month': month})).json()
    assert report['transaction_count'] == 2 and report['net'] == 200000
    assert report['tax_base'] == 200000 and report['tax_amount'] == 1000
    get_data = (await api.get('/books/get-data', params={'month': month})).json()
    assert get_data['count'] == 2 and get_data['total'] == 200000 and get_data['pph_final'] == 1000
    assert {row['transaction_id'] for row in report['rows']} == {future['id'], explicit['id']}
    assert await db.transactions.count_documents({}) == 3
    history = (await api.get('/transactions')).json()
    assert {transaction['id'] for transaction in history} == {old['id'], future['id'], explicit['id']}
    detail = await api.get(f"/transactions/{old['id']}")
    assert detail.status_code == 200 and detail.json()['details'][0]['subtotal'] == 100000
