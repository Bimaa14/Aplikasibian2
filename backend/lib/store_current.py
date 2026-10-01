"""Read the supplied Store export without changing stocks or assigning unknown owners."""
from collections import defaultdict
from datetime import datetime, date, time


def enrich_current(w, data):
    from lib.workbooks import num, text, day
    def rows(sheet):
        for i, r in enumerate(w[sheet].iter_rows(min_row=2, values_only=True), 2):
            yield i, list(r) + [None] * 50

    products = []
    master = defaultdict(list)
    for i, r in rows('DATABASE'):
        if not text(r[2]):
            continue
        owner_raw = text(r[9])
        owner = owner_raw.lower() or None
        tax = 1 if text(r[10]) in ('1', '1.0') else 0
        category = text(r[12]).upper() or 'TIRE'
        stock = num(r[16])
        issues = []
        if stock != int(stock):
            issues.append(f'Saldo DATABASE!Q{i} = {stock:g}; menunggu konfirmasi sumber stok')
        if category not in ('TIRE', 'OIL', 'SERVICE', 'COMPLEMENTARY'):
            issues.append('Kategori belum dipetakan')
        if num(r[7]) < 0 or num(r[8]) < 0:
            issues.append('Harga negatif')
        p = dict(row=i, sheet='DATABASE', name=text(r[2]), sku=f'XL-STORE-{i:04d}',
                 size=text(r[3]), brand=text(r[5]), type='jasa' if category in ('SERVICE', 'COMPLEMENTARY') else 'barang',
                 category=category, owner=owner, source_owner=owner_raw, tax=tax, stock=stock,
                 source_stock_opening=num(r[6]), source_stock_final=stock,
                 selling_price=num(r[7]), cost_price=num(r[8]), service_fee=num(r[11]), issue='; '.join(issues))
        products.append(p)
        master[p['name'].casefold()].append(p)
    for p in products:
        if len(master[p['name'].casefold()]) > 1:
            p['note'] = 'Nama sama dipertahankan sebagai produk terpisah sesuai baris sumber; stok tidak dijumlah.'
    data['products'] = products
    data['customers'], data['suppliers'] = [], []
    for i, r in rows('DATABASE'):
        for group, col in [('customers', 21), ('suppliers', 29)]:
            if text(r[col + 1]):
                data[group].append(dict(row=i, sheet='DATABASE', name=text(r[col+1]), code=text(r[col]),
                                        amount=num(r[col+2]), paid_amount=num(r[col+3]), remaining=num(r[col+4]), issue=''))
    source_lines = {}
    for sheet in ('SELLING CASH', 'SELLING CREDIT'):
        source_lines[sheet] = {i: r for i, r in rows(sheet)}
    for e in data['events']:
        if e['kind'] not in ('cash_sale', 'credit_sale'):
            continue
        r = source_lines[e['sheet']][e['row']]
        matches = master.get(e['name'].casefold(), [])
        # A repeated identical tax value is safe to read; conflicting/missing masters stay unknown.
        taxes = {p['tax'] for p in matches}
        e['tax'] = next(iter(taxes)) if len(taxes) == 1 else None
        e['tax_source'] = 'DATABASE.K' if e['tax'] is not None else 'unresolved'
        owner_raw = text(r[14] if e['kind'] == 'cash_sale' else r[19])
        e['owner'] = owner_raw.lower() or None
        e['source_owner'] = owner_raw
        e['base_price'] = e['price'] if e['kind'] == 'cash_sale' else num(r[7])
        e['credit_surcharge'] = e['price'] - e['base_price'] if e['kind'] == 'credit_sale' else 0
        e['discount_amount'] = round(e['price'] * e['qty'] - e['amount'], 2)
        if len(matches) == 1:
            e['product_size'], e['product_brand'] = matches[0]['size'], matches[0]['brand']
        e['source_row'], e['source_sheet'] = e['row'], e['sheet']
    data['purchases'], data['transfers'] = [], []
    for i, r in rows('PURCHASE'):
        if not day(r[2]):
            continue
        owner_raw = text(r[7])
        data['purchases'].append(dict(row=i, sheet='PURCHASE', date=day(r[2]), invoice_date=day(r[3]),
            supplier=text(r[4]), party=text(r[4]), invoice=text(r[6]), name=text(r[8]), qty=num(r[9]),
            price=num(r[11]), amount=num(r[13]), tax=1 if text(r[5]) in ('1','1.0') else 0,
            owner=owner_raw.lower() or None, source_owner=owner_raw,
            payment_method=text(r[12]), due_date=day(r[14]), category=text(r[15]).upper(), brand=text(r[16]),
            issue='' if day(r[3]) and text(r[8]) and num(r[13]) >= 0 else 'Tanggal faktur/nama/nominal perlu diperiksa'))
    for i, r in rows('TRANSFER'):
        if day(r[2]):
            data['transfers'].append(dict(row=i, sheet='TRANSFER', date=day(r[2]), amount=num(r[3]),
                                         name=text(r[4]), method=text(r[4]), issue='' if num(r[3]) >= 0 else 'Nominal negatif'))
    # Preserve all cached source rows, including side tables and unmatched balances, as reference only.
    data['source_rows'] = []
    for sheet in w:
        for i, row in enumerate(sheet.iter_rows(values_only=True), 1):
            cells = {str(j+1): v.isoformat() if isinstance(v, (datetime, date, time)) else v for j, v in enumerate(row) if v is not None}
            if cells:
                data['source_rows'].append(dict(row=i, sheet=sheet.title, cells=cells, issue=''))
    data['warnings'] = [
        'File 29 September: stok dibaca dari DATABASE Q (FINAL), kolom G disimpan sebagai referensi. Saldo negatif dipertahankan; nama ganda tetap terpisah berdasarkan baris sumber.',
        'Label kepemilikan sumber dipertahankan. BIAN/Bian menjadi bian; label NON/POLOSAN/NON VPT/NON VAT tetap dapat ditelusuri.',
        'PPh penjualan hanya TAX = 1 dari DATABASE K. TAX yang tidak dapat dipetakan tidak masuk dasar pajak.',
        'Pembelian/transfer diimpor sebagai riwayat sumber, tanpa menggerakkan stok atau menebak alokasi pembayaran invoice.',
        'Saldo agregat piutang/hutang tetap arsip sampai nomor invoice dan jatuh tempo dapat dipetakan.',
        'Versi sumber Store yang berbeda dari impor sebelumnya ditahan untuk mencegah data ganda. Perlu rencana migrasi data lama.',
    ]
