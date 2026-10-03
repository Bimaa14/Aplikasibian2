"""Riwayat kendaraan: daftar nomor polisi + detail servis (ban & oli terakhir yang dipakai)."""

import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import require_user
from lib.db import db
from models.transaction import Transaction, TransactionDetail
from models.vehicle import VehicleDetail, VehicleServiceSummary

router = APIRouter(prefix="/vehicles", tags=["vehicles"], dependencies=[Depends(require_user)])

# Klasifikasi dari SKU/nama produk: BAN-* = ban, OLI-* = oli
TIRE_RX = re.compile(r"^BAN|ban ", re.IGNORECASE)
OIL_RX = re.compile(r"^OLI|oli ", re.IGNORECASE)


def _norm_dt(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_tire(d: dict) -> bool:
    return d.get("product_type") == "barang" and bool(TIRE_RX.match(d.get("product_name", "")))


def _is_oil(d: dict) -> bool:
    return d.get("product_type") == "barang" and bool(OIL_RX.match(d.get("product_name", "")))


async def _plate_rows(plate: Optional[str] = None) -> dict:
    """Kumpulkan transaksi (completed) yang punya vehicle_plate, dikelompokkan per plat."""
    query: dict = {"vehicle_plate": {"$nin": [None, ""]}, "status": "completed"}
    if plate:
        query["vehicle_plate"] = plate.upper()
    txs = await db.transactions.find(query, {"_id": 0}).sort("date", -1).to_list(2000)
    if not txs:
        return {}
    details = await db.transaction_details.find(
        {"transaction_id": {"$in": [t["id"] for t in txs]}}, {"_id": 0}
    ).to_list(20000)
    by_tx: dict = {}
    for d in details:
        by_tx.setdefault(d["transaction_id"], []).append(d)

    grouped: dict = {}
    for t in txs:
        grouped.setdefault(t["vehicle_plate"], []).append((t, by_tx.get(t["id"], [])))
    return grouped


def _summarise(plate: str, rows: list) -> dict:
    # rows sudah terurut tanggal desc
    visit_count = len(rows)
    total_spent = sum(t.get("total_amount", 0) for t, _ in rows)
    last_tx = rows[0][0]
    last_tire = last_tire_date = last_oil = last_oil_date = None
    for t, dets in rows:  # dari terbaru
        for d in dets:
            if last_tire is None and _is_tire(d):
                last_tire, last_tire_date = d["product_name"], t.get("date_key")
            if last_oil is None and _is_oil(d):
                last_oil, last_oil_date = d["product_name"], t.get("date_key")
        if last_tire and last_oil:
            break
    return {
        "plate": plate,
        "visit_count": visit_count,
        "total_spent": total_spent,
        "last_visit": last_tx.get("date_key"),
        "last_customer": last_tx.get("customer_name"),
        "last_tire": last_tire,
        "last_tire_date": last_tire_date,
        "last_oil": last_oil,
        "last_oil_date": last_oil_date,
    }


@router.get("", response_model=List[VehicleServiceSummary])
async def list_vehicles(search: Optional[str] = None):
    grouped = await _plate_rows()
    out = [_summarise(plate, rows) for plate, rows in grouped.items()]
    if search:
        term = search.strip().upper()
        out = [v for v in out if term in v["plate"]]
    out.sort(key=lambda v: (v["last_visit"] or "", v["plate"]), reverse=True)
    return [VehicleServiceSummary(**v) for v in out]


@router.get("/{plate}", response_model=VehicleDetail)
async def vehicle_detail(plate: str):
    grouped = await _plate_rows(plate)
    key = plate.upper()
    if key not in grouped:
        raise HTTPException(status_code=404, detail="Kendaraan belum punya riwayat servis")
    rows = grouped[key]
    summary = _summarise(key, rows)
    services = []
    for t, dets in rows:
        t = dict(t)
        t.pop("details", None)
        t["date"] = _norm_dt(t["date"])
        services.append(Transaction(**t, details=[TransactionDetail(**d) for d in dets]))
    return VehicleDetail(**summary, services=services)
