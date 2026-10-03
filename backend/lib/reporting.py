"""DAILY REPORT and DASHBOARD formulas from the requested Store workbook.

REPORT, DAILY REPORT, and DASHBOARD have different recognition formulas. Keep
those differences explicit instead of reusing a POS margin for all three.
"""
from decimal import Decimal

from lib.excel_rules import n
from lib.db import db


def daily_report(events, day, modal_bian=0, laba_bian=0):
    todays = [e for e in events if e.get('date') == day]
    amount = lambda kind: sum((n(e.get('amount')) for e in todays if e['kind'] == kind), Decimal(0))
    cash = [e for e in todays if e['kind'] == 'cash_sale']
    credit = [e for e in todays if e['kind'] == 'credit_sale']
    category = lambda e: (e.get('category') or '').upper()
    cash_non_oil = sum((n(e.get('amount')) for e in cash if category(e) != 'OIL'), Decimal(0))
    cash_fee = sum((n(e.get('fee')) for e in cash), Decimal(0))
    credit_fee = sum((n(e.get('fee')) for e in credit), Decimal(0))
    expenses = sum((n(e.get('amount')) for e in todays if e['kind'] == 'expense'
                   and str(e.get('payment_source', 'Cashier')).strip().lower() == 'cashier'), Decimal(0))
    cash_profit = sum((n(e.get('profit')) for e in cash if category(e) not in ('OIL', 'SERVICE')), Decimal(0))
    service_profit = sum((n(e.get('profit')) for e in cash if category(e) == 'SERVICE'), Decimal(0))
    receipt_profit = sum((n(e.get('profit')) for e in todays if e['kind'] == 'credit_payment'), Decimal(0))
    net_cash = cash_non_oil + amount('credit_payment') - amount('transfer') - expenses - cash_fee - credit_fee
    final_cash = net_cash - n(modal_bian) - n(laba_bian)
    profit = cash_profit + receipt_profit - expenses - n(laba_bian) - credit_fee
    spooring = service_profit + credit_fee
    values = dict(
        cash_sales=cash_non_oil,
        non_cash_sales=sum((n(e.get('amount')) for e in cash if e.get('method', 'cash') != 'cash' and category(e) != 'OIL'), Decimal(0)),
        receivable_payments=amount('credit_payment'), transfer_payments=amount('transfer'),
        montir_fee=cash_fee + credit_fee, expenses=expenses, net_cash=net_cash,
        modal_bian=n(modal_bian), laba_bian=n(laba_bian), final_cash=final_cash,
        modal=final_cash - profit - spooring, laba=profit, spooring=spooring,
        oil_revenue=sum((n(e.get('amount')) for e in cash if category(e) == 'OIL'), Decimal(0)),
        oil_benefit=sum((n(e.get('profit')) for e in cash if category(e) == 'OIL'), Decimal(0)),
    )
    return {key: float(value) for key, value in values.items()}


def dashboard_report(events, year):
    """D4/J4/K4/L4 and E4 of DASHBOARD; recognition differs from REPORT."""
    yearly = [e for e in events if e.get('date', '')[:4] == str(year)]
    sales = [e for e in yearly if e['kind'] in ('cash_sale', 'credit_sale')]
    category = lambda e: (e.get('category') or '').upper()
    total = sum((n(e.get('amount')) for e in sales if category(e) != 'OIL'), Decimal(0))
    profit = sum((n(e.get('profit')) for e in yearly
                  if (e['kind'] == 'cash_sale' and category(e) not in ('OIL', 'SERVICE'))
                  or e['kind'] == 'credit_payment'), Decimal(0))
    expenses = sum((n(e.get('amount')) for e in yearly if e['kind'] == 'expense'), Decimal(0))
    return dict(total_revenue=float(total), gross_profit=float(profit), expenses_total=float(expenses),
                net_profit=float(profit - expenses),
                tire_qty_out=float(sum((n(e.get('qty')) for e in sales if category(e) == 'TIRE'), Decimal(0))),
                jasa_amount=float(sum((n(e.get('amount')) for e in sales if category(e) == 'SERVICE'), Decimal(0))),
                service_fee_total=float(sum((n(e.get('fee')) for e in sales), Decimal(0))))


async def live_purchases():
    """PURCHASE uses receipt date C, while Get Data uses invoice date D."""
    rows = await db.purchase_history.find({}, {'_id': 0}).to_list(None)
    stock_ins = await db.stock_in.find({'import_source': {'$exists': False}}, {'_id': 0}).to_list(None)
    product_ids = {item['product_id'] for entry in stock_ins for item in entry.get('items', [])}
    products = {p['id']: p async for p in db.products.find({'id': {'$in': list(product_ids)}}, {'_id': 0})}
    for entry in stock_ins:
        for item in entry.get('items', []):
            product = products.get(item['product_id'], {})
            rows.append(dict(date=entry['date_key'], amount=item.get('subtotal', 0), qty=item.get('qty', 0),
                             category=item.get('category') or product.get('category') or ''))
    return rows
