"""Literal formulas from REPORT and Laporan Laba - Rugi, independent of cached cells."""
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


def n(value):
    return Decimal(str(value)) if isinstance(value, (int, float, Decimal)) else Decimal(0)


def line_values(product, qty, credit=False, discount=0):
    category = product.get('category') or ('SERVICE' if product['type'] == 'jasa' else 'TIRE')
    cost = (n(product.get('cost_price', 0)) / 5000).to_integral_value(rounding=ROUND_CEILING) * 5000
    total = n(product['selling_price']) * qty - n(discount)
    # Only the item named SERVICE uses 50% of the discounted line total.
    fee = ((total / 2).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
           if str(product.get('name', '')).strip().upper() == 'SERVICE'
           else n(product.get('service_fee', 0)) * qty)
    profit = total - cost * qty - fee
    if category == 'SERVICE':
        profit = total - fee - cost  # Literal Excel uses cost once for SERVICE, not qty*cost.
    elif credit and category not in ('TIRE', 'COMPLEMENTARY'):
        profit = Decimal(0)
    return dict(category=category, spreadsheet_cost=float(cost), spreadsheet_profit=float(profit), spreadsheet_fee=float(fee))


def store_report(events, month):
    values = {k: Decimal(0) for k in ['cash_non_oil', 'cash_fees', 'cash_profit', 'credit_fees', 'receipt_total', 'receipt_profit', 'spooring', 'supplier', 'expenses']}
    for e in events:
        if e['date'][:7] != month:
            continue
        kind, amount, category = e['kind'], n(e.get('amount')), e.get('category', '').upper()
        if kind == 'cash_sale':
            if category != 'OIL': values['cash_non_oil'] += amount
            values['cash_fees'] += n(e.get('fee'))
            if category not in ('OIL', 'SERVICE'): values['cash_profit'] += n(e.get('profit'))
            if category == 'SERVICE': values['spooring'] += n(e.get('profit'))
        elif kind == 'credit_sale': values['credit_fees'] += n(e.get('fee'))
        elif kind == 'credit_payment':
            values['receipt_total'] += amount
            values['receipt_profit'] += n(e.get('profit'))
        elif kind == 'supplier_payment': values['supplier'] += amount
        elif kind == 'expense': values['expenses'] += amount
    v = values
    revenue = v['cash_non_oil'] + v['receipt_total'] - v['cash_fees']
    profit = v['cash_profit'] + v['receipt_profit'] - v['credit_fees']
    capital = revenue - profit - v['spooring']
    return {k: float(a) for k, a in dict(pendapatan=revenue, modal=capital, laba=profit,
        spooring=v['spooring'], supplier=v['supplier'], pengeluaran=v['expenses'],
        total_modal=capital-v['supplier'], nett_laba=profit-v['expenses'],
        nett_spooring=v['spooring']).items()}


def september_report(inputs):
    i = {k: n(v) for k, v in inputs.items()}
    get = lambda k: i.get(k, Decimal(0))
    modal = get('pendapatan_toko')-get('distributor')
    net = get('pendapatan_laba')-get('gaji')-get('pajak')-get('operasional')-get('pengeluaran')
    spooring = get('spooring')-get('cicilan_mesin')
    return {k: float(v) for k, v in dict(total_pendapatan=get('pendapatan_toko')+get('pendapatan_laba')+get('spooring')+get('oli'), modal_bersih=modal,
        laba_kotor=get('pendapatan_laba'), laba_bersih=net, spooring_bersih=spooring,
        jumlah_aset=get('stok')+modal+get('piutang'), sisa_aset=get('stok')+modal+get('piutang')-get('hutang')).items()}
