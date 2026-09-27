"""Laporan kas harian, ringkasan bulanan (+ per pemilik), PPh final 0,5%, dan ekspor CSV.

Sumber data = `live_events()` (konsisten dgn laporan Excel). Ringkasan per pemilik dihitung
langsung dari transaction_details.owner (produk baru), data lama owner=None -> "Belum ditandai".
Aturan uang: distributor pakai UANG MODAL; pengeluaran + pajak + gaji pakai UANG LABA.
"""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from lib.auth import require_admin
from lib.db import db
from lib.dates import today_iso
from lib.debts import hydrate
from routers.excel_reports import live_events

router = APIRouter(prefix="/books", tags=["books"], dependencies=[Depends(require_admin)])

PPH_RATE = 0.005  # PPh Final UMKM 0,5% dari omzet
BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
OWNER_LABEL = {"bian": "Barang Bian", "ibu": "Barang Ibu (Mamah Bian)", "unassigned": "Belum ditandai (data lama)"}


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
    cash_sales = sum(e["amount"] for e in todays if e["kind"] == "cash_sale")
    receivable_payments = sum(e["amount"] for e in todays if e["kind"] == "credit_payment")
    transfer_payments = sum(e["amount"] for e in todays if e["kind"] == "credit_payment" and e.get("method") == "transfer")
    montir_fee = sum(e.get("fee", 0) for e in todays if _is_sale(e))
    expenses = sum(e["amount"] for e in todays if e["kind"] == "expense")
    net_cash = cash_sales + receivable_payments - transfer_payments - montir_fee - expenses
    return {
        "date": day,
        "cash_sales": cash_sales,
        "receivable_payments": receivable_payments,
        "transfer_payments": transfer_payments,
        "montir_fee": montir_fee,
        "expenses": expenses,
        "net_cash": net_cash,
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
        products = await db.products.find({"type": "barang"}, {"_id": 0, "stock": 1, "cost_price": 1}).to_list(None)
        stok_value = sum((p.get("stock", 0) or 0) * (p.get("cost_price", 0) or 0) for p in products)
        stok_basis = "valuasi stok produk terkini"
    return stok_value, piutang, hutang, stok_basis


async def _owner_summary(month: str) -> list:
    """Omzet (kecuali oli) & laba per pemilik untuk bagi hasil, dari transaction_details.owner."""
    txs = await db.transactions.find({"date_key": {"$regex": f"^{month}"}, "status": "completed"}, {"_id": 0, "id": 1}).to_list(None)
    ids = [t["id"] for t in txs]
    buckets = {k: {"omzet": 0.0, "laba": 0.0} for k in ("bian", "ibu", "unassigned")}
    if ids:
        async for d in db.transaction_details.find({"transaction_id": {"$in": ids}}, {"_id": 0}):
            key = d.get("owner") if d.get("owner") in ("bian", "ibu") else "unassigned"
            if (d.get("category", "") or "").upper() != "OIL":
                buckets[key]["omzet"] += d.get("subtotal", 0)
            buckets[key]["laba"] += d.get("spreadsheet_profit", d.get("subtotal", 0) - d.get("cost_price", 0) * d.get("qty", 0))
    return [{"owner": k, "label": OWNER_LABEL[k], "omzet": buckets[k]["omzet"], "laba": buckets[k]["laba"]} for k in ("bian", "ibu", "unassigned")]


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
    pph = round(omzet * PPH_RATE)
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
        ["Pembayaran piutang masuk", _rp(d["receivable_payments"])],
        ["Dikurangi: pembayaran via transfer", -_rp(d["transfer_payments"])],
        ["Dikurangi: komisi montir", -_rp(d["montir_fee"])],
        ["Dikurangi: pengeluaran", -_rp(d["expenses"])],
        ["KAS BERSIH HARI INI", _rp(d["net_cash"])],
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
async def tax(month: Optional[str] = Query(default=None)):
    m = month or today_iso()[:7]
    if not _valid_month(m):
        raise HTTPException(422, "Format bulan harus YYYY-MM")
    events = await live_events()
    me = [e for e in events if e.get("date", "")[:7] == m]
    omzet = sum(e["amount"] for e in me if _is_sale(e) and e.get("category", "").upper() != "OIL")
    omzet_bruto = sum(e["amount"] for e in me if _is_sale(e))
    pph = round(omzet * PPH_RATE)
    return {
        "month": m,
        "month_label": _month_label(m),
        "basis": "Total omzet (semua kecuali oli)",
        "omzet_base": omzet,
        "omzet_bruto": omzet_bruto,
        "rate": PPH_RATE,
        "pph_final": pph,
        "months_available": _months_from(events),
    }
