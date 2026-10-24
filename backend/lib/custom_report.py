"""Literal Code.gs Get Data selection and REPORT!U4 summary range."""
import asyncio
from decimal import Decimal
from lib.db import db
from lib.sales import (GET_DATA_BASIS, GET_DATA_ROW_LIMIT, TAX_RATE,
                       archived_zero_sales, excel_sale_amount, get_data_order, month_bounds, sales_report)
from lib.workbooks import dataset


async def get_data_report(month, kind='sales', owner=None, category=None, tax=None,
                          origin='live', page=1, page_size=25, payment_method=None):
    bounds = month_bounds(month)
    rows = []
    def matches(e):
        return (not owner or (e.get('owner') or 'unassigned') == owner) and (not category or (e.get('category') or 'unassigned') == category) and (tax is None or ('unassigned' if e.get('tax') is None else str(e['tax'])) == tax)
    def append(e):
        if not matches(e):
            return
        if kind == 'sales':
            amount = excel_sale_amount(e)
            if amount is None:
                return
        else:
            if e.get('tax') != 1:  # Code.gs getPurchaseData requires PURCHASE!F == 1.
                return
            amount = Decimal(str(e.get('amount', 0)))
        credit = e.get('payment_method') == 'credit' or e.get('kind') == 'credit_sale'
        party = e.get('supplier') or e.get('customer') or e.get('customer_name') or ''
        if kind == 'sales' and not credit:
            party = ''
        rows.append(dict(date=e.get('date'), invoice_date=e.get('invoice_date') or e.get('date'),
                         item=e.get('name') or e.get('product_name'),
                         invoice=(e['source_invoice'] if e.get('source_invoice') is not None
                                  else e['invoice'] if e.get('invoice') is not None
                                  else e.get('invoice_number')),
                         amount=float(amount), amount_without_vat=None, vat_amount=None, party=party,
                         owner=e.get('owner'), category=e.get('category'), tax=e.get('tax'),
                         source_sheet=e.get('sheet') or e.get('source_sheet') or ('POS' if kind == 'sales' else 'STOK MASUK'),
                         source_row=e.get('row') or e.get('source_row'), kind=e.get('kind', kind),
                         payment_method='credit' if credit else e.get('payment_method', 'cash')))
    if origin == 'preview':
        raw = await asyncio.to_thread(dataset, 'store_current')
        entries = [e for e in raw['events'] if e['kind'] in ('cash_sale', 'credit_sale')] if kind == 'sales' else raw['purchases']
        for e in entries:
            day = e.get('date') if kind == 'sales' else e.get('invoice_date')
            if day and bounds['$gte'] <= day < bounds['$lt']:
                append(e)
        filename = raw['filename']
    elif kind == 'sales':
        report = await sales_report(month, owner, category, tax, payment_method, page_size=None)
        for e in report['rows']:
            append(e)
        for e in await archived_zero_sales(month, owner, category, tax, payment_method):
            append(e)
        filename = None
    else:
        async for e in db.purchase_history.find({'invoice_date': bounds}, {'_id': 0}):
            append(e)
        async for record in db.stock_in.find({'invoice_date': bounds}, {'_id': 0}):
            for item in record['items']:
                e = {**item, 'date': record['date_key'], 'invoice_date': record['invoice_date'], 'invoice': record['invoice_number'],
                     'supplier': record['supplier_name'], 'amount': item['subtotal']}
                append(e)
        # Older stock-in records have no invoice date. Never assume the receipt date is the invoice date.
        filename = None
    rows.sort(key=get_data_order)
    summarized = rows[:GET_DATA_ROW_LIMIT]
    total = sum((Decimal(str(r['amount'])) for r in summarized), Decimal(0))
    full_total = sum((Decimal(str(r['amount'])) for r in rows), Decimal(0))
    return dict(month=month, report=kind, origin=origin, filename=filename, total=float(total),
                full_total=float(full_total), tax_base=float(total),
                pph_final=round(total * Decimal(str(TAX_RATE))) if kind == 'sales' else None,
                count=len(rows), summarized_count=len(summarized), summary_row_limit=GET_DATA_ROW_LIMIT,
                page=page, page_size=page_size,
                rows=rows if page_size is None else rows[(page-1)*page_size:page*page_size],
                basis=GET_DATA_BASIS if kind == 'sales' else 'PURCHASE!F = 1; bulan berdasarkan tanggal faktur D',
                notice='Mengikuti Get Data Apps Script: tunai TAX = 1; tempo hanya Tire pada harga tunai, pembelian TAX = 1 berdasarkan tanggal faktur. Total mengikuti REPORT!U4 (996 baris pertama). Kolom tanpa PPN dan PPN kosong seperti sumber. Estimasi PPh 0,5% ditampilkan terpisah; tarif ini merupakan pengaturan aplikasi.')
