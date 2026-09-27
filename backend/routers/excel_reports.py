"""Two explicitly separate spreadsheet profiles; original margin report is retained."""
import asyncio
import math
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from lib.auth import require_admin
from lib.db import db
from lib.dates import today_iso
from lib.debts import hydrate
from lib.excel_rules import store_report, september_report
from lib.workbooks import dataset, SEPT_CELLS

router = APIRouter(prefix='/excel', tags=['excel-reports'], dependencies=[Depends(require_admin)])


async def live_events(include_imported=True):
    events = await db.excel_events.find({}, {'_id': 0}).to_list(None) if include_imported else []
    txs = await db.transactions.find({'import_source': {'$exists': False}}, {'_id': 0}).to_list(None)
    details = await db.transaction_details.find({'transaction_id': {'$in': [t['id'] for t in txs]}}, {'_id': 0}).to_list(None)
    by_tx = {}
    for d in details: by_tx.setdefault(d['transaction_id'], []).append(d)
    for t in txs:
        for d in by_tx.get(t['id'], []):
            e = dict(date=t['date_key'], kind='cash_sale' if t['payment_method'] == 'cash' else 'credit_sale', amount=d['subtotal'], fee=d.get('spreadsheet_fee', d['service_fee'] * d['qty']), profit=d.get('spreadsheet_profit', d['subtotal']-d['cost_price']*d['qty']), category=d.get('category', 'TIRE'))
            events.append(e)
            if t.get('return_date'):
                events.append({**e, 'date': t['return_date'], 'amount': -e['amount'], 'fee': -e['fee'], 'profit': -e['profit']})
    for collection, kind in [(db.accounts_receivable, 'credit_payment'), (db.accounts_payable, 'supplier_payment')]:
        async for debt in collection.find({}, {'_id': 0}):
            for p in debt.get('payments', []):
                events.append(dict(date=p['payment_date'], kind=kind, amount=p['amount'], profit=p.get('profit_amount', 0)))
            if kind == 'credit_payment' and debt.get('return_date') and debt.get('refund_amount'):
                events.append(dict(date=debt['return_date'], kind=kind, amount=-debt['refund_amount'], profit=-sum(p.get('profit_amount', 0) for p in debt.get('payments', []))))
    async for e in db.expenses.find({'import_source': {'$exists': False}}, {'_id': 0}):
        events.append(dict(date=e['date'], kind='expense', amount=e['amount'], category=e['category']))
    return events


@router.get('/reports')
async def reports(month: str = Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'), origin: str = Query(default='live', pattern='^(live|preview)$')):
    if origin == 'preview':
        store, september = await asyncio.gather(asyncio.to_thread(dataset, 'store'), asyncio.to_thread(dataset, 'september'))
        check = next((c for c in store['checks'] if c['month'] == month), None)
        sc = september['checks'][0] if month == '2026-08' else None
        return {'month': month, 'origin': origin, 'store': check['actual'] if check else None,
                'store_check': check, 'september': sc['actual'] if sc else None, 'september_check': sc,
                'inputs': september['inputs'] if sc else None, 'parameters_saved': False,
                'notice': 'Pratinjau file asli, BELUM transaksi kasir. File bernama September berisi laporan Agustus 2026.',
                'months': sorted({c['month'] for c in store['checks']}, reverse=True)}
    events = await live_events()
    store = store_report(events, month)
    snapshot = await db.excel_snapshots.find_one({'source': 'september', 'month': month}, {'_id': 0})
    # September snapshot and Store workbook intentionally never merge as one historical source.
    sept_events = await live_events(include_imported=False) if snapshot else events
    base = store_report(sept_events, month)
    inputs = {k: 0.0 for k in SEPT_CELLS}
    inputs.update(pendapatan_toko=base['modal'], pendapatan_laba=base['laba'], spooring=base['spooring'], distributor=base['supplier'])
    for e in sept_events:
        if e['date'][:7] != month: continue
        if e['kind'] == 'cash_sale' and e.get('category', '').upper() == 'OIL': inputs['oli'] += e['amount']
        if e['kind'] != 'expense': continue
        cat = e.get('category', '').lower()
        key = 'gaji' if 'gaji' in cat else 'pajak' if cat == 'pajak' else 'cicilan_mesin' if cat == 'cicilan mesin' else 'operasional' if cat == 'operasional' else 'pengeluaran'
        inputs[key] += e['amount']
    if snapshot:
        for k, value in snapshot['inputs'].items(): inputs[k] += value
    if month == today_iso()[:7] and not snapshot:
        products = await db.products.find({}, {'_id': 0}).to_list(None)
        inputs['stok'] = sum(p['stock']*p['cost_price'] for p in products if p['type'] == 'barang')
        for name, collection in [('piutang', db.accounts_receivable), ('hutang', db.accounts_payable)]:
            inputs[name] = sum([hydrate(d)['remaining'] async for d in collection.find({}, {'_id': 0})])
    parameters = await db.excel_parameters.find_one({'month': month}, {'_id': 0})
    if parameters: inputs.update(parameters['values'])
    saved = bool(parameters)
    current_events = [e for e in events if e['date'][:7] == month]
    cash = {'income': sum(e['amount'] for e in current_events if e['kind'] in ('cash_sale', 'credit_payment')),
            'supplier': sum(e['amount'] for e in current_events if e['kind'] == 'supplier_payment'),
            'expenses': sum(e['amount'] for e in current_events if e['kind'] == 'expense')}
    cash['net'] = cash['income'] - cash['supplier'] - cash['expenses']
    historical_missing = month != today_iso()[:7] and not snapshot and not all(k in (parameters or {}).get('values', {}) for k in ('stok', 'piutang', 'hutang'))
    return {'month': month, 'origin': origin, 'store': store, 'september': september_report(inputs), 'inputs': inputs,
            'parameters_saved': saved, 'overrides': (parameters or {}).get('values', {}), 'cash': cash, 'asset_snapshot_missing': historical_missing,
            'notice': ('Snapshot September/Agustus yang disetujui + transaksi POS baru; sumber Store tidak dicampurkan ke snapshot ini.' if snapshot else 'Data kasir tersimpan. Kategori produk menentukan pemisahan modal/laba/spooring/oli. Parameter manual menggantikan nilai otomatis, bukan ditambahkan dua kali.'),
            'months': sorted(set([today_iso()[:7], month]+[e['date'][:7] for e in events]), reverse=True)}


class Parameters(BaseModel):
    values: dict[str, float]


@router.get('/stock-snapshot')
async def stock_snapshot(source: str = Query(default='september', pattern='^(september|store)$')):
    """Referensi read-only: snapshot stok dari workbook (September = Laporan Data Barang, 2 Juni 2026). TIDAK mengubah stok produk."""
    data = await asyncio.to_thread(dataset, source)
    current = {p['name'].casefold(): p['stock'] async for p in db.products.find({'type': 'barang'}, {'_id': 0, 'name': 1, 'stock': 1})}
    rows = []
    total_value = 0.0
    for p in data['products']:
        val = p['stock'] * p['cost_price']
        total_value += val
        cur = current.get(p['name'].casefold())
        rows.append({'name': p['name'], 'sku': p['sku'], 'snapshot_stock': p['stock'], 'cost_price': p['cost_price'],
                     'selling_price': p['selling_price'], 'value': val, 'current_stock': cur,
                     'diff': None if cur is None else cur - p['stock'], 'matched': cur is not None})
    rows.sort(key=lambda r: r['value'], reverse=True)
    official = data.get('inputs', {}).get('stok') if source == 'september' else None
    return {'source': source, 'snapshot_date': '2026-06-02' if source == 'september' else None,
            'count': len(rows), 'total_value': round(total_value), 'official_total': official,
            'matched_count': sum(1 for r in rows if r['matched']), 'rows': rows,
            'note': 'Snapshot stok bertanggal 2 Juni 2026 dari sheet "Laporan Data Barang". Hanya referensi untuk perbandingan; stok produk aktif TIDAK diubah. Nilai resmi laporan aset memakai angka workbook (B19).'}


@router.put('/parameters/{month}')
async def set_parameters(month: str, body: Parameters, user: dict = Depends(require_admin)):
    try: datetime.strptime(month, '%Y-%m')
    except ValueError: raise HTTPException(422, 'Periode tidak valid')
    if any(k not in SEPT_CELLS or not math.isfinite(v) or abs(v) > 1e15 for k, v in body.values.items()):
        raise HTTPException(422, 'Parameter atau nominal tidak valid')
    doc = {'month': month, 'values': body.values, 'recorded_by': user['id'], 'updated_at': datetime.now(timezone.utc).isoformat()}
    await db.excel_parameters.update_one({'month': month}, {'$set': doc}, upsert=True)
    return doc