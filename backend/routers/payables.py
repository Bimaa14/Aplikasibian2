"""Accounts payable (hutang distributor): list, catat hutang baru, tandai lunas."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lib.auth import require_user
from lib.db import db
from models.finance import AccountsPayable, PayableCreate
from models.finance import PaymentInput
from lib.debts import hydrate, pay

router = APIRouter(prefix="/payables", tags=["payables"], dependencies=[Depends(require_user)])


class PayableCreateBody(PayableCreate):
    # due_date arrives as YYYY-MM-DD string from the form; validate the shape
    pass


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
async def create_payable(body: PayableCreate):
    supplier = await db.suppliers.find_one({"id": body.supplier_id}, {"_id": 0})
    if not supplier:
        raise HTTPException(status_code=404, detail="Distributor tidak ditemukan")
    try:
        due = date.fromisoformat(body.due_date).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Format jatuh tempo harus YYYY-MM-DD")
    payable = AccountsPayable(
        supplier_id=body.supplier_id,
        supplier_name=supplier["name"],
        invoice_number=body.invoice_number,
        amount=body.amount,
        remaining=body.amount,
        due_date=due,
    )
    await db.accounts_payable.insert_one(payable.model_dump())
    return payable


@router.post("/{payable_id}/pay", response_model=AccountsPayable)
async def pay_payable(payable_id: str, body: PaymentInput, user: dict = Depends(require_user)):
    return await pay(db.accounts_payable, payable_id, body, user)
