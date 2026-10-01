"""Expenses (pengeluaran operasional bengkel)."""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import require_user
from lib.db import db
from lib.dates import today_iso
from models.finance import Expense, ExpenseCreate

router = APIRouter(prefix="/expenses", tags=["expenses"], dependencies=[Depends(require_user)])


@router.get("", response_model=List[Expense])
async def list_expenses():
    docs = await db.expenses.find({}, {"_id": 0}).sort("date", -1).to_list(1000)
    return [Expense(**d) for d in docs]


@router.post("", response_model=Expense, status_code=201)
async def create_expense(body: ExpenseCreate):
    expense_date = body.date or today_iso()
    try:
        expense_date = date.fromisoformat(expense_date).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD")
    expense = Expense(
        date=expense_date,
        amount=body.amount,
        category=body.category,
        description=body.description,
    )
    await db.expenses.insert_one(expense.model_dump())
    return expense


@router.delete("/{expense_id}")
async def delete_expense(expense_id: str):
    result = await db.expenses.delete_one({"id": expense_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pengeluaran tidak ditemukan")
    return {"ok": True}
