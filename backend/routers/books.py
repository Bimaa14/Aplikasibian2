"""Laporan kas harian, ringkasan bulanan (+ per pemilik), PPh final 0,5%, dan ekspor CSV.

Sumber data = `live_events()` (konsisten dgn laporan Excel). Ringkasan per pemilik dihitung
langsung dari transaction_details.owner (produk baru), data lama owner=None -> "Belum ditandai".
Aturan uang: distributor pakai UANG MODAL; pengeluaran + pajak + gaji pakai UANG LABA.
"""
import csv
import io
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from lib.auth import require_admin
from lib.db import db
from lib.dates import today_iso
from lib.debts import hydrate
from routers.excel_reports import live_events
from lib.sales import sales_report, month_bounds, OwnerFilter, CategoryFilter, TaxFilter
from models.transaction import PaymentMethod
from lib.custom_report import get_data_report
from lib.excel_rules import store_report

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
    return len(d) == 10 and d[4] == "-" and d[7] == "-"


def _valid_month(m: str) -> bool:
    return len(m) == 7 and m[4] == "-"


async def _daily_data(day: str) -> dict:
    events = await live_events()
    todays = [e for e in events if e.get("date") == day]
    cash_sales = sum(e["amount"] for e in todays if e["kind"] == "cash_sale" and e.get("method", "cash") == "cash")
    non_cash_sales = sum(e["amount"] for e in todays if e["kind"] == "cash_sale" and e.get("method", "cash") != "cash")
    receivable_payments = sum(e["amount"] for e in todays if e["kind"] == "credit_payment")
    transfer_payments = sum(e["amount"] for e in todays if e["kind"] == "credit_payment" and e.get("method", "cash") != "cash")
    montir_fee = sum(e.get("fee", 0) for e in todays if _is_sale(e))
    expenses = sum(e["amount"] for e in todays if e["kind"] == "expense")
    net_cash = cash_sales + receivable_payments - transfer_payments - montir_fee - expenses
    breakdown = store_report(todays, day[:7])
    oil_sales = [e for e in todays if _is_sale(e) and (e.get("category") or "").upper() == "OIL"]
    return {
        "date": day,
        "cash_sales": cash_sales,
        "non_cash_sales": non_cash_sales,
        "receivable_payments": receivable_payments,
        "transfer_payments": transfer_payments,
        "montir_fee": montir_fee,
        "expenses": expenses,
        "net_cash": net_cash,
        "modal": breakdown["modal"],
        "laba": breakdown["laba"],
        "spooring": breakdown["spooring"],
        "oil_revenue": sum(e["amount"] for e in oil_sales),
        "oil_benefit": sum(e.get("profit", 0) for e in oil_sales),
        "months_available": _months_from(events),
    }


async def _asset_snapshot():
    """Aset lancar terkini. Stok memakai nilai resmi snapshot (B19, 2 Juni 2026) bila ada."""
    piutang = sum([hydrate(d)["remaining"] async for d in db.accounts_receivable.find({}, {"_id": 0})])
    hutang = sum([hydrate(d)["remaining"] async for d in db.accounts_payable.find({}, {"_id": 0})])
    snap = await db.excel_snapshots.find_one({"source": "september"}, {"_id": 0})
    if snap and snap.get("inputs", {}).get("stok"):
        stok_value = float(snap["inputs"]["stok"])
        stok_basis = "snapshot stok 2 Juni 2026 (B19)"
    else:
        products = await db.products.find({"type": "barang", "active": {"$ne": False}}, {"_id": 0, "stock": 1, "cost_price": 1}).to_list(None)
        stok_value = sum((p.get("stock", 0) or 0) * (p.get("cost_price", 0) or 0) for p in products)
        stok_basis = "valuasi stok produk terkini"
    return stok_value, piutang, hutang, stok_basis


async def _owner_summary(month: str) -> list:
    """Omzet (kecuali oli) & laba per pemilik untuk bagi hasil, dari transaction_details.owner."""
    txs = await db.transactions.find({"date_key": {"$regex": f"^{month}"}, "status": "completed"}, {"_id": 0, "id": 1}).to_list(None)
    ids = [t["id"] for t in txs]
    buckets = {k: {"omzet": 0.0, "laba": 0.0} for k in OWNER_LABEL}
    if ids:
        async for d in db.transaction_details.find({"transaction_id": {"$in": ids}}, {"_id": 0}):
            key = d.get("owner") if d.get("owner") in OWNER_LABEL else "unassigned"
            if (d.get("category", "") or "").upper() != "OIL":
                buckets[key]["omzet"] += d.get("subtotal", 0)
            buckets[key]["laba"] += d.get("spreadsheet_profit", d.get("subtotal", 0) - d.get("cost_price", 0) * d.get("qty", 0))
    return [{"owner": k, "label": OWNER_LABEL[k], "omzet": buckets[k]["omzet"], "laba": buckets[k]["laba"]} for k in OWNER_LABEL]


async def _monthly_data(m: str) -> dict:
    events = await live_events()
    me = [e for e in events if e.get("date", "")[:7] == m]
    omzet = sum(e["amount"] for e in me if _is_sale(e) and e.get("category", "").upper() != "OIL")
    omzet_bruto = sum(e["amount"] for e in me if _is_sale(e))
    oli = omzet_bruto - omzet
    distributor = sum(e["amount"] for e in me if e["kind"] == "supplier_payment")
    expenses_total = sum(e["amount"] for e in me if e["kind"] == "expense")
    gaji = sum(e["amount"] for e in me if e["kind"] == "expense" and "gaji" in e.get("category", "").lower())
    pengeluaran = expenses_total - gaji
    tax_data = await sales_report(m)
    pph = tax_data['tax_amount']
    stok_value, piutang, hutang, stok_basis = await _asset_snapshot()
    sisa_aset = stok_value + piutang - hutang
    owner_summary = await _owner_summary(m)
    return {
        "month": m,
        "month_label": _month_label(m),
        "omzet": omzet,
        "omzet_bruto": omzet_bruto,
        "oli": oli,
        "distributor_payment": distributor,
        "expenses": pengeluaran,
        "expenses_total": expenses_total,
        "gaji": gaji,
        "pph_final": pph,
        "pph_rate": PPH_RATE,
        "tax_base": tax_data['tax_base'],
        "unassigned_tax_net": tax_data['unassigned_tax_net'],
        "sisa_aset": sisa_aset,
        "stok_value": stok_value,
        "stok_basis": stok_basis,
        "piutang_outstanding": piutang,
        "hutang_outstanding": hutang,
        "funding": {
            "modal": {"label": "Uang Modal", "total": distributor,
                      "items": [{"name": "Pembayaran distributor", "amount": distributor}]},
            "laba": {"label": "Uang Laba", "total": pengeluaran + pph + gaji,
                     "items": [{"name": "Pengeluaran", "amount": pengeluaran},
                               {"name": "Pajak (PPh final 0,5%)", "amount": pph},
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
        ["Penjualan non-tunai (di luar kas fisik)", _rp(d["non_cash_sales"])],
        ["Pembayaran piutang masuk", _rp(d["receivable_payments"])],
        ["Dikurangi: pembayaran piutang non-tunai", -_rp(d["transfer_payments"])],
        ["Dikurangi: komisi montir", -_rp(d["montir_fee"])],
        ["Dikurangi: pengeluaran", -_rp(d["expenses"])],
        ["KAS BERSIH HARI INI", _rp(d["net_cash"])],
        [],
        ["Ringkasan Modal dan Laba (definisi spreadsheet)", "Jumlah (Rp)"],
        ["Modal", _rp(d["modal"])],
        ["Laba (tanpa oli dan spooring)", _rp(d["laba"])],
        ["Spooring / Service", _rp(d["spooring"])],
        [],
        ["Laporan Oli", "Jumlah (Rp)"],
        ["Pendapatan oli", _rp(d["oil_revenue"])],
        ["Benefit oli", _rp(d["oil_benefit"])],
    ]
    return _csv_response(rows, f"laporan-harian-{day}.csv")


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
        ["1. Total omzet (semua kecuali oli)", _rp(r["omzet"])],
        ["   Omzet termasuk oli", _rp(r["omzet_bruto"])],
        ["2. Pembayaran ke distributor", _rp(r["distributor_payment"])],
        ["3. Pengeluaran", _rp(r["expenses"])],
        ["   Gaji karyawan", _rp(r["gaji"])],
        ["   Pajak (PPh final 0,5%)", _rp(r["pph_final"])],
        ["4. Sisa aset", _rp(r["sisa_aset"])],
        [],
        ["Sumber Uang", "Jumlah (Rp)"],
        ["Uang Modal — Pembayaran distributor", _rp(r["distributor_payment"])],
        ["Uang Laba — Pengeluaran", _rp(r["expenses"])],
        ["Uang Laba — Pajak (PPh final)", _rp(r["pph_final"])],
        ["Uang Laba — Gaji karyawan", _rp(r["gaji"])],
        [],
        ["Ringkasan Per Pemilik (bagi hasil)", "Omzet (kecuali oli)", "Laba"],
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
        "basis": "Penjualan bersih setelah potongan, hanya item TAX = 1",
        "omzet_base": report['tax_base'],
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
    rows.extend([[], ['Total bersih', report['net']], ['Dasar pajak TAX = 1', report['tax_base']], ['Pajak 0,5%', report['tax_amount']]])
    return _csv_response(rows, f'transaksi-bulanan-{month}.csv')


@router.get('/get-data')
async def get_data(month: str, report: Literal['sales', 'purchases'] = 'sales',
                   owner: Optional[OwnerFilter] = None, category: Optional[CategoryFilter] = None,
                   tax: Optional[TaxFilter] = '1', origin: Literal['live', 'preview'] = 'live',
                   page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), all_tax: bool = False):
    return await get_data_report(month, report, owner, category, None if all_tax else tax, origin, page, page_size)


@router.get('/get-data/csv')
async def get_data_csv(month: str, report: Literal['sales', 'purchases'] = 'sales',
                       owner: Optional[OwnerFilter] = None, category: Optional[CategoryFilter] = None,
                       tax: Optional[TaxFilter] = '1', origin: Literal['live', 'preview'] = 'live', all_tax: bool = False):
    data = await get_data_report(month, report, owner, category, None if all_tax else tax, origin, page_size=None)
    rows = [['Tanggal transaksi', 'Jenis barang', 'No. faktur', 'Tanggal faktur', 'Harga jual termasuk PPN' if report == 'sales' else 'Harga beli termasuk PPN', 'Harga tanpa PPN', 'Nilai PPN', 'Nama pembeli/penjual']]
    for r in data['rows']:
        cells = [r[k] for k in ('date', 'item', 'invoice', 'invoice_date', 'amount', 'amount_without_vat', 'vat_amount', 'party')]
        rows.append(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in cells])
    rows.extend([[], ['Total', data['total']]])
    if report == 'sales':
        rows.append(['PPh 0,5% TAX = 1', data['pph_final']])
    return _csv_response(rows, f'get-data-{report}-{month}.csv')
