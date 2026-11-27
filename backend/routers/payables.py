"""Accounts payable (hutang distributor): list, catat hutang baru, ubah, bayar cicilan."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import require_user
from lib.dates import today_iso
from lib.db import db
from models.finance import AccountsPayable, PayableCreate, PayableUpdate, PaymentInput
from lib.debts import hydrate, pay, update_debt

router = APIRouter(prefix="/payables", tags=["payables"], dependencies=[Depends(require_user)])


@router.get("", response_model=List[AccountsPayable])
async def list_payables(status: Optional[str] = None):
    query: dict = {}
    if status in ("unpaid", "partial", "paid", "void"):
        query["status"] = status
    docs = (
        await db.accounts_payable.find(query, {"_id": 0})
        .sort([("status", 1), ("due_date", 1)])
        .to_list(1000)
    )
    return [AccountsPayable(**hydrate(d)) for d in docs]


@router.post("", response_model=AccountsPayable, status_code=201)
async def create_payable(body: PayableCreate, user: dict = Depends(require_user)):
    supplier = await db.suppliers.find_one({"id": body.supplier_id}, {"_id": 0})
    if not supplier:
        raise HTTPException(status_code=404, detail="Distributor tidak ditemukan")
    try:
        due = date.fromisoformat(body.due_date).isoformat()
        issued = date.fromisoformat(body.issued_date).isoformat() if body.issued_date else today_iso()
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD")
    payable = AccountsPayable(
        supplier_id=body.supplier_id,
        supplier_name=supplier["name"],
        invoice_number=body.invoice_number,
        amount=body.amount,
        remaining=body.amount,
        issued_date=issued,
        due_date=due,
        note=body.note,
    )
    doc = {**payable.model_dump(), "created_by": user["id"]}
    await db.accounts_payable.insert_one(doc)
    return AccountsPayable(**hydrate(doc))


@router.put("/{payable_id}", response_model=AccountsPayable)
async def update_payable(payable_id: str, body: PayableUpdate, user: dict = Depends(require_user)):
    supplier = await db.suppliers.find_one({"id": body.supplier_id}, {"_id": 0})
    if not supplier:
        raise HTTPException(status_code=404, detail="Distributor tidak ditemukan")
    try:
        due = date.fromisoformat(body.due_date).isoformat()
        issued = date.fromisoformat(body.issued_date).isoformat() if body.issued_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD")
    updates = {
        "supplier_id": body.supplier_id,
        "supplier_name": supplier["name"],
        "invoice_number": body.invoice_number,
        "amount": body.amount,
        "due_date": due,
        "note": body.note,
    }
    if issued:
        updates["issued_date"] = issued
    return await update_debt(db.accounts_payable, payable_id, updates, user)


@router.post("/{payable_id}/pay", response_model=AccountsPayable)
async def pay_payable(payable_id: str, body: PaymentInput, user: dict = Depends(require_user)):
    return await pay(db.accounts_payable, payable_id, body, user)
