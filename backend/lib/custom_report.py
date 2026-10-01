"""REPORT/Get Data columns, with separate sales and invoice-dated purchases."""
import asyncio
from decimal import Decimal
from lib.db import db
from lib.sales import month_bounds, sales_report
from lib.workbooks import dataset


async def get_data_report(month, kind='sales', owner=None, category=None, tax='1', origin='live', page=1, page_size=25):
    bounds = month_bounds(month)
    rows = []
    def matches(e):
        return (not owner or (e.get('owner') or 'unassigned') == owner) and (not category or (e.get('category') or 'unassigned') == category) and (tax is None or ('unassigned' if e.get('tax') is None else str(e['tax'])) == tax)
    def row(e):
        return dict(date=e.get('date'), invoice_date=e.get('invoice_date') or e.get('date'),
                    item=e.get('name') or e.get('product_name'), invoice=e.get('source_invoice') or e.get('invoice') or e.get('invoice_number'),
                    amount=e.get('amount', e.get('net', 0)), amount_without_vat=None, vat_amount=None,
                    party='' if (e.get('sheet') or e.get('source_sheet')) == 'SELLING CASH' else e.get('supplier') or e.get('customer') or e.get('customer_name') or '',
                    owner=e.get('owner'), category=e.get('category'), tax=e.get('tax'),
                    source_sheet=e.get('sheet') or e.get('source_sheet') or ('POS' if kind == 'sales' else 'STOK MASUK'),
                    source_row=e.get('row') or e.get('source_row'), kind=e.get('kind', kind))
    if origin == 'preview':
        raw = await asyncio.to_thread(dataset, 'store_current')
        entries = [e for e in raw['events'] if e['kind'] in ('cash_sale', 'credit_sale')] if kind == 'sales' else raw['purchases']
        for e in entries:
            day = e.get('date') if kind == 'sales' else e.get('invoice_date')
            if day and bounds['$gte'] <= day < bounds['$lt'] and matches(e):
                rows.append(row(e))
        filename = raw['filename']
    elif kind == 'sales':
        report = await sales_report(month, owner, category, tax, page_size=None)
        rows = [row(e) for e in report['rows']]
        filename = None
    else:
        async for e in db.purchase_history.find({'invoice_date': bounds}, {'_id': 0}):
            if matches(e):
                rows.append(row(e))
        async for record in db.stock_in.find({'invoice_date': bounds}, {'_id': 0}):
            for item in record['items']:
                e = {**item, 'date': record['date_key'], 'invoice_date': record['invoice_date'], 'invoice': record['invoice_number'],
                     'supplier': record['supplier_name'], 'amount': item['subtotal']}
                if matches(e):
                    rows.append(row(e))
        # Older stock-in records have no invoice date. Never assume the receipt date is the invoice date.
        filename = None
    rows.sort(key=lambda r: (r['invoice_date'] or '', str(r['invoice'] or ''), r['source_row'] or 0))
    total = sum((Decimal(str(r['amount'])) for r in rows), Decimal(0))
    taxable = sum((Decimal(str(r['amount'])) for r in rows if r['tax'] == 1), Decimal(0))
    return dict(month=month, report=kind, origin=origin, filename=filename, total=float(total), tax_base=float(taxable),
                pph_final=round(taxable * Decimal('0.005')) if kind == 'sales' else None,
                count=len(rows), page=page, page_size=page_size,
                rows=rows if page_size is None else rows[(page-1)*page_size:page*page_size],
                notice='Kolom tanpa PPN dan PPN dibiarkan kosong seperti keluaran Apps Script; PPh 0,5% dihitung terpisah, bukan PPN. Pembelian disaring berdasarkan tanggal faktur.')
