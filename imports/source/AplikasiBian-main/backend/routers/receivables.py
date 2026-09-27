"""Accounts receivable (piutang pelanggan): list + tandai lunas."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import require_user
from lib.db import db
from models.finance import AccountsReceivable

router = APIRouter(prefix="/receivables", tags=["receivables"], dependencies=[Depends(require_user)])


@router.get("", response_model=List[AccountsReceivable])
async def list_receivables(status: Optional[str] = None):
    query: dict = {}
    if status in ("unpaid", "paid"):
        query["status"] = status
    docs = (
        await db.accounts_receivable.find(query, {"_id": 0})
        .sort([("status", 1), ("due_date", 1)])
        .to_list(1000)
    )
    return [AccountsReceivable(**d) for d in docs]


@router.post("/{receivable_id}/pay", response_model=AccountsReceivable)
async def pay_receivable(receivable_id: str):
    doc = await db.accounts_receivable.find_one({"id": receivable_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Piutang tidak ditemukan")
    if doc["status"] == "paid":
        raise HTTPException(status_code=400, detail="Piutang sudah lunas")
    await db.accounts_receivable.update_one({"id": receivable_id}, {"$set": {"status": "paid"}})
    doc["status"] = "paid"
    return AccountsReceivable(**doc)
