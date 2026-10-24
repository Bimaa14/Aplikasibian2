"""Reports based on the configured Store workbook and its cached source history."""
import asyncio
import math
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from lib.auth import require_admin
from lib.db import db
from lib.dates import today_iso
from lib.debts import hydrate
from lib.excel_rules import n, store_report, september_report
from lib.workbooks import dataset, SEPT_CELLS
from lib.source_sales import reference_sale_rows, overlay_sale_detail, overlay_sale_event, matched_source_sale

router = APIRouter(prefix='/excel', tags=['excel-reports'], dependencies=[Depends(require_admin)])


async def live_events(include_imported=True):
    events = await db.excel_events.find({}, {'_id': 0}).to_list(None) if include_imported else []
    source = None
    sale_source = None
    imported_current = [e for e in events if e.get('import_source') == 'store_current']
    if imported_current:
        source = await asyncio.to_thread(dataset, 'store_current')
        sale_source = await asyncio.to_thread(reference_sale_rows)
        by_source = {(e['sheet'], e['row']): e for e in source['events']}
        for event in imported_current:
            original = by_source.get((event.get('source_sheet') or event.get('sheet'),
                                      event.get('source_row') or event.get('row')))
            # Read missing metadata only when the row still describes this exact event.
            # Cached amounts/fees/profits, including manual corrections, never change.
            if not original or any(event.get(k) != original.get(k) for k in ('kind', 'date', 'amount')):
                continue
            if event.get('kind') in ('cash_sale', 'credit_sale'):
                if matched_source_sale(event, sale_source) is None:
                    continue
                event.update(overlay_sale_event(event, sale_source))
            for key in ('payment_source', 'cash_subtotal', 'invoice_date', 'base_price', 'qty', 'name',
                        'cost', 'source_fee', 'source_fixed_cost', 'source_profit', 'source_row', 'source_sheet'):
                if key not in event and key in original:
                    event[key] = original[key]
    if include_imported:
        transfers = await db.transfer_history.find({}, {'_id': 0}).to_list(None)
        by_transfer = {(e.get('sheet'), e.get('row')): e for e in (source or {}).get('transfers', [])}
        for transfer in transfers:
            original = by_transfer.get((transfer.get('source_sheet') or transfer.get('sheet'),
                                         transfer.get('source_row') or transfer.get('row')))
            if original and all(transfer.get(k) == original.get(k) for k in ('date', 'amount')):
                transfer = {**original, **transfer}
            events.append({**transfer, 'kind': 'transfer', 'source_sheet': transfer.get('source_sheet') or transfer.get('sheet'),
                           'source_row': transfer.get('source_row') or transfer.get('row')})
    transaction_query = {'$or': [
        {'import_source': {'$exists': False}},
        {'import_source': {'$exists': True}, 'return_date': {'$type': 'string'}},
    ]} if include_imported else {'import_source': {'$exists': False}}
    # Baseline reconciliation can retain old invoices without recognizing them
    # again. Unmarked future invoices remain part of the live ledger.
    transaction_query['report_excluded'] = {'$ne': True}
    txs = await db.transactions.find(transaction_query, {'_id': 0}).to_list(None)
    details = await db.transaction_details.find({'transaction_id': {'$in': [t['id'] for t in txs]}}, {'_id': 0}).to_list(None)
    by_tx = {}
    for d in details: by_tx.setdefault(d['transaction_id'], []).append(d)
    for t in txs:
        imported = bool(t.get('import_source'))
        if t.get('import_source') == 'store_current' and sale_source is None:
            sale_source = await asyncio.to_thread(reference_sale_rows)
        for d in by_tx.get(t['id'], []):
            if sale_source is not None:
                d = overlay_sale_detail(t, d, sale_source)
            from lib.excel_rules import line_snapshot_values
            values = line_snapshot_values({**d, **({'import_source': t['import_source']} if imported else {})},
                                          t['payment_method'] == 'credit')
            e = dict(date=t['date_key'], invoice_date=t['date_key'], transaction_id=t['id'], detail_id=d['id'],
                     invoice=t.get('source_invoice') or t['invoice_number'], customer=t.get('customer_name') or '',
                     kind='credit_sale' if t['payment_method'] == 'credit' else 'cash_sale', method=t['payment_method'],
                     amount=d['subtotal'], fee=values['spreadsheet_fee'], profit=values['spreadsheet_profit'],
                     category=values['category'], tax=d.get('tax'), owner=d.get('owner'),
                     qty=d['qty'], name=d['product_name'], product_id=d['product_id'],
                     cost=values['spreadsheet_cost'], price=d['price'], base_price=d.get('base_price') if d.get('base_price') is not None else d['price'],
                     cash_subtotal=values['cash_subtotal'])
            if imported:
                e.update(import_source=t['import_source'], source_sheet=d.get('source_sheet'), source_row=d.get('source_row'))
            else:
                events.append(e)
            if t.get('return_date'):
                events.append({**e, 'date': t['return_date'], 'amount': -e['amount'], 'fee': -e['fee'],
                               'profit': -e['profit'], 'qty': -e['qty'], 'cash_subtotal': -e['cash_subtotal'], 'is_return': True})
        if not imported and t['payment_method'] not in ('cash', 'credit'):
            transfer = dict(date=t['date_key'], kind='transfer', amount=t['total_amount'], method=t['payment_method'],
                            transaction_id=t['id'], origin='transaction')
            events.append(transfer)
            if t.get('return_date'):
                events.append({**transfer, 'date': t['return_date'], 'amount': -transfer['amount'], 'is_return': True})
    tx_lookup = {t['id']: t for t in txs}
    for collection, kind in [(db.accounts_receivable, 'credit_payment'), (db.accounts_payable, 'supplier_payment')]:
        async for debt in collection.find({}, {'_id': 0}):
            transaction = tx_lookup.get(debt.get('transaction_id'), {})
            meta = dict(transaction_id=debt.get('transaction_id'), customer=debt.get('customer_name') or '',
                        invoice_date=transaction.get('date_key') or debt.get('issued_date'),
                        supplier=debt.get('supplier_name') or '', debt_id=debt['id'])
            payments = [p for p in debt.get('payments', []) if p.get('report_excluded') is not True]
            excluded = [p for p in debt.get('payments', []) if p.get('report_excluded') is True]
            refund_amount, refund_ratio = n(debt.get('refund_amount')), n(1)
            if excluded:
                # A return reverses only receipts recognized by this ledger.
                # Bound partial legacy refunds and their noncash transfer share.
                amounts = [n(p.get('amount')) for p in payments + excluded]
                if refund_amount.is_finite() and all(a.is_finite() and a >= 0 for a in amounts):
                    included_amount = sum((n(p.get('amount')) for p in payments), n(0))
                    excluded_amount = sum((n(p.get('amount')) for p in excluded), n(0))
                    refund_amount = min(included_amount, max(n(0), refund_amount - excluded_amount))
                    refund_ratio = refund_amount / included_amount if included_amount else n(0)
                else:
                    refund_amount, refund_ratio = n(0), n(0)
            for p in payments:
                events.append(dict(**meta, date=p['payment_date'], kind=kind, amount=p['amount'],
                                   profit=p.get('profit_amount', 0), method=p.get('method', 'cash'), payment_id=p.get('id'),
                                   profit_allocation=p.get('profit_allocation') or ('invoice' if p.get('is_down_payment') else None)))
                if kind == 'credit_payment' and p.get('method', 'cash') != 'cash':
                    transfer = dict(**meta, date=p['payment_date'], kind='transfer', amount=p['amount'],
                                    method=p['method'], payment_id=p.get('id'), origin='credit_payment')
                    events.append(transfer)
                    if debt.get('return_date') and refund_amount:
                        events.append({**transfer, 'date': debt['return_date'],
                                       'amount': -float(n(p['amount']) * refund_ratio), 'is_return': True})
            if kind == 'credit_payment' and debt.get('return_date') and refund_amount:
                events.append(dict(**meta, date=debt['return_date'], kind=kind, amount=-float(refund_amount),
                                   profit=-sum(p.get('profit_amount', 0) for p in payments), is_return=True,
                                   profit_allocation='invoice' if payments and all(
                                       p.get('profit_allocation') == 'invoice' or p.get('is_down_payment') for p in payments) else None))
    async for e in db.expenses.find({'import_source': {'$exists': False}, 'report_excluded': {'$ne': True}}, {'_id': 0}):
        events.append(dict(date=e['date'], kind='expense', amount=e['amount'], category=e['category'],
                           description=e.get('description', ''), payment_source=e.get('payment_source', 'Cashier')))
    return events


@router.get('/reports')
async def reports(month: str = Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'), origin: str = Query(default='live', pattern='^(live|preview)$')):
    if origin == 'preview':
        store, september = await asyncio.gather(asyncio.to_thread(dataset, 'store_current'), asyncio.to_thread(dataset, 'september'))
        check = next((c for c in store['checks'] if c['month'] == month), None)
        sc = september['checks'][0] if month == '2026-08' else None
        return {'month': month, 'origin': origin, 'store': check['actual'] if check else None,
                'store_check': check, 'september': sc['actual'] if sc else None, 'september_check': sc,
                'inputs': september['inputs'] if sc else None, 'parameters_saved': False,
                'source_filename': store['filename'],
                'notice': 'Acuan Store: ' + store['filename'] + '. Pratinjau memakai baris dan rumus REPORT sumber. Laporan September tambahan memuat Agustus 2026.',
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
        products = await db.products.find({'active': {'$ne': False}}, {'_id': 0}).to_list(None)
        inputs['stok'] = sum(p['stock']*p['cost_price'] for p in products if p['type'] == 'barang')
        for name, collection in [('piutang', db.accounts_receivable), ('hutang', db.accounts_payable)]:
            inputs[name] = sum([hydrate(d)['remaining'] async for d in collection.find({}, {'_id': 0})])
    parameters = await db.excel_parameters.find_one({'month': month}, {'_id': 0})
    if parameters: inputs.update(parameters['values'])
    saved = bool(parameters)
    current_events = [e for e in events if e['date'][:7] == month]
    from lib.reporting import daily_report
    reference = await asyncio.to_thread(dataset, 'store_current')
    defaults = reference.get('daily_inputs') or {}
    overrides = await db.books_daily_parameters.find({'date': {'$regex': '^' + month}}, {'_id': 0}).to_list(None)
    by_date = {o['date']: o for o in overrides}
    dates = {e['date'] for e in current_events} | set(by_date)
    if defaults.get('date', '')[:7] == month:
        dates.add(defaults['date'])
    daily = [daily_report(current_events, day, **{k: by_date.get(day, defaults if defaults.get('date') == day else {}).get(k, 0)
                                               for k in ('modal_bian', 'laba_bian')}) for day in dates]
    cash = {'income': float(sum(n(d['cash_sales']) + n(d['receivable_payments']) for d in daily)),
            'supplier': float(sum(n(e['amount']) for e in current_events if e['kind'] == 'supplier_payment')),
            **{key: float(sum(n(d[field]) for d in daily)) for key, field in {
                'expenses': 'expenses', 'transfers': 'transfer_payments', 'service_fee': 'montir_fee',
                'modal_bian': 'modal_bian', 'laba_bian': 'laba_bian', 'net': 'net_cash', 'final': 'final_cash'}.items()}}
    historical_missing = month != today_iso()[:7] and not snapshot and not all(k in (parameters or {}).get('values', {}) for k in ('stok', 'piutang', 'hutang'))
    return {'month': month, 'origin': origin, 'store': store, 'september': september_report(inputs), 'inputs': inputs,
            'parameters_saved': saved, 'overrides': (parameters or {}).get('values', {}), 'cash': cash, 'asset_snapshot_missing': historical_missing,
            'source_filename': reference['filename'],
            'notice': 'Perhitungan mengikuti ' + reference['filename'] + '. REPORT memakai riwayat sumber dan transaksi kasir. Kas mengikuti DAILY REPORT; pengambilan BIAN disimpan per tanggal. Laporan aset tambahan memakai snapshot dan parameter bulanan.',
            'months': sorted(set([today_iso()[:7], month]+[e['date'][:7] for e in events]), reverse=True)}


class Parameters(BaseModel):
    values: dict[str, float]


@router.get('/stock-snapshot')
async def stock_snapshot(source: str = Query(default='september', pattern='^(september|store)$')):
    """Referensi read-only: snapshot stok dari workbook (September = Laporan Data Barang, 2 Juni 2026). TIDAK mengubah stok produk."""
    data = await asyncio.to_thread(dataset, 'store_current' if source == 'store' else source)
    current = {p['name'].casefold(): p['stock'] async for p in db.products.find({'type': 'barang', 'active': {'$ne': False}}, {'_id': 0, 'name': 1, 'stock': 1})}
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
            'filename': data['filename'],
            'note': ('Snapshot stok bertanggal 2 Juni 2026 dari sheet "Laporan Data Barang". Nilai resmi laporan aset memakai angka workbook (B19).' if source == 'september' else 'Acuan stok DATABASE!Q dari ' + data['filename'] + '.') + ' Hanya referensi untuk perbandingan; stok produk aktif tidak diubah.'}


@router.put('/parameters/{month}')
async def set_parameters(month: str, body: Parameters, user: dict = Depends(require_admin)):
    try: datetime.strptime(month, '%Y-%m')
    except ValueError: raise HTTPException(422, 'Periode tidak valid')
    if any(k not in SEPT_CELLS or not math.isfinite(v) or abs(v) > 1e15 for k, v in body.values.items()):
        raise HTTPException(422, 'Parameter atau nominal tidak valid')
    doc = {'month': month, 'values': body.values, 'recorded_by': user['id'], 'updated_at': datetime.now(timezone.utc).isoformat()}
    await db.excel_parameters.update_one({'month': month}, {'$set': doc}, upsert=True)
    return doc
