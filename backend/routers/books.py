"""Laporan kas harian, ringkasan bulanan (+ per pemilik), PPh final 0,5%, dan ekspor CSV.

Sumber data = `live_events()`. DAILY REPORT dan REPORT memakai rumus masing-masing.
Ringkasan per pemilik memisahkan nilai REPORT yang sudah diakui. Pajak estimasi
ditampilkan terpisah; hanya pengeluaran pajak tercatat yang mengurangi laba.
"""
import csv
import io
import asyncio
from datetime import date as iso_date, datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lib.auth import require_admin
from lib.db import db
from lib.dates import today_iso
from lib.debts import hydrate
from routers.excel_reports import live_events
from lib.sales import sales_report, OwnerFilter, CategoryFilter, TaxFilter
from models.transaction import PaymentMethod
from lib.custom_report import get_data_report
from lib.excel_rules import n, store_report
from lib.reporting import daily_report
from lib.workbooks import dataset

router = APIRouter(prefix="/books", tags=["books"], dependencies=[Depends(require_admin)])

PPH_RATE = 0.005  # PPh Final UMKM 0,5% dari omzet
BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
OWNER_LABEL = {"bian": "Barang Bian", "ibu": "Barang Ibu (Mamah Bian)", "unassigned": "Belum ditandai (data lama)", "non": "NON", "polosan": "POLOSAN", "non vpt": "NON VPT", "non vat": "NON VAT"}


def _month_label(month: str) -> str:
    try:
        y, m = month.split("-")
        return f"{BULAN_ID[int(m) - 1]} {y}"
    except (ValueError, IndexError):
        return month


def _is_sale(e: dict) -> bool:
    return e.get("kind") in ("cash_sale", "credit_sale")


def _months_from(events) -> list:
    months = {e["date"][:7] for e in events if e.get("date")}
    months.add(today_iso()[:7])
    return sorted(months, reverse=True)


def _valid_date(d: str) -> bool:
    try:
        return len(d) == 10 and iso_date.fromisoformat(d).isoformat() == d
    except ValueError:
        return False


def _valid_month(m: str) -> bool:
    return len(m) == 7 and _valid_date(m + '-01')


async def _daily_inputs(day: str, has_imported: bool = True) -> dict:
    saved = await db.books_daily_parameters.find_one({'_id': day}, {'_id': 0})
    if saved:
        return {**saved, 'parameters_saved': True}
    source = ((await asyncio.to_thread(dataset, 'store_current')).get('daily_inputs') or {}) if has_imported else {}
    defaults = source if source.get('date') == day else {}
    return dict(date=day, modal_bian=defaults.get('modal_bian', 0),
                laba_bian=defaults.get('laba_bian', 0), parameters_saved=False)


async def _daily_data(day: str) -> dict:
    events = await live_events()
    has_imported = any(e.get('import_source') == 'store_current' for e in events)
    inputs = await _daily_inputs(day, has_imported=has_imported)
    transfers = {}
    for event in events:
        if event.get('date') != day or event.get('kind') != 'transfer':
            continue
        method = str(event.get('method') or event.get('bank') or 'other').strip().lower()
        aliases = {'bca': 'transfer_bca', 'bri': 'transfer_bri', 'bni': 'transfer_bni',
                   'danamon': 'transfer_danamon'}
        method = aliases.get(method, method)
        transfers[method] = transfers.get(method, n(0)) + n(event.get('amount'))
    return {
        "date": day,
        **daily_report(events, day, inputs['modal_bian'], inputs['laba_bian']),
        "receivable_profit": float(sum((n(e.get('profit')) for e in events
                                        if e.get('date') == day and e.get('kind') == 'credit_payment'), n(0))),
        "transfer_breakdown": {method: float(value) for method, value in transfers.items()},
        "parameters_saved": inputs['parameters_saved'],
        "months_available": _months_from(events),
    }


async def _asset_snapshot():
    """Nilai stok master aktif + piutang - hutang, tanpa snapshot workbook lain."""
    piutang = sum([hydrate(d)["remaining"] async for d in db.accounts_receivable.find({}, {"_id": 0})])
    hutang = sum([hydrate(d)["remaining"] async for d in db.accounts_payable.find({}, {"_id": 0})])
    products = await db.products.find({"type": "barang", "active": {"$ne": False}}, {"_id": 0, "stock": 1, "cost_price": 1}).to_list(None)
    stok_value = sum((p.get("stock", 0) or 0) * (p.get("cost_price", 0) or 0) for p in products)
    stok_basis = "stok master aktif × harga modal"
    return stok_value, piutang, hutang, stok_basis


async def _owner_summary(month: str, events=None) -> list:
    """Split the same recognized REPORT amounts by known owners.

    A receipt with no reliable owner remains unassigned, as its source has no
    owner column. Do not recognize unpaid credit profit in an owner total.
    """
    events = await live_events() if events is None else events
    def invoice_key(event):
        customer = event.get('customer')
        issued = event.get('invoice_date') or event.get('date')
        return (str(customer).casefold(), issued) if customer and issued else None

    owner_by_tx, owner_by_invoice = {}, {}
    for event in events:
        if event['kind'] != 'credit_sale' or event.get('is_return'):
            continue
        owner = event.get('owner') or 'unassigned'
        if event.get('transaction_id'):
            owner_by_tx.setdefault(event['transaction_id'], set()).add(owner)
        group_key = invoice_key(event)
        if group_key:
            owner_by_invoice.setdefault(group_key, set()).add(owner)
    buckets = {key: [] for key in OWNER_LABEL}
    for event in events:
        event_owner = event.get('owner')
        if event['kind'] == 'credit_payment' and not event_owner:
            group_key = invoice_key(event)
            transaction_id = event.get('transaction_id')
            # New receipts use invoice allocation; old W14 receipts retain their group.
            if event.get('profit_allocation') == 'invoice':
                matches = owner_by_tx.get(transaction_id, owner_by_invoice.get(group_key, set()))
            else:
                matches = owner_by_invoice.get(group_key, owner_by_tx.get(transaction_id, set()))
            if len(matches) == 1:
                event_owner = next(iter(matches))
        key = event_owner if event_owner in OWNER_LABEL else 'unassigned'
        buckets[key].append(event)
    summaries = {key: store_report(rows, month) for key, rows in buckets.items()}
    return [{"owner": key, "label": OWNER_LABEL[key], "omzet": summaries[key]['pendapatan'],
             "laba": summaries[key]['laba'], "modal": summaries[key]['modal'],
             "spooring": summaries[key]['spooring']} for key in OWNER_LABEL]


async def _monthly_data(m: str) -> dict:
    events = await live_events()
    me = [e for e in events if e.get("date", "")[:7] == m]
    breakdown = store_report(events, m)
    omzet = breakdown['pendapatan']
    oli = sum(e['amount'] for e in me if e['kind'] == 'cash_sale' and (e.get('category') or '').upper() == 'OIL')
    omzet_bruto = omzet + oli
    distributor = sum(e["amount"] for e in me if e["kind"] == "supplier_payment")
    expenses_total = sum(e["amount"] for e in me if e["kind"] == "expense")
    gaji = sum(e["amount"] for e in me if e["kind"] == "expense" and "gaji" in e.get("category", "").lower())
    pajak_recorded = sum(e['amount'] for e in me if e['kind'] == 'expense' and 'pajak' in e.get('category', '').lower())
    pengeluaran = expenses_total - gaji - pajak_recorded
    tax_data = await sales_report(m)
    pph = tax_data['tax_amount']
    stok_value, piutang, hutang, stok_basis = await _asset_snapshot()
    sisa_aset = stok_value + piutang - hutang
    owner_summary = await _owner_summary(m, events)
    return {
        "month": m,
        "month_label": _month_label(m),
        "omzet": omzet,
        "omzet_bruto": omzet_bruto,
        "oli": oli,
        "store": breakdown,
        "distributor_payment": distributor,
        "expenses": pengeluaran,
        "expenses_total": expenses_total,
        "gaji": gaji,
        "pajak_recorded": pajak_recorded,
        "pph_final": pph,
        "pph_rate": PPH_RATE,
        "tax_base": tax_data['tax_base'],
        "full_tax_base": tax_data['full_tax_base'],
        "tax_summary_row_limit": tax_data['tax_summary_row_limit'],
        "tax_eligible_line_count": tax_data['tax_eligible_line_count'],
        "unassigned_tax_net": tax_data['unassigned_tax_net'],
        "sisa_aset": sisa_aset,
        "stok_value": stok_value,
        "stok_basis": stok_basis,
        "piutang_outstanding": piutang,
        "hutang_outstanding": hutang,
        "funding": {
            "modal": {"label": "Uang Modal", "total": distributor,
                      "items": [{"name": "Pembayaran distributor", "amount": distributor}]},
            "laba": {"label": "Uang Laba", "total": expenses_total,
                     "items": [{"name": "Pengeluaran", "amount": pengeluaran},
                               {"name": "Pajak yang sudah dicatat", "amount": pajak_recorded},
                               {"name": "Gaji karyawan", "amount": gaji}]},
        },
        "owner_summary": owner_summary,
        "months_available": _months_from(events),
    }


def _csv_response(rows, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _rp(v) -> int:
    return int(round(v))


@router.get("/daily")
async def daily(date: Optional[str] = Query(default=None)):
    day = date or today_iso()
    if not _valid_date(day):
        raise HTTPException(422, "Format tanggal harus YYYY-MM-DD")
    return await _daily_data(day)


@router.get("/daily/csv")
async def daily_csv(date: Optional[str] = Query(default=None)):
    day = date or today_iso()
    if not _valid_date(day):
        raise HTTPException(422, "Format tanggal harus YYYY-MM-DD")
    d = await _daily_data(day)
    rows = [
        ["Laporan Kas Harian", day],
        [],
        ["Keterangan", "Jumlah (Rp)"],
        ["Total pendapatan tunai", _rp(d["cash_sales"])],
        ["Pembayaran piutang masuk", _rp(d["receivable_payments"])],
        ["Dikurangi: transfer (TRANSFER)", -_rp(d["transfer_payments"])],
        ["Dikurangi: komisi montir", -_rp(d["montir_fee"])],
        ["Dikurangi: pengeluaran Cashier", -_rp(d["expenses"])],
        ["KAS BERSIH SEBELUM BIAN (E12)", _rp(d["net_cash"])],
        ["Dikurangi: modal Bian", -_rp(d["modal_bian"])],
        ["Dikurangi: laba Bian", -_rp(d["laba_bian"])],
        ["KAS BERSIH AKHIR (E15)", _rp(d["final_cash"])],
        [],
        ["Ringkasan Modal dan Laba (definisi spreadsheet)", "Jumlah (Rp)"],
        ["Modal", _rp(d["modal"])],
        ["Laba setelah pengeluaran Cashier dan laba Bian (H7)", _rp(d["laba"])],
        ["Spooring / Service", _rp(d["spooring"])],
        [],
        ["Laporan Oli", "Jumlah (Rp)"],
        ["Pendapatan oli", _rp(d["oil_revenue"])],
        ["Benefit oli", _rp(d["oil_benefit"])],
    ]
    return _csv_response(rows, f"laporan-harian-{day}.csv")


class DailyInputs(BaseModel):
    modal_bian: float = Field(default=0, ge=0, le=1e15, allow_inf_nan=False)
    laba_bian: float = Field(default=0, ge=0, le=1e15, allow_inf_nan=False)


@router.put('/daily/parameters/{day}')
async def save_daily_inputs(day: str, body: DailyInputs, user: dict = Depends(require_admin)):
    if not _valid_date(day):
        raise HTTPException(422, 'Format tanggal harus YYYY-MM-DD')
    values = dict(date=day, **body.model_dump(), recorded_by=user['id'],
                  updated_at=datetime.now(timezone.utc).isoformat())
    await db.books_daily_parameters.update_one({'_id': day}, {'$set': values}, upsert=True)
    return {**values, 'parameters_saved': True}


@router.get("/monthly")
async def monthly(month: Optional[str] = Query(default=None)):
    m = month or today_iso()[:7]
    if not _valid_month(m):
        raise HTTPException(422, "Format bulan harus YYYY-MM")
    return await _monthly_data(m)


@router.get("/monthly/csv")
async def monthly_csv(month: Optional[str] = Query(default=None)):
    m = month or today_iso()[:7]
    if not _valid_month(m):
        raise HTTPException(422, "Format bulan harus YYYY-MM")
    r = await _monthly_data(m)
    rows = [
        ["Laporan Bulanan", r["month_label"]],
        [],
        ["Ringkasan", "Jumlah (Rp)"],
        ["1. Pendapatan REPORT (tanpa oli, setelah komisi tunai)", _rp(r["omzet"])],
        ["Modal REPORT", _rp(r['store']['modal'])],
        ["Laba REPORT", _rp(r['store']['laba'])],
        ["Spooring REPORT", _rp(r['store']['spooring'])],
        ["Saldo modal setelah distributor", _rp(r['store']['total_modal'])],
        ["Laba bersih REPORT", _rp(r['store']['nett_laba'])],
        ["   Omzet termasuk oli", _rp(r["omzet_bruto"])],
        ["2. Pembayaran ke distributor", _rp(r["distributor_payment"])],
        ["3. Semua pengeluaran tercatat", _rp(r["expenses_total"])],
        ["   Gaji karyawan", _rp(r["gaji"])],
        ["   Pajak yang sudah dicatat", _rp(r['pajak_recorded'])],
        ["Estimasi PPh final 0,5% (informasi, tidak dipotong ulang)", _rp(r["pph_final"])],
        ["4. Sisa aset", _rp(r["sisa_aset"])],
        [],
        ["Sumber Uang", "Jumlah (Rp)"],
        ["Uang Modal — Pembayaran distributor", _rp(r["distributor_payment"])],
        ["Uang Laba — Pengeluaran", _rp(r["expenses"])],
        ["Uang Laba — Pajak yang sudah dicatat", _rp(r['pajak_recorded'])],
        ["Uang Laba — Gaji karyawan", _rp(r["gaji"])],
        [],
        ["Ringkasan Per Pemilik (bagi hasil)", "Pendapatan REPORT", "Laba REPORT"],
    ]
    for o in r["owner_summary"]:
        rows.append([o["label"], _rp(o["omzet"]), _rp(o["laba"])])
    return _csv_response(rows, f"laporan-bulanan-{m}.csv")


@router.get("/tax")
async def tax(month: Optional[str] = Query(default=None), owner: Optional[OwnerFilter] = None,
              category: Optional[CategoryFilter] = None, payment_method: Optional[PaymentMethod] = None):
    m = month or today_iso()[:7]
    if not _valid_month(m):
        raise HTTPException(422, "Format bulan harus YYYY-MM")
    report = await sales_report(m, owner=owner, category=category, payment_method=payment_method)
    return {
        "month": m,
        "month_label": _month_label(m),
        "basis": "Get Data spreadsheet: tunai TAX = 1 + tempo TIRE berdasarkan total harga tunai",
        "omzet_base": report['tax_base'],
        "full_tax_base": report['full_tax_base'],
        "tax_summary_row_limit": report['tax_summary_row_limit'],
        "tax_eligible_line_count": report['tax_eligible_line_count'],
        "omzet_bruto": report['net'],
        "rate": PPH_RATE,
        "pph_final": report['tax_amount'],
        "unassigned_tax_net": report['unassigned_tax_net'],
        "months_available": [m],
    }


@router.get('/sales')
async def monthly_sales(month: str, owner: Optional[OwnerFilter] = None,
                        category: Optional[CategoryFilter] = None, tax: Optional[TaxFilter] = None,
                        payment_method: Optional[PaymentMethod] = None,
                        page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100)):
    return await sales_report(month, owner, category, tax, payment_method, page, page_size)


@router.get('/sales/csv')
async def monthly_sales_csv(month: str, owner: Optional[OwnerFilter] = None,
                            category: Optional[CategoryFilter] = None, tax: Optional[TaxFilter] = None,
                            payment_method: Optional[PaymentMethod] = None):
    report = await sales_report(month, owner, category, tax, payment_method, page_size=None)
    rows = [['Tanggal', 'Nota', 'Jenis', 'Pembayaran', 'Pemilik', 'Kategori', 'TAX', 'Kode', 'Barang', 'Qty', 'Sebelum potongan', 'Potongan', 'Bersih']]
    for row in report['rows']:
        values = [row[k] for k in ('date', 'invoice_number', 'kind', 'payment_method', 'owner', 'category', 'tax', 'product_sku', 'product_name', 'qty', 'gross', 'discount', 'net')]
        rows.append([("'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v) for v in values])
    rows.extend([[], ['Total bersih', report['net']], ['Dasar Get Data spreadsheet', report['tax_base']], ['Pajak 0,5%', report['tax_amount']]])
    return _csv_response(rows, f'transaksi-bulanan-{month}.csv')


@router.get('/get-data')
async def get_data(month: str, report: Literal['sales', 'purchases'] = 'sales',
                   owner: Optional[OwnerFilter] = None, category: Optional[CategoryFilter] = None,
                   tax: Optional[TaxFilter] = None, origin: Literal['live', 'preview'] = 'live',
                   page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), all_tax: bool = False):
    return await get_data_report(month, report, owner, category, None if all_tax else tax, origin, page, page_size)


@router.get('/get-data/csv')
async def get_data_csv(month: str, report: Literal['sales', 'purchases'] = 'sales',
                       owner: Optional[OwnerFilter] = None, category: Optional[CategoryFilter] = None,
                       tax: Optional[TaxFilter] = None, origin: Literal['live', 'preview'] = 'live', all_tax: bool = False):
    data = await get_data_report(month, report, owner, category, None if all_tax else tax, origin, page_size=None)
    rows = [['Tanggal transaksi', 'Jenis barang', 'No. faktur', 'Tanggal faktur', 'Harga jual termasuk PPN' if report == 'sales' else 'Harga beli termasuk PPN', 'Harga tanpa PPN', 'Nilai PPN', 'Nama pembeli/penjual']]
    for r in data['rows']:
        cells = [r[k] for k in ('date', 'item', 'invoice', 'invoice_date', 'amount', 'amount_without_vat', 'vat_amount', 'party')]
        rows.append(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in cells])
    rows.extend([[], ['Total', data['total']]])
    if data['count'] > data['summary_row_limit']:
        rows.extend([['Baris total sesuai REPORT U4', data['summarized_count']],
                     ['Jumlah seluruh baris', data['full_total']]])
    if report == 'sales':
        rows.append(['PPh 0,5% dasar Get Data spreadsheet', data['pph_final']])
    return _csv_response(rows, f'get-data-{report}-{month}.csv')
