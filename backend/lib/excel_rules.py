"""Literal formulas from REPORT and Laporan Laba - Rugi, independent of cached cells."""
from decimal import Decimal, ROUND_CEILING


def n(value):
    return Decimal(str(value)) if isinstance(value, (int, float, Decimal)) else Decimal(0)


def line_values(product, qty, credit=False, discount=0):
    """SELLING CASH I/J/M/N and SELLING CREDIT K/N/O/P/Q.

    ``discount`` is the complete line discount, so callers can also reconstruct
    older saved invoices. The checkout UI supplies Excel's per-unit H value.
    ``base_price`` is the undiscounted cash H price on a credit line.
    """
    category = (product.get('category') or ('SERVICE' if product['type'] == 'jasa' else 'TIRE')).upper()
    quantity = n(qty)
    cost = (n(product.get('cost_price', 0)) / 5000).to_integral_value(rounding=ROUND_CEILING) * 5000
    total = n(product['selling_price']) * quantity - n(discount)
    cash_total = n(product.get('base_price', product['selling_price'])) * quantity if credit else total
    # SERVICE is an item-name check, independent of its category. Credit K
    # uses the CASH total O; a higher tempo price does not increase its fee.
    fee = ((cash_total / 2)
           if str(product.get('name', '')).strip().upper() == 'SERVICE'
           else n(product.get('service_fee', 0)) * quantity)
    cost_total = cost if category == 'SERVICE' else cost * quantity
    if category in ('SERVICE', 'COMPLEMENTARY'):
        profit = total - cost_total - fee
    elif credit and category != 'TIRE':
        profit = Decimal(0)
    else:
        # CASH N and CREDIT Q do not subtract the DATABASE fee for TIRE/OIL.
        profit = total - cost_total
    return dict(category=category, spreadsheet_cost=float(cost),
                spreadsheet_cost_total=float(cost_total), cash_subtotal=float(cash_total),
                spreadsheet_profit=float(profit), spreadsheet_fee=float(fee))


def line_snapshot_values(detail, credit=False):
    """Calculate native invoices from their saved inputs, never today's master.

    Workbook rows keep their cached manual costs, fees and profit overrides.
    """
    if detail.get('import_source') or detail.get('source_sheet') in ('SELLING CASH', 'SELLING CREDIT'):
        cost = detail.get('spreadsheet_cost', detail.get('cost_price', 0))
        category = detail.get('category', 'TIRE').upper()
        quantity = detail.get('qty', 0)
        cash_total = detail.get('cash_subtotal')
        if cash_total is None:
            base_price = detail.get('base_price') if detail.get('base_price') is not None else detail['price']
            cash_total = base_price * quantity if credit else detail['subtotal']
        return dict(category=category, spreadsheet_cost=cost,
                    spreadsheet_cost_total=cost if category == 'SERVICE' else cost * quantity,
                    spreadsheet_fee=detail.get('spreadsheet_fee', detail.get('service_fee', 0) * quantity),
                    spreadsheet_profit=detail.get('spreadsheet_profit', 0),
                    cash_subtotal=cash_total)
    product = dict(name=detail['product_name'], type=detail['product_type'],
                   category=detail.get('category'), selling_price=detail['price'],
                   base_price=detail.get('base_price') if detail.get('base_price') is not None else detail['price'],
                   cost_price=detail.get('source_cost_price') if detail.get('source_cost_price') is not None else detail.get('cost_price', 0),
                   service_fee=detail.get('service_fee', 0))
    return line_values(product, detail['qty'], credit,
                       n(detail['price']) * n(detail['qty']) - n(detail['subtotal']))


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
