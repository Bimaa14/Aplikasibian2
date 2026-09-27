"""Riwayat kendaraan — agregasi servis per nomor polisi (vehicle_plate di transaksi)."""
from typing import List, Optional

from pydantic import BaseModel

from models.transaction import Transaction


class VehicleServiceSummary(BaseModel):
    plate: str
    visit_count: int
    total_spent: float
    last_visit: Optional[str] = None  # YYYY-MM-DD
    last_customer: Optional[str] = None
    last_tire: Optional[str] = None       # ban terakhir yang dipakai
    last_tire_date: Optional[str] = None
    last_oil: Optional[str] = None        # oli terakhir yang dipakai
    last_oil_date: Optional[str] = None


class VehicleDetail(BaseModel):
    plate: str
    visit_count: int
    total_spent: float
    last_visit: Optional[str] = None
    last_customer: Optional[str] = None
    last_tire: Optional[str] = None
    last_tire_date: Optional[str] = None
    last_oil: Optional[str] = None
    last_oil_date: Optional[str] = None
    services: List[Transaction] = []
