import uuid
from datetime import datetime
import openpyxl
import pytest
from tests.test_financial_safety import isolated, product, checkout
from lib.store_current import enrich_current
from lib.custom_report import get_data_report
from tools.prepare_store_candidate import prepare_candidate


def source_data():
    w = openpyxl.Workbook()
    w.remove(w.active)
    for sheet in ['DATABASE', 'SELLING CASH', 'SELLING CREDIT', 'PURCHASE', 'TRANSFER']:
        w.create_sheet(sheet)
    for cell, value in {'C2':'Tyre','D2':'175/65 14','F2':'Test','G2':2,'H2':10000,'I2':5000,'J2':'IBU','K2':'1','L2':0,'M2':'Tire','Q2':-3,'W2':'Customer','V2':'C1','AE2':'Supplier','AD2':'D1'}.items():
        w['DATABASE'][cell] = value
    w['SELLING CASH']['O2'] = 'IBU'
    for cell, value in {'C2':datetime(2026,9,1),'D2':datetime(2026,8,31),'E2':'Supplier','F2':'1','G2':'PO1','H2':'IBU','I2':'Tyre','J2':2,'L2':5000,'M2':'Cash','N2':10000,'P2':'Tire'}.items():
        w['PURCHASE'][cell]=value
    for cell, value in {'C2':datetime(2026,9,1),'D2':9000,'E2':'BCA'}.items():
        w['TRANSFER'][cell]=value
    raw = {'filename':'test.xlsx','digest':'test-digest','events':[dict(row=2,sheet='SELLING CASH',date='2026-09-01',kind='cash_sale',invoice='INV1',name='Tyre',qty=1,price=10000,amount=9000,fee=0,cost=5000,profit=4000,category='TIRE',customer='')], 'receivables':[], 'payables':[], 'checks':[]}
    enrich_current(w,raw)
    return raw


def test_exact_stock_owner_and_tax_from_database():
    raw = source_data()
    p = raw['products'][0]
    assert p['stock'] == -3 and p['source_stock_opening'] == 2
    assert p['owner'] == 'ibu' and p['tax'] == 1 and not p['issue']
    assert raw['events'][0]['tax_source'] == 'DATABASE.K'
    assert raw['events'][0]['discount_amount'] == 1000
    assert raw['purchases'][0]['invoice_date'] == '2026-08-31'
    assert raw['transfers'][0]['method'] == 'BCA'


async def test_get_data_purchase_uses_invoice_month_and_preview_is_readonly(isolated, monkeypatch):
    db, api, user, _ = isolated
    user['role']='admin'
    from lib import custom_report
    monkeypatch.setattr(custom_report, 'dataset', lambda _:source_data())
    response = await api.get('/books/get-data', params={'month':'2026-08','report':'purchases','origin':'preview','owner':'ibu'})
    assert response.status_code==200, response.text
    r=response.json()
    assert r['total']==10000 and r['count']==1 and r['pph_final'] is None
    assert r['rows'][0]['date']=='2026-09-01' and r['rows'][0]['invoice_date']=='2026-08-31'
    assert r['rows'][0]['vat_amount'] is None
    assert (await api.get('/books/get-data',params={'month':'2026-09','report':'purchases','origin':'preview'})).json()['count']==0
    sales=(await api.get('/books/get-data',params={'month':'2026-09','origin':'preview'})).json()
    assert sales['total']==9000 and sales['pph_final']==45
    assert await db.products.count_documents({})==0
    assert await db.purchase_history.count_documents({})==0


async def test_candidate_preserves_source_live_sales_and_exact_master(isolated,tmp_path):
    db, api, _, _=isolated
    pid=await product(db,stock=8)
    await db.products.update_one({'id':pid},{'$set':{'sku':'XL-STORE-0002','name':'Tyre','import_source':'store','source_row':2}})
    sale=(await api.post('/transactions',json=checkout(pid))).json()
    target=db.client['bian_store_candidate_test_'+uuid.uuid4().hex]
    try:
        result=await prepare_candidate(db,target,source_data(),tmp_path)
        assert (await db.products.find_one({'id':pid}))['stock']==7
        p=await target.products.find_one({'id':pid})
        assert p['stock']==-3 and p['owner']=='ibu' and p['tax']==1
        assert await target.transactions.count_documents({})==2
        assert await target.transactions.find_one({'id':sale['id']})
        assert result['activated'] is False and result['preserved_live_transactions']==1
        assert await target.purchase_history.count_documents({})==1
        assert await target.spreadsheet_rows.count_documents({})>0
        with pytest.raises(ValueError,match='empty'):
            await prepare_candidate(db,target,source_data(),tmp_path)
    finally:
        assert target.name.startswith('bian_store_candidate_test_')
        await db.client.drop_database(target.name)


async def test_product_edit_keeps_import_provenance(isolated):
    db,api,user,_=isolated
    user['role']='admin'
    pid=await product(db)
    await db.products.update_one({'id':pid},{'$set':{'import_source':'store_current','source_row':2,'source_digest':'abc'}})
    response=await api.put('/products/'+pid,json={'selling_price':15000})
    assert response.status_code==200
    p=await db.products.find_one({'id':pid})
    assert p['import_source']=='store_current' and p['source_row']==2 and p['source_digest']=='abc'


async def test_source_current_cannot_be_imported_over_existing_data(isolated):
    db,api,user,_=isolated
    user['role']='admin'
    r=await api.post('/imports/commit',json={'source':'store_current','digest':'x','groups':['products'],'confirmed':True})
    assert r.status_code==409
    assert await db.products.count_documents({})==0


async def test_size_and_brand_are_snapshotted_for_credit_note(isolated):
    db,api,_,_=isolated
    pid=await product(db)
    await db.products.update_one({'id':pid},{'$set':{'brand':'Dunlop','size':'175/65 14'}})
    await db.customers.insert_one({'id':'c','name':'Customer','address':'Alamat lama'})
    r=await api.post('/transactions',json=checkout(pid,payment_method='credit',customer_id='c',due_date='2099-01-01'))
    assert r.status_code==201,r.text
    tx=r.json()
    await db.products.update_one({'id':pid},{'$set':{'brand':'Changed','size':'Changed'}})
    stored=(await api.get('/transactions/'+tx['id'])).json()
    assert stored['details'][0]['product_brand']=='Dunlop' and stored['details'][0]['product_size']=='175/65 14'
    assert stored['customer_address']=='Alamat lama'
