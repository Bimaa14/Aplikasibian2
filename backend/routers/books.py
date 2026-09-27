"""Laporan kas harian, ringkasan bulanan, dan PPh final 0.5% (dari omzet).

Sumber data = `live_events()` yang sama dipakai laporan Excel, jadi angkanya konsisten
dengan pembukuan spreadsheet. Aturan uang (dari pemilik):
- Pembayaran distributor memakai UANG MODAL.
- Pengeluaran, pajak (PPh final), dan gaji karyawan memakai UANG LABA.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from lib.auth import require_admin
from lib.db import db
from lib.dates import today_iso
from lib.debts import hydrate
from routers.excel_reports import live_events

router = APIRouter(prefix="/books", tags=["books"], dependencies=[Depends(require_admin)])

PPH_RATE = 0.005  # PPh Final UMKM 0,5% dari peredaran bruto (omzet)
BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


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


@router.get("/daily")
async def daily(date: Optional[str] = Query(default=None)):
    """Rekonsiliasi kas harian: pendapatan tunai + bayar piutang − bayar transfer − komisi montir − pengeluaran."""
    day = date or today_iso()
    if len(day) != 10 or day[4] != "-" or day[7] != "-":
        raise HTTPException(422, "Format tanggal harus YYYY-MM-DD")
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
        "cash_sales": cash_sales,                 # total pendapatan tunai hari itu
        "receivable_payments": receivable_payments,  # pembayaran piutang yang masuk
        "transfer_payments": transfer_payments,   # bagian pembayaran via transfer (dikurangi)
        "montir_fee": montir_fee,                 # komisi ke montir
        "expenses": expenses,                     # pengeluaran hari itu
        "net_cash": net_cash,                     # kas bersih di laci hari itu
        "months_available": _months_from(events),
    }


async def _asset_snapshot():
    """Aset lancar terkini. Stok memakai nilai resmi snapshot (B19, 2 Juni 2026) bila ada —
    valuasi stok mentah produk tidak dipakai karena berbeda jauh dari dasar laporan."""
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


@router.get("/monthly")
async def monthly(month: Optional[str] = Query(default=None)):
    m = month or today_iso()[:7]
    if len(m) != 7 or m[4] != "-":
        raise HTTPException(422, "Format bulan harus YYYY-MM")
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

    return {
        "month": m,
        "month_label": _month_label(m),
        "omzet": omzet,                       # 1. Total omzet (semua kecuali oli)
        "omzet_bruto": omzet_bruto,
        "oli": oli,
        "distributor_payment": distributor,   # 2. Pembayaran ke distributor
        "expenses": pengeluaran,              # 3. Pengeluaran (di luar gaji)
        "expenses_total": expenses_total,
        "gaji": gaji,
        "pph_final": pph,                     # pajak PPh final 0,5% dari omzet
        "pph_rate": PPH_RATE,
        "sisa_aset": sisa_aset,               # 4. Sisa aset (stok + piutang − hutang, terkini)
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
        "months_available": _months_from(events),
    }


@router.get("/tax")
async def tax(month: Optional[str] = Query(default=None)):
    m = month or today_iso()[:7]
    if len(m) != 7 or m[4] != "-":
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
