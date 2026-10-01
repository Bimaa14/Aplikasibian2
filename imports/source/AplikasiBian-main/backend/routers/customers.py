"""Customers (pelanggan) CRUD."""

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import require_admin, require_user
from lib.db import db
from models.partner import Customer, CustomerCreate

# Baca & tambah pelanggan: semua user login (kasir perlu saat checkout tempo). Ubah/hapus: admin.
router = APIRouter(prefix="/customers", tags=["customers"], dependencies=[Depends(require_user)])


@router.get("", response_model=List[Customer])
async def list_customers(search: Optional[str] = None):
    query: dict = {}
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        query["$or"] = [{"name": rx}, {"phone": rx}]
    docs = await db.customers.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    return [Customer(**d) for d in docs]


@router.post("", response_model=Customer, status_code=201)
async def create_customer(body: CustomerCreate):
    customer = Customer(**body.model_dump())
    await db.customers.insert_one(customer.model_dump())
    return customer


@router.put("/{customer_id}", response_model=Customer, dependencies=[Depends(require_admin)])
async def update_customer(customer_id: str, body: CustomerCreate):
    doc = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Pelanggan tidak ditemukan")
    doc.update(body.model_dump())
    customer = Customer(**doc)
    await db.customers.replace_one({"id": customer_id}, customer.model_dump())
    return customer


@router.delete("/{customer_id}", dependencies=[Depends(require_admin)])
async def delete_customer(customer_id: str):
    result = await db.customers.delete_one({"id": customer_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pelanggan tidak ditemukan")
    return {"ok": True}
