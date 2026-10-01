"""Monthly item ledger from immutable checkout snapshots, including dated returns."""
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from fastapi import HTTPException
from lib.db import db

OwnerFilter = Literal['bian', 'ibu', 'non', 'polosan', 'non vpt', 'non vat', 'unassigned']
CategoryFilter = Literal['TIRE', 'OIL', 'SERVICE', 'COMPLEMENTARY', 'unassigned']
TaxFilter = Literal['0', '1', 'unassigned']
TAX_RATE = 0.005


def month_bounds(month):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise HTTPException(422, 'Format bulan harus YYYY-MM')
    try:
        start = date.fromisoformat(month + '-01')
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    except ValueError as exc:
        raise HTTPException(422, 'Bulan tidak valid') from exc
    return {'$gte': start.isoformat(), '$lt': end.isoformat()}


async def sales_report(month, owner=None, category=None, tax=None, payment_method=None, page=1, page_size=25):
    bounds = month_bounds(month)
    query = {'$or': [{'date_key': bounds}, {'return_date': bounds}], 'status': {'$in': ['completed', 'returned']}}
    if payment_method:
        query['payment_method'] = payment_method
    pipeline = [
        {'$match': query},
        {'$lookup': {'from': 'transaction_details', 'localField': 'id', 'foreignField': 'transaction_id', 'as': 'lines'}},
        {'$sort': {'date_key': -1, 'invoice_number': -1}},
    ]
    rows = []
    groups = defaultdict(lambda: {'gross': Decimal(0), 'discount': Decimal(0), 'net': Decimal(0)})
    taxable = Decimal(0)
    unknown = Decimal(0)
    transactions = set()
    for_row = lambda value: Decimal(str(value or 0))
    async for tx in db.transactions.aggregate(pipeline):
        for d in tx['lines']:
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
                }
                rows.append(row)
                transactions.add(tx['id'])
                bucket = groups[(line_owner, line_category, line_tax)]
                for key, amount in [('gross', gross), ('discount', discount), ('net', net)]:
                    bucket[key] += amount * sign
                if line_tax == '1':
                    taxable += net * sign
                elif line_tax == 'unassigned':
                    unknown += net * sign
    rows.sort(key=lambda row: (row['date'], row['invoice_number'], row['kind']), reverse=True)
    totals = {key: float(sum((g[key] for g in groups.values()), Decimal(0))) for key in ('gross', 'discount', 'net')}
    summary = [{
        'owner': key[0], 'category': key[1], 'tax': None if key[2] == 'unassigned' else int(key[2]),
        **{field: float(amount) for field, amount in values.items()},
    } for key, values in sorted(groups.items())]
    return {
        'month': month, 'filters': {'owner': owner, 'category': category, 'tax': tax, 'payment_method': payment_method},
        **totals, 'tax_base': float(taxable), 'tax_amount': round(taxable * Decimal(str(TAX_RATE))),
        'tax_rate': TAX_RATE, 'unassigned_tax_net': float(unknown),
        'transaction_count': len(transactions), 'line_count': len(rows), 'groups': summary,
        'page': page, 'page_size': page_size,
        'rows': rows if page_size is None else rows[(page - 1) * page_size:page * page_size],
    }
