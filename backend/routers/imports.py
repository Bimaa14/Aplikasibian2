"""Explicit preview/approval. Stable IDs, source hashes, no silent stock replay or inferred receipts."""
import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from lib.auth import require_admin
from lib.db import db
from lib.debts import financial_lock
from lib.workbooks import dataset

router = APIRouter(prefix='/imports', tags=['imports'], dependencies=[Depends(require_admin)])
GROUPS = ('products', 'history', 'receivables', 'payables', 'reference')


def stable(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, '|'.join(map(str, parts))))


async def prepare(source):
    if source not in ('store', 'september'): raise HTTPException(404, 'Sumber tidak ditemukan')
    raw = await asyncio.to_thread(dataset, source)
    existing = await db.products.find({}, {'_id': 0, 'sku': 1, 'name': 1, 'import_source': 1}).to_list(None)
    names = {p['name'].casefold() for p in existing}; skus = {p['sku'] for p in existing}
    groups = {k: [dict(r) for r in raw.get(k, [])] for k in ('products', 'receivables', 'payables')}
    seen = set()
    for row in groups['products']:
        if row['name'].casefold() in names or row['sku'] in skus: row['issue'] = 'Nama/SKU sudah ada; tidak ditimpa'
        if row['name'].casefold() in seen: row['issue'] = 'Nama produk ganda dalam sumber; perlu digabung manual'
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
    if not body.confirmed or not body.groups or any(g not in GROUPS for g in body.groups): raise HTTPException(422, 'Pilih kelompok dan konfirmasi pemeriksaan terlebih dahulu')
    async with financial_lock:
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