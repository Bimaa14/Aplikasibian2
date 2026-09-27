"""Read user-supplied workbooks, never run macros or trust descriptive AI summaries."""
import hashlib
import os
from functools import lru_cache
from datetime import datetime, date
from pathlib import Path
import openpyxl
from lib.excel_rules import store_report, september_report

FILES = {'store': 'store-1.xlsx', 'september': 'september-1.xlsx'}
STORE_KEYS = ['pendapatan', 'modal', 'laba', 'spooring', 'supplier', 'pengeluaran', 'total_modal', 'nett_laba', 'nett_spooring']
SEPT_CELLS = {'pendapatan_toko': 'B4', 'pendapatan_laba': 'B5', 'spooring': 'B6', 'oli': 'B7', 'distributor': 'B11', 'gaji': 'E11', 'pajak': 'E12', 'operasional': 'E13', 'pengeluaran': 'E14', 'cicilan_mesin': 'H11', 'stok': 'B19', 'piutang': 'B21', 'hutang': 'B23'}
SEPT_OUTPUTS = {'total_pendapatan': 'B8', 'modal_bersih': 'B12', 'laba_kotor': 'E10', 'laba_bersih': 'E15', 'spooring_bersih': 'H12', 'jumlah_aset': 'B22', 'sisa_aset': 'B24'}


def num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0


def day(x):
    return x.date().isoformat() if isinstance(x, datetime) else x.isoformat() if isinstance(x, date) else None


def text(x):
    return str(x).strip() if x is not None else ''


@lru_cache(maxsize=2)
def dataset(source):
    path = Path(os.environ['WORKBOOK_DIR']) / FILES[source]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    w = openpyxl.load_workbook(path, read_only=True, data_only=True)
    data = {'source': source, 'digest': digest, 'filename': path.name, 'events': [], 'products': [], 'receivables': [], 'payables': [], 'checks': [], 'warnings': []}
    def rows(sn, start=2):
        for i, values in enumerate(w[sn].iter_rows(min_row=start, max_col=50, values_only=True), start):
            yield i, list(values) + [None] * 50
    if source == 'store':
        for i, r in rows('DATABASE'):
            if not text(r[2]): continue
            raw_cat = text(r[12]).upper()
            category = raw_cat or 'TIRE'  # sel kategori kosong default ke TIRE (barang), bisa diedit setelah impor
            raw_stock = num(r[16]); stock = max(0, int(round(raw_stock)))  # stok akhir Q: clamp negatif/pecahan ke >=0
            sell = num(r[7]); cost = num(r[8])
            issue = ''; note = ''
            if raw_cat and raw_cat not in ('TIRE', 'OIL', 'SERVICE', 'COMPLEMENTARY'): issue = 'Kategori tidak dikenal; petakan dulu'
            elif not raw_cat: note = 'Kategori kosong di sheet; diset TIRE (bisa diedit)'
            if sell < 0 or cost < 0: issue = 'Harga negatif'
            if raw_stock < 0 or raw_stock != int(raw_stock): note = (note + ' · ' if note else '') + f'Stok sheet {raw_stock:g} diset {stock} (cek fisik)'
            data['products'].append({'row': i, 'sheet': 'DATABASE', 'name': text(r[2]), 'sku': f'XL-STORE-{i:04d}', 'type': 'jasa' if category in ('SERVICE', 'COMPLEMENTARY') else 'barang', 'category': category, 'brand': text(r[5]), 'size': text(r[3]), 'stock': stock, 'selling_price': sell, 'cost_price': cost, 'service_fee': num(r[11]), 'issue': issue, 'note': note})
            for key, idx in [('receivables', 21), ('payables', 29)]:
                # DATABASE customer/supplier balances are not invoice-linked. Never invent payment dates.
                name = text(r[idx + 1]); total = num(r[idx + 2]); paid = num(r[idx + 3]); remaining = num(r[idx + 4])
                if name and (total or paid or remaining): data[key].append({'row': i, 'sheet': 'DATABASE', 'party': name, 'amount': total, 'paid_amount': paid, 'remaining': remaining, 'issue': 'Saldo agregat tanpa invoice/jatuh tempo. Perlu pemetaan; tidak diimpor sebagai tagihan.'})
        # Gabungkan produk bernama sama (duplikat di sheet) jadi satu baris: stok dijumlah, harga pakai baris harga jual tertinggi.
        by_name, order = {}, []
        for p in data['products']:
            key = p['name'].casefold()
            if key not in by_name:
                by_name[key] = p; order.append(key)
            else:
                m = by_name[key]; m['stock'] += p['stock']
                if p['selling_price'] > m['selling_price']:
                    m['selling_price'], m['cost_price'], m['service_fee'] = p['selling_price'], p['cost_price'], p['service_fee']
                base = (m.get('note') or '').split(' · Nama ganda')[0]
                m['note'] = (base + ' · ' if base else '') + 'Nama ganda digabung jadi 1 (cek harga/stok)'
        data['products'] = [by_name[k] for k in order]
        for sn, kind in [('SELLING CASH', 'cash_sale'), ('SELLING CREDIT', 'credit_sale'), ('PAYMENT CREDIT', 'credit_payment'), ('PAYMENT SUPPLIER', 'supplier_payment'), ('EXPENSES', 'expense')]:
            for i, r in rows(sn):
                date_key = day(r[2])
                if not date_key: continue
                e = dict(row=i, sheet=sn, date=date_key, kind=kind)
                if kind == 'cash_sale':
                    e.update(invoice=text(r[3]), name=text(r[4]), qty=num(r[5]), price=num(r[6]), amount=num(r[8]), fee=num(r[9]), cost=num(r[12]), profit=num(r[13]), category=text(r[17]).upper(), customer='')
                elif kind == 'credit_sale':
                    e.update(invoice=text(r[3]), customer=text(r[4]), name=text(r[5]), qty=num(r[6]), price=num(r[8]), due_date=day(r[9]), fee=num(r[10]), cost=num(r[13]), amount=num(r[15]), profit=num(r[16]), category=text(r[18]).upper())
                elif kind == 'credit_payment': e.update(customer=text(r[4]), amount=num(r[5]), profit=num(r[6]), invoice_date=day(r[3]))
                elif kind == 'supplier_payment': e.update(supplier=text(r[3]), amount=num(r[4]))
                else: e.update(amount=num(r[3]), description=text(r[4]), category=text(r[5]))
                data['events'].append(e)
        for row, r in rows('REPORT'):
            try: month = datetime.strptime(text(r[3]), '%B %Y').strftime('%Y-%m')
            except ValueError: continue
            actual = store_report(data['events'], month)
            expected = {key: num(r[4 + i]) for i, key in enumerate(STORE_KEYS)}
            data['checks'].append({'month': month, 'sheet': 'REPORT', 'row': row, 'actual': actual, 'expected': expected, 'differences': {k: round(actual[k]-v, 2) for k, v in expected.items()}})
        data['warnings'] = ['Stok menggunakan DATABASE!Q (saldo akhir); nilai negatif/pecahan di-clamp ke 0 dan diberi catatan, bukan menambah ulang pembelian historis. Cek stok fisik lalu edit bila perlu.', 'Pembayaran pelanggan/supplier tidak berisi nomor invoice yang andal. Saldo tagihan agregat ditahan; alokasi cicilan tidak ditebak.', 'Riwayat transaksi diimpor tanpa mengubah stok dan tanpa membuat piutang kedua. Saldo awal tagihan perlu diselesaikan terpisah.']
    else:
        s = w['Laporan Laba - Rugi']; vals = {c.coordinate: c.value for row in s.iter_rows() for c in row if c.value is not None}
        inputs = {key: num(vals.get(cell)) for key, cell in SEPT_CELLS.items()}
        actual = september_report(inputs); expected = {key: num(vals.get(cell)) for key, cell in SEPT_OUTPUTS.items()}
        data['inputs'] = inputs
        data['checks'] = [{'month': '2026-08', 'sheet': 'Laporan Laba - Rugi', 'actual': actual, 'expected': expected, 'differences': {k: round(actual[k]-v, 2) for k, v in expected.items()}}]
        for i, r in rows('Laporan Data Barang', 3):
            if not text(r[1]) or not text(r[2]): continue
            data['products'].append({'row': i, 'sheet': 'Laporan Data Barang', 'name': text(r[1]), 'sku': text(r[2]), 'type': 'barang', 'category': 'TIRE', 'stock': int(num(r[3])), 'selling_price': num(r[4]), 'cost_price': num(r[5]), 'issue': 'Snapshot stok bertanggal 2 Juni 2026; kategori belum dipetakan. Gunakan master Store atau rekonsiliasi dulu.'})
        for sn, key in [('Piutang', 'receivables'), ('Hutang', 'payables')]:
            for i, r in rows(sn, 5):
                name = text(r[2]); amount = num(r[3] if key == 'receivables' else r[4])
                if not name or amount <= 0: continue  # lewati baris kosong/header/total, bukan tagihan
                remaining_cell = r[5]
                if isinstance(remaining_cell, (int, float)) and not isinstance(remaining_cell, bool): remaining = num(remaining_cell)
                elif text(remaining_cell).upper() == 'LUNAS': remaining = 0.0
                else: remaining = amount  # SISA kosong / catatan (mis. 'Tunggakan') = belum dibayar, sisa = total
                remaining = min(max(remaining, 0.0), amount); paid = round(amount - remaining, 2)
                issued = day(r[0]); due = day(r[1]); issue = ''
                if not due: issue = 'Tanggal jatuh tempo kosong; isi dulu agar aging bisa dihitung (bisa diedit setelah impor).'
                elif key == 'receivables' and isinstance(r[4], (int, float)) and not isinstance(r[4], bool) and abs(num(r[4]) - paid) > 0.01: issue = 'BAYAR + SISA tidak sama dengan TOTAL'
                data[key].append({'row': i, 'sheet': sn, 'party': name, 'invoice': text(r[3]) if key == 'payables' else '', 'issued_date': issued or due, 'due_date': due, 'amount': amount, 'paid_amount': paid, 'remaining': remaining, 'issue': issue})
        data['warnings'] = ['Nama file September, tetapi data laporan utama adalah Agustus 2026. Periode tidak diganti berdasarkan nama file.', 'Tabel kedua/ketiga Piutang dan Hutang adalah catatan samping/rekonsiliasi, bukan invoice baru; tidak digandakan.', 'Pembayaran saldo awal tidak mempunyai tanggal cicilan. Nilai terbayar dipertahankan tanpa menciptakan riwayat pembayaran palsu.', 'Laporan Data Barang adalah snapshot 2 Juni 2026, berbeda dari stok akhir Store. Impor stok file ini ditahan.']
    w.close()
    return data