"""Monthly item ledger from immutable checkout snapshots, including dated returns."""
import re
import asyncio
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from fastapi import HTTPException
from lib.db import db
from lib.source_sales import reference_sale_rows, overlay_sale_detail

OwnerFilter = Literal['bian', 'ibu', 'non', 'polosan', 'non vpt', 'non vat', 'unassigned']
CategoryFilter = Literal['TIRE', 'OIL', 'SERVICE', 'COMPLEMENTARY', 'unassigned']
TaxFilter = Literal['0', '1', 'unassigned']
TAX_RATE = 0.005
GET_DATA_ROW_LIMIT = 996  # REPORT!U4 = SUM(U7:U1002)
GET_DATA_BASIS = 'Tunai TAX = 1; tempo kategori Tire memakai total harga tunai (SELLING CREDIT!O)'


def excel_sale_amount(row):
    """Code.gs getSellingData: cash I with P=1, credit O with S=Tire."""
    credit = row.get('payment_method') == 'credit' or row.get('kind') == 'credit_sale'
    if credit:
        if (row.get('category') or '').upper() != 'TIRE':
            return None
        cash_total = row.get('cash_subtotal')
        if cash_total is None:
            base = row.get('base_price')
            if base is None:
                base = Decimal(str(row.get('price') or 0)) - Decimal(str(row.get('credit_surcharge') or 0))
            cash_total = Decimal(str(base)) * Decimal(str(row.get('qty') or 0))
        return Decimal(str(cash_total))
    if row.get('tax') != 1:
        return None
    return Decimal(str(row.get('net', row.get('amount', 0)) or 0))


def get_data_order(row):
    """Apps Script appends source CASH rows first, then CREDIT rows."""
    credit = row.get('payment_method') == 'credit' or row.get('kind') == 'credit_sale'
    source_row = row.get('source_row', row.get('row'))
    return (int(credit), int(source_row is None), source_row or 0,
            row.get('date') or '', str(row.get('invoice_number', row.get('invoice')) or ''),
            row.get('kind') == 'return')


def excel_sales_summary(rows):
    eligible = [(row, excel_sale_amount(row)) for row in rows]
    eligible = [(row, amount) for row, amount in eligible if amount is not None]
    eligible.sort(key=lambda pair: get_data_order(pair[0]))
    base = sum((amount for _, amount in eligible[:GET_DATA_ROW_LIMIT]), Decimal(0))
    full_base = sum((amount for _, amount in eligible), Decimal(0))
    return base, full_base, len(eligible)


def month_bounds(month):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise HTTPException(422, 'Format bulan harus YYYY-MM')
    try:
        start = date.fromisoformat(month + '-01')
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    except ValueError as exc:
        raise HTTPException(422, 'Bulan tidak valid') from exc
    return {'$gte': start.isoformat(), '$lt': end.isoformat()}


async def archived_zero_sales(month, owner=None, category=None, tax=None, payment_method=None):
    """Source-only zero rows still occupy the Apps Script REPORT summary range.

    Their POS invoices were intentionally omitted during import. Read the source
    archive without manufacturing transactions or adding item-ledger rows.
    """
    query = {'import_source': 'store_current', 'date': month_bounds(month),
             'kind': {'$in': ['cash_sale', 'credit_sale']}, 'qty': 0, 'amount': 0,
             'report_excluded': {'$ne': True}}
    rows = []
    async for event in db.excel_events.find(query, {'_id': 0}):
        method = 'credit' if event['kind'] == 'credit_sale' else 'cash'
        line_owner = event.get('owner') or 'unassigned'
        line_category = event.get('category') or 'unassigned'
        line_tax = str(event['tax']) if event.get('tax') in (0, 1) else 'unassigned'
        if (owner is not None and line_owner != owner
                or category is not None and line_category != category
                or tax is not None and line_tax != tax
                or payment_method is not None and method != payment_method):
            continue
        rows.append({**event, 'payment_method': method})
    return rows


async def sales_report(month, owner=None, category=None, tax=None, payment_method=None, page=1, page_size=25):
    bounds = month_bounds(month)
    query = {'$or': [{'date_key': bounds}, {'return_date': bounds}],
             'status': {'$in': ['completed', 'returned']}, 'report_excluded': {'$ne': True}}
    if payment_method:
        query['payment_method'] = payment_method
    pipeline = [
        {'$match': query},
        {'$lookup': {'from': 'transaction_details', 'localField': 'id', 'foreignField': 'transaction_id', 'as': 'lines'}},
        {'$sort': {'date_key': -1, 'invoice_number': -1}},
    ]
    rows = []
    groups = defaultdict(lambda: {'gross': Decimal(0), 'discount': Decimal(0), 'net': Decimal(0)})
    unknown = Decimal(0)
    transactions = set()
    for_row = lambda value: Decimal(str(value or 0))
    source = None
    async for tx in db.transactions.aggregate(pipeline):
        if tx.get('import_source') == 'store_current' and source is None:
            source = await asyncio.to_thread(reference_sale_rows)
        for d in tx['lines']:
            if source is not None:
                d = overlay_sale_detail(tx, d, source)
            line_owner = d.get('owner') or 'unassigned'
            line_category = d.get('category') or 'unassigned'
            line_tax = str(d['tax']) if d.get('tax') in (0, 1) else 'unassigned'
            if owner is not None and line_owner != owner:
                continue
            if category is not None and line_category != category:
                continue
            if tax is not None and line_tax != tax:
                continue
            net = for_row(d.get('subtotal'))
            gross = for_row(d.get('price')) * d.get('qty', 0)
            discount = gross - net
            cash_total = d.get('cash_subtotal')
            if cash_total is None:
                cash_price = d.get('base_price')
                if cash_price is None:
                    cash_price = for_row(d.get('price')) - for_row(d.get('credit_surcharge'))
                cash_total = for_row(cash_price) * d.get('qty', 0)
            events = []
            if tx.get('date_key', '')[:7] == month:
                # Legacy returns without a return date cannot be placed in a period.
                if tx['status'] != 'returned' or tx.get('return_date'):
                    events.append((tx['date_key'], 'sale', 1))
            if (tx.get('return_date') or '')[:7] == month:
                events.append((tx['return_date'], 'return', -1))
            for day, kind, sign in events:
                row = {
                    'transaction_id': tx['id'], 'invoice_number': tx['invoice_number'], 'source_invoice': tx.get('source_invoice'), 'date': day,
                    'kind': kind, 'customer_name': tx.get('customer_name') or 'Umum',
                    'payment_method': tx['payment_method'], 'product_name': d['product_name'],
                    'product_sku': d.get('product_sku'), 'source_sheet': d.get('source_sheet'), 'source_row': d.get('source_row'), 'owner': line_owner, 'category': line_category,
                    'tax': None if line_tax == 'unassigned' else int(line_tax), 'qty': d['qty'] * sign,
                    'gross': float(gross * sign), 'discount': float(discount * sign), 'net': float(net * sign),
                    'cash_subtotal': float(for_row(cash_total) * sign),
                }
                rows.append(row)
                transactions.add(tx['id'])
                bucket = groups[(line_owner, line_category, line_tax)]
                for key, amount in [('gross', gross), ('discount', discount), ('net', net)]:
                    bucket[key] += amount * sign
                if line_tax == 'unassigned' and tx['payment_method'] != 'credit':
                    unknown += net * sign
    rows.sort(key=lambda row: (row['date'], row['invoice_number'], row['kind']), reverse=True)
    totals = {key: float(sum((g[key] for g in groups.values()), Decimal(0))) for key in ('gross', 'discount', 'net')}
    archive_rows = await archived_zero_sales(month, owner, category, tax, payment_method)
    taxable, full_taxable, eligible_count = excel_sales_summary(rows + archive_rows)
    summary = [{
        'owner': key[0], 'category': key[1], 'tax': None if key[2] == 'unassigned' else int(key[2]),
        **{field: float(amount) for field, amount in values.items()},
    } for key, values in sorted(groups.items())]
    return {
        'month': month, 'filters': {'owner': owner, 'category': category, 'tax': tax, 'payment_method': payment_method},
        **totals, 'tax_base': float(taxable), 'tax_amount': round(taxable * Decimal(str(TAX_RATE))),
        'tax_basis': GET_DATA_BASIS, 'full_tax_base': float(full_taxable),
        'tax_summary_row_limit': GET_DATA_ROW_LIMIT, 'tax_eligible_line_count': eligible_count,
        'tax_rate': TAX_RATE, 'unassigned_tax_net': float(unknown),
        'transaction_count': len(transactions), 'line_count': len(rows), 'groups': summary,
        'page': page, 'page_size': page_size,
        'rows': rows if page_size is None else rows[(page - 1) * page_size:page * page_size],
    }
