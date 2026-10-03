"""Suppliers (distributor) CRUD."""

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import require_admin, require_user
from lib.db import db
from models.partner import Supplier, SupplierCreate

# Data distributor hanya dikelola admin; kasir boleh membaca (referensi).
router = APIRouter(prefix="/suppliers", tags=["suppliers"], dependencies=[Depends(require_user)])


@router.get("", response_model=List[Supplier])
async def list_suppliers(search: Optional[str] = None):
    query: dict = {}
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        query["$or"] = [{"name": rx}, {"phone": rx}]
    docs = await db.suppliers.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    return [Supplier(**d) for d in docs]


@router.post("", response_model=Supplier, status_code=201, dependencies=[Depends(require_admin)])
async def create_supplier(body: SupplierCreate):
    supplier = Supplier(**body.model_dump())
    await db.suppliers.insert_one(supplier.model_dump())
    return supplier


@router.put("/{supplier_id}", response_model=Supplier, dependencies=[Depends(require_admin)])
async def update_supplier(supplier_id: str, body: SupplierCreate):
    doc = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Distributor tidak ditemukan")
    doc.update(body.model_dump())
    supplier = Supplier(**doc)
    await db.suppliers.replace_one({"id": supplier_id}, supplier.model_dump())
    return supplier


@router.delete("/{supplier_id}", dependencies=[Depends(require_admin)])
async def delete_supplier(supplier_id: str):
    result = await db.suppliers.delete_one({"id": supplier_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Distributor tidak ditemukan")
    return {"ok": True}
