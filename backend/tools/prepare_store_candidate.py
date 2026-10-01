"""Prepare, never activate, a complete Store migration in a separate database.

Run with backend/venv Python. Source database is read-only. Existing POS transactions
and September balances are preserved. Stated stock policy: exact DATABASE!Q snapshot.
"""
import asyncio
import hashlib
import json
import sys
import uuid
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bson import json_util
from lib.db import db, client
from lib.workbooks import dataset
from models.product import Product
from models.transaction import Transaction

ROOT = Path(__file__).resolve().parents[2]


def stable(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, '|'.join(map(str, parts))))


async def snapshot(database):
    result = {}
    for name in sorted(await database.list_collection_names()):
        result[name] = await database[name].find({}).sort('_id', 1).to_list(None)
    return result


def fingerprint(data):
    # Sessions/logging can change on reads; business records must remain unchanged.
    selected = {k: v for k, v in data.items() if k not in ('sessions', 'status_checks')}
    return hashlib.sha256(json_util.dumps(selected, sort_keys=True).encode()).hexdigest()


async def prepare_candidate(source, target, raw, output):
    if not target.name.startswith('bian_store_candidate_') or source.name == target.name:
        raise ValueError('Target must be a separate bian_store_candidate_ database')
    if await target.list_collection_names():
        raise ValueError('Candidate must be empty; existing databases are never overwritten')
    before = await snapshot(source)
    if before.get('financial_operations'):
        raise RuntimeError('Financial operation pending; let the application recover first')
    if fingerprint(before) != fingerprint(await snapshot(source)):
        raise RuntimeError('Source changed during snapshot; retry while no transactions are being entered')
    output.mkdir(parents=True, exist_ok=True)
    backup = output / 'source-backup.bson.json'
    backup.write_text(json_util.dumps(before), encoding='utf-8')
    for name, docs in before.items():
        if docs and name not in ('sessions', 'financial_operations'):
            await target[name].insert_many(docs)
        indexes = await source[name].index_information()
        for index_name, spec in indexes.items():
            if index_name != '_id_':
                options = {k: v for k, v in spec.items() if k in ('unique', 'sparse', 'expireAfterSeconds', 'partialFilterExpression')}
                await target[name].create_index(spec['key'], name=index_name, **options)
    old_sources = ['store', 'store_current']
    source_skus = {p['sku']: p for p in raw['products']}
    def managed(p):
        match = source_skus.get(p.get('sku'))
        return p.get('import_source') in old_sources or (match and match['name'].casefold() == p['name'].casefold())
    old_products = [p for p in before.get('products', []) if managed(p)]
    old_by_row = {p.get('source_row') or source_skus.get(p.get('sku'), {}).get('row'): p for p in old_products}
    old_tx = [t for t in before.get('transactions', []) if t.get('import_source') in old_sources]
    old_ids = [t['id'] for t in old_tx]
    # All deletions are scoped to the new, checked candidate database.
    await target.transaction_details.delete_many({'transaction_id': {'$in': old_ids}})
    for collection in ('products', 'transactions', 'excel_events', 'purchase_history', 'transfer_history', 'spreadsheet_rows'):
        await target[collection].delete_many({'import_source': {'$in': old_sources}})
    await target.products.delete_many({'id': {'$in': [p['id'] for p in old_products]}})
    await target.import_batches.delete_many({'source': {'$in': old_sources}})
    master = defaultdict(list)
    products = []
    for p in raw['products']:
        if p['issue']:
            raise ValueError(f"Product {p['row']}: {p['issue']}")
        doc = {k: v for k, v in p.items() if k not in ('row', 'sheet', 'issue', 'note')}
        prior = old_by_row.get(p['row'])
        # Reuse IDs only for a matching row AND name; preserve references used by live POS.
        doc.update(id=prior['id'] if prior and prior['name'].casefold() == p['name'].casefold() else stable('store-master', p['row'], p['name']),
                   import_source='store_current', source_row=p['row'], source_sheet='DATABASE', source_digest=raw['digest'])
        Product(**doc)
        products.append(doc)
        master[p['name'].casefold()].append(doc)
    live_products = [p for p in before.get('products', []) if not managed(p)]
    overlaps = {p['sku'] for p in live_products} & {p['sku'] for p in products}
    if overlaps:
        raise ValueError('Live SKU conflict: ' + ', '.join(sorted(overlaps)))
    if products:
        await target.products.insert_many(products)
    # Existing party IDs are retained. Workbook balances are archival, not fictitious invoices.
    for group in ('customers', 'suppliers'):
        existing = {p['name'].strip().casefold(): p for p in await target[group].find({}).to_list(None)}
        for p in raw[group]:
            key = p['name'].strip().casefold()
            if key not in existing:
                doc = dict(id=stable('store-party', group, key), name=p['name'], phone='', address='', source_code=p['code'])
                await target[group].insert_one(doc)
                existing[key] = doc
    parties = {p['name'].strip().casefold(): p['id'] for p in await target.customers.find({}).to_list(None)}
    groups = defaultdict(list)
    skipped = []
    for e in raw['events']:
        if e['kind'] in ('cash_sale', 'credit_sale'):
            if e['qty'] == 0 and e['amount'] == 0:
                skipped.append(dict(sheet=e['sheet'], row=e['row'], reason='Baris nol tersimpan di arsip sumber'))
                continue
            if e['qty'] <= 0 or e['qty'] != int(e['qty']) or e['amount'] < 0:
                raise ValueError(f"Invalid historical sale {e['sheet']}:{e['row']}")
            groups[(e['date'], e['invoice'], e.get('customer', ''), e['kind'])].append(e)
    transactions, details = [], []
    for key, entries in groups.items():
        txid = stable('store-history', *key)
        lines = []
        for e in entries:
            candidates = master.get(e['name'].casefold(), [])
            # A historical name alone cannot identify one of several duplicate master rows.
            pid = candidates[0]['id'] if len(candidates) == 1 else stable('store-history-unresolved', e['name'])
            line = dict(id=stable(txid, e['sheet'], e['row']), transaction_id=txid, product_id=pid,
                        product_name=e['name'], product_type='jasa' if e['category'] in ('SERVICE', 'COMPLEMENTARY') else 'barang',
                        product_size=e.get('product_size', ''), product_brand=e.get('product_brand', ''),
                        product_sku=candidates[0]['sku'] if len(candidates) == 1 else None,
                        qty=int(e['qty']), price=e['price'], base_price=e['base_price'], credit_surcharge=e['credit_surcharge'],
                        discount_amount=e['discount_amount'], subtotal=e['amount'], cost_price=e['cost'],
                        service_fee=e['fee']/e['qty'], spreadsheet_fee=e['fee'], spreadsheet_profit=e['profit'],
                        category=e['category'], owner=e['owner'], tax=e['tax'], tax_source=e['tax_source'],
                        source_row=e['row'], source_sheet=e['sheet'], import_source='store_current')
            lines.append(line)
        tx = dict(id=txid, invoice_number='XL-' + key[0].replace('-', '') + '-' + txid[:8], source_invoice=key[1],
                  date=datetime.fromisoformat(key[0]).replace(tzinfo=timezone.utc), date_key=key[0],
                  customer_id=parties.get(key[2].strip().casefold()), customer_name=key[2] or None,
                  payment_method='credit' if key[3] == 'credit_sale' else 'cash', source_payment_unallocated=key[3] == 'cash_sale',
                  total_amount=sum(l['subtotal'] for l in lines), discount_total=sum(l['discount_amount'] for l in lines),
                  barang_amount=sum(l['subtotal'] for l in lines if l['product_type']=='barang'),
                  jasa_amount=sum(l['subtotal'] for l in lines if l['product_type']=='jasa'),
                  total_cost=sum(l['cost_price']*l['qty'] for l in lines), service_fee=sum(l['spreadsheet_fee'] for l in lines),
                  total_profit=sum(l['spreadsheet_profit'] for l in lines), spreadsheet_profit=sum(l['spreadsheet_profit'] for l in lines),
                  status='completed', due_date=entries[0].get('due_date'), import_source='store_current',
                  source_row=entries[0]['row'], source_sheet=entries[0]['sheet'], source_digest=raw['digest'])
        Transaction(**tx)
        transactions.append(tx)
        details.extend(lines)
    async def insert_chunks(collection, docs):
        for start in range(0, len(docs), 1000):
            await target[collection].insert_many(docs[start:start+1000])
    await insert_chunks('transactions', transactions)
    await insert_chunks('transaction_details', details)
    for key, collection in [('events', 'excel_events'), ('purchases', 'purchase_history'), ('transfers', 'transfer_history'), ('source_rows', 'spreadsheet_rows')]:
        docs = [{**r, 'id': stable('store-source', key, r['sheet'], r['row']), 'import_source': 'store_current', 'source_digest': raw['digest']} for r in raw[key]]
        await insert_chunks(collection, docs)
    for group, count in [('products',len(products)), ('history',len(transactions)), ('purchases',len(raw['purchases'])), ('transfers',len(raw['transfers'])), ('customers',len(raw['customers'])), ('suppliers',len(raw['suppliers'])), ('source_rows',len(raw['source_rows']))]:
        await target.import_batches.insert_one(dict(id=stable(raw['digest'], group), source='store_current', group=group, status='completed', count=count, digest=raw['digest']))
    live_ids = [t['id'] for t in before.get('transactions', []) if t.get('import_source') not in old_sources]
    available = {p['id'] for p in await target.products.find({}, {'id':1}).to_list(None)}
    unresolved_live = [d['product_id'] async for d in target.transaction_details.find({'transaction_id': {'$in':live_ids}, 'product_id':{'$nin':list(available)}})]
    if unresolved_live:
        raise ValueError('Live product references would be lost: ' + str(len(unresolved_live)))
    if fingerprint(before) != fingerprint(await snapshot(source)):
        raise RuntimeError('Source changed while preparing candidate. Candidate must not be activated.')
    result = dict(source_database=source.name, candidate_database=target.name, source_fingerprint=fingerprint(before), digest=raw['digest'],
                  backup=str(backup), products=len(products), preserved_live_products=len(live_products),
                  historical_transactions=len(transactions), historical_lines=len(details), preserved_live_transactions=len(live_ids),
                  purchases=len(raw['purchases']), transfers=len(raw['transfers']), source_rows=len(raw['source_rows']),
                  negative_stock_rows=sum(p['stock']<0 for p in products), source_stock_total=sum(p['stock'] for p in products),
                  owners=dict(Counter(p.get('owner') for p in products)), tax=dict(Counter(str(p['tax']) for p in products)),
                  skipped_sales=skipped, activated=False,
                  limitations=['Stok barang impor persis DATABASE Q; transaksi POS lama dipertahankan tanpa memutar ulang pengurangan stok.',
                               'Saldo piutang/hutang September yang sudah ada tetap dipertahankan; saldo DATABASE diarsipkan tanpa membuat tagihan ganda.',
                               'TRANSFER tetap ledger terpisah; tidak ditebak sebagai metode pembayaran per invoice.',
                               'Baris master bernama sama tetap terpisah. Riwayat ambigu tidak boleh dipakai untuk retur otomatis.'])
    (output / 'migration-plan.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return result


async def main():
    name = 'bian_store_candidate_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    output = ROOT / 'test_reports' / 'spreadsheet' / name
    try:
        result = await prepare_candidate(db, client[name], dataset('store_current'), output)
    except BaseException:
        # This invocation owns this fresh candidate; the source and backup remain intact.
        assert name.startswith('bian_store_candidate_') and name != db.name
        await client.drop_database(name)
        raise
    print(json.dumps(result, indent=2, ensure_ascii=True))
    client.close()


if __name__ == '__main__':
    asyncio.run(main())
