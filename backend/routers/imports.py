"""Explicit preview/approval. Stable IDs, source hashes, no silent stock replay or inferred receipts."""
import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from lib.auth import require_admin
from lib.db import db
from lib.debts import financial_lock
from lib.workbooks import dataset

router = APIRouter(prefix='/imports', tags=['imports'], dependencies=[Depends(require_admin)])
GROUPS = ('products', 'history', 'receivables', 'payables', 'reference', 'purchases', 'transfers', 'customers', 'suppliers', 'source_rows')


def stable(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, '|'.join(map(str, parts))))


async def prepare(source):
    if source not in ('store', 'september', 'store_current'): raise HTTPException(404, 'Sumber tidak ditemukan')
    raw = await asyncio.to_thread(dataset, source)
    existing = await db.products.find({}, {'_id': 0, 'sku': 1, 'name': 1, 'import_source': 1, 'source_row': 1}).to_list(None)
    names = {p['name'].casefold() for p in existing}; skus = {p['sku'] for p in existing}
    groups = {k: [dict(r) for r in raw.get(k, [])] for k in ('products', 'receivables', 'payables', 'purchases', 'transfers', 'customers', 'suppliers', 'source_rows')}
    seen = set()
    for row in groups['products']:
        same_source = source == 'store_current' and any(p.get('import_source') == source and p.get('source_row') == row['row'] for p in existing)
        if not same_source and (row['name'].casefold() in names or row['sku'] in skus): row['issue'] = 'Nama/SKU sudah ada; tidak ditimpa'
        if source != 'store_current' and row['name'].casefold() in seen: row['issue'] = 'Nama produk ganda dalam sumber; perlu digabung manual'
        seen.add(row['name'].casefold())
    grouped = defaultdict(list)
    for e in raw['events']:
        if e['kind'] in ('cash_sale', 'credit_sale'):
            grouped[(e['date'], e['invoice'], e.get('customer', ''), e['kind'])].append(e)
    groups['history'] = []
    for key, lines in grouped.items():
        lines = [e for e in lines if not (e['qty'] == 0 and e['amount'] == 0)]  # buang baris kosong/nyampah (qty & nominal nol)
        if not lines: continue
        issue = '' if all(e['qty'] > 0 and e['qty'] == int(e['qty']) and e['amount'] >= 0 and e['name'] for e in lines) else 'Qty/nama/nominal historis tidak valid'
        groups['history'].append({'row': lines[0]['row'], 'sheet': lines[0]['sheet'], 'date': key[0], 'invoice': key[1], 'party': key[2], 'method': 'cash' if key[3] == 'cash_sale' else 'credit', 'amount': sum(e['amount'] for e in lines), 'lines': lines, 'issue': issue})
    groups['reference'] = [{'row': 1, 'sheet': 'Laporan Laba - Rugi', 'month': '2026-08', 'issue': ''}] if source == 'september' else []
    return raw, groups


@router.get('/preview')
async def preview(source: str = 'store', group: str = 'products', page: int = Query(default=1, ge=1), issues_only: bool = False):
    if group not in GROUPS: raise HTTPException(422, 'Kelompok tidak valid')
    raw, groups = await prepare(source)
    batches = await db.import_batches.find({'source': source}, {'_id': 0}).to_list(None)
    completed = [b['group'] for b in batches if b['status'] == 'completed']
    summary = {k: {'total': len(v), 'ready': sum(not r['issue'] for r in v), 'blocked': sum(bool(r['issue']) for r in v), 'imported': k in completed} for k, v in groups.items()}
    warnings = list(raw['warnings'])
    if source == 'store' and await db.import_batches.find_one({'source':'store_current', 'status':'completed'}):
        warnings.insert(0, 'Sumber ini arsip lama. Sumber Store terbaru sudah aktif; impor ulang arsip dinonaktifkan.')
        for info in summary.values(): info['ready'] = 0
    if source == 'store_current':
        warnings.insert(0, 'Sumber Store terbaru sudah aktif. Kelompok bertanda Sudah diimpor telah dimigrasikan; saldo agregat yang belum memiliki invoice tetap arsip.' if completed else 'Migrasi lengkap dipersiapkan dalam database kandidat. Impor parsial ditahan agar tidak menggandakan impor lama.')
        for info in summary.values():
            if not info['imported']: info['ready'] = 0
    if summary['history']['blocked']:
        summary['history']['ready'] = 0
        warnings.append('Kelompok riwayat ditahan seluruhnya sampai transaksi bermasalah direkonsiliasi; gunakan filter Hanya bermasalah. Ini mencegah ledger laporan berbeda dari riwayat POS.')
    filtered = [r for r in groups[group] if not issues_only or r['issue']]
    rows = [{k: v for k, v in r.items() if k != 'lines'} for r in filtered[(page-1)*20:page*20]]
    return {'source': source, 'digest': raw['digest'], 'summary': summary, 'rows': rows, 'group': group, 'page': page,
            'warnings': warnings, 'checks': raw['checks'], 'committed_groups': completed, 'filtered_total': len(filtered),
            'notice': 'Pratinjau saja. Baris bermasalah tidak akan disimpan. Riwayat tidak menambah/mengurangi stok akhir.'}


class Commit(BaseModel):
    source: str
    digest: str
    groups: list[str]
    confirmed: bool = False


async def insert_once(collection, doc):
    await collection.update_one({'id': doc['id']}, {'$setOnInsert': doc}, upsert=True)


@router.post('/commit')
async def commit(body: Commit, user: dict = Depends(require_admin)):
    if body.source == 'store_current':
        raise HTTPException(409, 'Gunakan migrasi kandidat untuk sumber baru; impor parsial berisiko menggandakan data lama.')
    if not body.confirmed or not body.groups or any(g not in GROUPS for g in body.groups): raise HTTPException(422, 'Pilih kelompok dan konfirmasi pemeriksaan terlebih dahulu')
    async with financial_lock:
        if body.source == 'store' and await db.import_batches.find_one({'source':'store_current','status':'completed'}):
            raise HTTPException(409, 'Sumber Store terbaru sudah aktif. Arsip lama tidak boleh diimpor ulang.')
        raw, groups = await prepare(body.source)
        if body.digest != raw['digest']: raise HTTPException(409, 'File berubah; buka pratinjau terbaru')
        if 'history' in body.groups and any(r['issue'] for r in groups['history']):
            raise HTTPException(422, 'Impor riwayat ditahan: ada transaksi dengan qty/nama/nominal tidak valid. Rekonsiliasi baris bermasalah agar ledger dan riwayat POS tetap sama.')
        if any(any(abs(v) > 0.01 for v in c['differences'].values()) for c in raw['checks']): raise HTTPException(409, 'Rumus belum rekonsiliasi; impor ditahan')
        results = {}
        for group in dict.fromkeys(body.groups):
            batch_id = stable(body.digest, group)
            done = await db.import_batches.find_one({'id': batch_id}, {'_id': 0})
            if done and done['status'] == 'completed': results[group] = {'status': 'already_imported', 'count': done['count']}; continue
            valid = [r for r in groups[group] if not r['issue']]
            if not valid: results[group] = {'status': 'blocked', 'count': 0}; continue
            await db.import_batches.update_one({'id': batch_id}, {'$set': {'source': body.source, 'group': group, 'status': 'processing', 'recorded_by': user['id']}}, upsert=True)
            count = 0
            from pymongo import UpdateOne
            tx_ops, detail_ops = [], []
            name_to_id = {p['name']: p['id'] for p in await db.products.find({}, {'_id': 0, 'name': 1, 'id': 1}).to_list(None)} if group == 'history' else {}
            for r in valid:
                rid = stable(body.digest, group, r['sheet'], r['row'])
                meta = {'id': rid, 'import_source': body.source, 'source_row': r['row'], 'source_sheet': r['sheet']}
                if group == 'products':
                    doc = {k: v for k, v in r.items() if k not in ('row', 'sheet', 'issue')}; doc.update(meta)
                    if doc['type'] == 'jasa': doc['stock'] = 0
                    await insert_once(db.products, doc)
                elif group in ('receivables', 'payables'):
                    party_collection = db.customers if group == 'receivables' else db.suppliers
                    existing_party = await party_collection.find_one({'name': r['party']}, {'_id': 0})
                    party_id = existing_party['id'] if existing_party else stable('party', group, r['party'].casefold())
                    await insert_once(party_collection, {'id': party_id, 'name': r['party'], 'phone': '', 'address': ''})
                    doc = {**meta, 'amount': r['amount'], 'paid_amount': r['paid_amount'], 'remaining': r['remaining'], 'status': 'paid' if r['remaining'] == 0 else 'partial' if r['paid_amount'] else 'unpaid', 'due_date': r['due_date'], 'issued_date': r['issued_date'], 'invoice_number': r.get('invoice') or f'XL-{group[:2].upper()}-{r["row"]}', 'payments': [], 'version': 0, 'legacy_payment_history_missing': r['paid_amount'] > 0}
                    if group == 'receivables': doc.update(transaction_id='', customer_id=party_id, customer_name=r['party'])
                    else: doc.update(supplier_id=party_id, supplier_name=r['party'])
                    await insert_once(db.accounts_receivable if group == 'receivables' else db.accounts_payable, doc)
                elif group == 'history':
                    lines = []
                    for e in r['lines']:
                        pid = name_to_id.get(e['name']) or stable('historical-product', e['name'])
                        lines.append({'id': stable(rid, e['row']), 'transaction_id': rid, 'product_id': pid, 'product_name': e['name'], 'product_type': 'jasa' if e['category'] in ('SERVICE', 'COMPLEMENTARY') else 'barang', 'qty': int(e['qty']), 'price': e['price'], 'cost_price': e['cost'], 'service_fee': e['fee']/e['qty'] if e['qty'] else 0, 'subtotal': e['amount'], 'category': e['category'], 'spreadsheet_cost': e['cost'], 'spreadsheet_profit': e['profit']})
                    tx = {**meta, 'invoice_number': f'XL-{r["date"].replace("-", "")}-{rid[:8]}', 'source_invoice': r['invoice'], 'date': datetime.fromisoformat(r['date']).replace(tzinfo=timezone.utc), 'date_key': r['date'], 'customer_id': None, 'customer_name': r['party'] or None, 'payment_method': r['method'], 'total_amount': r['amount'], 'barang_amount': sum(l['subtotal'] for l in lines if l['product_type'] == 'barang'), 'jasa_amount': sum(l['subtotal'] for l in lines if l['product_type'] == 'jasa'), 'total_cost': sum(l['cost_price']*l['qty'] for l in lines), 'service_fee': sum(l['service_fee']*l['qty'] for l in lines), 'total_profit': sum(l['spreadsheet_profit'] for l in lines), 'spreadsheet_profit': sum(l['spreadsheet_profit'] for l in lines), 'status': 'completed', 'due_date': r['lines'][0].get('due_date')}
                    tx_ops.append(UpdateOne({'id': tx['id']}, {'$setOnInsert': tx}, upsert=True))
                    detail_ops += [UpdateOne({'id': line['id']}, {'$setOnInsert': line}, upsert=True) for line in lines]
                else:
                    await db.excel_snapshots.update_one({'source': 'september', 'month': '2026-08'}, {'$setOnInsert': {'source': 'september', 'month': '2026-08', 'inputs': raw['inputs'], 'digest': raw['digest']}}, upsert=True)
                count += 1
            if group == 'history':
                # Report ledger preserves all original sheet rows, not a reconstruction from rounded POS data.
                for i in range(0, len(tx_ops), 1000):
                    await db.transactions.bulk_write(tx_ops[i:i+1000], ordered=False)
                for i in range(0, len(detail_ops), 1000):
                    await db.transaction_details.bulk_write(detail_ops[i:i+1000], ordered=False)
                ops = [UpdateOne({'id': stable(body.digest, e['sheet'], e['row'])}, {'$setOnInsert': {**e, 'id': stable(body.digest, e['sheet'], e['row']), 'import_source': body.source}}, upsert=True) for e in raw['events']]
                for i in range(0, len(ops), 2000):
                    await db.excel_events.bulk_write(ops[i:i+2000], ordered=False)
            await db.import_batches.update_one({'id': batch_id}, {'$set': {'status': 'completed', 'count': count, 'completed_at': datetime.now(timezone.utc).isoformat()}})
            results[group] = {'status': 'imported', 'count': count}
        return {'results': results, 'notice': 'Hanya baris lolos pemeriksaan yang disimpan; baris tertahan tetap membutuhkan rekonsiliasi.'}


class ResetDataInput(BaseModel):
    mode: Literal['testing_only', 'zero_transactions', 'zero_all', 'sync_store_current'] = 'zero_transactions'
    zero_product_stock: bool = True
    confirmation: str


async def _sync_store_current(user_id: str) -> dict:
    raw = await asyncio.to_thread(dataset, 'store_current')
    for name in (
        'transactions', 'transaction_details', 'checkout_requests', 'accounts_receivable',
        'accounts_payable', 'expenses', 'stock_in', 'excel_events', 'transfer_history',
        'purchase_history', 'excel_snapshots', 'excel_parameters', 'books_daily_parameters',
        'import_batches', 'products', 'customers', 'suppliers',
    ):
        await db[name].delete_many({})
    master = defaultdict(list)
    products = []
    for p in raw['products']:
        if p.get('issue'):
            continue
        doc = {k: v for k, v in p.items() if k not in ('row', 'sheet', 'issue', 'note')}
        doc.update(
            id=stable('store-master', p['row'], p['name']),
            import_source='store_current',
            source_row=p['row'],
            source_sheet='DATABASE',
            source_digest=raw['digest'],
            active=True,
        )
        if doc.get('type') == 'jasa':
            doc['stock'] = 0
        products.append(doc)
        master[p['name'].casefold()].append(doc)
    if products:
        await db.products.insert_many(products)
    for group in ('customers', 'suppliers'):
        seen_names = set()
        docs = []
        for p in raw.get(group, []):
            key = p['name'].strip().casefold()
            if key and key not in seen_names:
                seen_names.add(key)
                docs.append(dict(id=stable('store-party', group, key), name=p['name'], phone='', address='', source_code=p.get('code', '')))
        if docs:
            await db[group].insert_many(docs)
    parties = {p['name'].strip().casefold(): p['id'] for p in await db.customers.find({}, {'_id': 0, 'name': 1, 'id': 1}).to_list(None)}
    groups = defaultdict(list)
    for e in raw['events']:
        if e['kind'] in ('cash_sale', 'credit_sale'):
            if e['qty'] == 0 and e['amount'] == 0:
                continue
            if e['qty'] <= 0 or e['qty'] != int(e['qty']) or e['amount'] < 0:
                continue
            groups[(e['date'], e['invoice'], e.get('customer', ''), e['kind'])].append(e)
    transactions, details = [], []
    for key, entries in groups.items():
        txid = stable('store-history', *key)
        lines = []
        for e in entries:
            candidates = master.get(e['name'].casefold(), [])
            pid = candidates[0]['id'] if len(candidates) == 1 else stable('store-history-unresolved', e['name'])
            line = dict(
                id=stable(txid, e['sheet'], e['row']),
                transaction_id=txid,
                product_id=pid,
                product_name=e['name'],
                product_type='jasa' if e['category'] in ('SERVICE', 'COMPLEMENTARY') else 'barang',
                product_size=e.get('product_size', ''),
                product_brand=e.get('product_brand', ''),
                product_sku=candidates[0]['sku'] if len(candidates) == 1 else None,
                qty=int(e['qty']),
                price=e['price'],
                base_price=e['base_price'],
                cash_subtotal=e['cash_subtotal'],
                credit_surcharge=e['credit_surcharge'],
                discount_amount=e['discount_amount'],
                subtotal=e['amount'],
                cost_price=e['cost'],
                service_fee=e['fee'] / e['qty'] if e['qty'] else 0,
                spreadsheet_fee=e['fee'],
                spreadsheet_profit=e['profit'],
                category=e['category'],
                owner=e['owner'],
                tax=e['tax'],
                tax_source=e['tax_source'],
                source_row=e['row'],
                source_sheet=e['sheet'],
                import_source='store_current',
            )
            lines.append(line)
        tx = dict(
            id=txid,
            invoice_number='XL-' + key[0].replace('-', '') + '-' + txid[:8],
            source_invoice=key[1],
            date=datetime.fromisoformat(key[0]).replace(tzinfo=timezone.utc),
            date_key=key[0],
            customer_id=parties.get(key[2].strip().casefold()),
            customer_name=key[2] or None,
            payment_method='credit' if key[3] == 'credit_sale' else 'cash',
            source_payment_unallocated=key[3] == 'cash_sale',
            total_amount=sum(l['subtotal'] for l in lines),
            discount_total=sum(l['discount_amount'] for l in lines),
            barang_amount=sum(l['subtotal'] for l in lines if l['product_type'] == 'barang'),
            jasa_amount=sum(l['subtotal'] for l in lines if l['product_type'] == 'jasa'),
            total_cost=sum(l['cost_price'] * l['qty'] for l in lines),
            service_fee=sum(l['spreadsheet_fee'] for l in lines),
            total_profit=sum(l['spreadsheet_profit'] for l in lines),
            spreadsheet_profit=sum(l['spreadsheet_profit'] for l in lines),
            status='completed',
            due_date=entries[0].get('due_date'),
            import_source='store_current',
            source_row=entries[0]['row'],
            source_sheet=entries[0]['sheet'],
            source_digest=raw['digest'],
        )
        transactions.append(tx)
        details.extend(lines)
    for start in range(0, len(transactions), 1000):
        await db.transactions.insert_many(transactions[start:start + 1000])
    for start in range(0, len(details), 1000):
        await db.transaction_details.insert_many(details[start:start + 1000])
    for key, collection in [('events', 'excel_events'), ('purchases', 'purchase_history'), ('transfers', 'transfer_history')]:
        docs = [{**r, 'id': stable('store-source', key, r['sheet'], r['row']), 'import_source': 'store_current', 'source_digest': raw['digest']} for r in raw.get(key, [])]
        for start in range(0, len(docs), 1000):
            await db[collection].insert_many(docs[start:start + 1000])
    for group, count in [
        ('products', len(products)),
        ('history', len(transactions)),
        ('purchases', len(raw.get('purchases', []))),
        ('transfers', len(raw.get('transfers', []))),
        ('customers', len(raw.get('customers', []))),
        ('suppliers', len(raw.get('suppliers', []))),
        ('source_rows', len(raw.get('source_rows', []))),
    ]:
        await db.import_batches.insert_one(dict(
            id=stable(raw['digest'], group),
            source='store_current',
            group=group,
            status='completed',
            count=count,
            digest=raw['digest'],
            recorded_by=user_id,
        ))
    return {
        'products_synced': len(products),
        'transactions_synced': len(transactions),
        'events_synced': len(raw.get('events', [])),
    }


@router.post('/reset')
async def reset_data(body: ResetDataInput, user: dict = Depends(require_admin)):
    """Reset or zero out operational/testing data so the system is clean for fresh input or re-sync."""
    if body.confirmation.strip().upper() != 'NOLKAN':
        raise HTTPException(422, 'Ketik kata kunci NOLKAN untuk mengonfirmasi pengosongan data')
    async with financial_lock:
        deleted = {}
        if body.mode == 'sync_store_current':
            deleted = await _sync_store_current(user['id'])
            return {
                'mode': body.mode,
                'zero_product_stock': False,
                'deleted': deleted,
                'reset_at': datetime.now(timezone.utc).isoformat(),
                'recorded_by': user['id'],
                'notice': 'Data berhasil disinkronkan ulang dengan sumber Store terbaru.',
            }
        if body.mode == 'testing_only':
            test_txs = await db.transactions.find({'import_source': {'$exists': False}}, {'_id': 0, 'id': 1}).to_list(None)
            test_tx_ids = [t['id'] for t in test_txs]
            r_tx = await db.transactions.delete_many({'import_source': {'$exists': False}})
            r_det = await db.transaction_details.delete_many({'transaction_id': {'$in': test_tx_ids}}) if test_tx_ids else None
            r_chk = await db.checkout_requests.delete_many({})
            r_ar = await db.accounts_receivable.delete_many({'import_source': {'$exists': False}})
            r_ap = await db.accounts_payable.delete_many({'import_source': {'$exists': False}})
            r_exp = await db.expenses.delete_many({'import_source': {'$exists': False}})
            r_si = await db.stock_in.delete_many({'import_source': {'$exists': False}})
            r_dp = await db.books_daily_parameters.delete_many({})
            r_ep = await db.excel_parameters.delete_many({})
            await db.transactions.update_many(
                {'import_source': {'$exists': True}, 'status': 'returned'},
                {'$set': {'status': 'completed'}, '$unset': {'returned_at': '', 'return_date': '', 'return_reason': '', 'refund_amount': ''}},
            )
            for collection in (db.accounts_receivable, db.accounts_payable):
                async for debt in collection.find({'import_source': {'$exists': True}}):
                    baseline_payments = [p for p in debt.get('payments', []) if p.get('import_source') or p.get('report_excluded')]
                    if len(baseline_payments) != len(debt.get('payments', [])) or debt.get('return_date'):
                        paid = round(sum(float(p.get('amount', 0)) for p in baseline_payments), 2)
                        rem = max(0.0, round(float(debt.get('amount', 0)) - paid, 2))
                        status = 'paid' if rem == 0 else ('partial' if paid > 0 else 'unpaid')
                        await collection.update_one(
                            {'id': debt['id']},
                            {'$set': {'payments': baseline_payments, 'paid_amount': paid, 'remaining': rem, 'status': status},
                             '$unset': {'return_date': '', 'refund_amount': ''}},
                        )
            for src in ('store_current', 'store'):
                if await db.import_batches.find_one({'source': src, 'group': 'products', 'status': 'completed'}):
                    raw = await asyncio.to_thread(dataset, src)
                    for row in raw.get('products', []):
                        await db.products.update_many(
                            {'import_source': src, 'source_row': row['row']},
                            {'$set': {'stock': 0 if row.get('type') == 'jasa' else row['stock']}},
                        )
                    break
            if body.zero_product_stock:
                await db.products.update_many({'type': 'barang'}, {'$set': {'stock': 0}})
            deleted = {
                'transactions': r_tx.deleted_count,
                'transaction_details': r_det.deleted_count if r_det else 0,
                'checkout_requests': r_chk.deleted_count,
                'accounts_receivable': r_ar.deleted_count,
                'accounts_payable': r_ap.deleted_count,
                'expenses': r_exp.deleted_count,
                'stock_in': r_si.deleted_count,
                'daily_parameters': r_dp.deleted_count,
                'excel_parameters': r_ep.deleted_count,
            }
        else:
            tx_collections = (
                'transactions',
                'transaction_details',
                'checkout_requests',
                'accounts_receivable',
                'accounts_payable',
                'expenses',
                'stock_in',
                'excel_events',
                'transfer_history',
                'purchase_history',
                'excel_snapshots',
                'excel_parameters',
                'books_daily_parameters',
            )
            for name in tx_collections:
                res = await db[name].delete_many({})
                deleted[name] = res.deleted_count
            if body.mode == 'zero_all':
                for name in ('products', 'customers', 'suppliers', 'import_batches'):
                    res = await db[name].delete_many({})
                    deleted[name] = res.deleted_count
            else:
                res_batches = await db.import_batches.delete_many({'group': {'$nin': ['products', 'customers', 'suppliers']}})
                deleted['import_batches'] = res_batches.deleted_count
                if body.zero_product_stock:
                    res_prod = await db.products.update_many({'type': 'barang'}, {'$set': {'stock': 0}})
                    deleted['products_zeroed'] = res_prod.modified_count
        return {
            'mode': body.mode,
            'zero_product_stock': body.zero_product_stock,
            'deleted': deleted,
            'reset_at': datetime.now(timezone.utc).isoformat(),
            'recorded_by': user['id'],
            'notice': 'Data berhasil dibersihkan dan dinolkan. Sistem siap untuk testing dari 0 atau sinkronisasi data asli.',
        }
