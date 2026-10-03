from typing import Optional
from fastapi import APIRouter, Depends
from lib.auth import require_user
from lib.db import db
from lib.debts import hydrate, pay
from models.finance import AccountsReceivable, PaymentInput

router = APIRouter(prefix='/receivables', tags=['receivables'], dependencies=[Depends(require_user)])


@router.get('', response_model=list[AccountsReceivable])
async def list_receivables(status: Optional[str] = None):
    query = {'status': status} if status in ('unpaid', 'partial', 'paid', 'void') else {}
    return [hydrate(d) async for d in db.accounts_receivable.find(query, {'_id': 0}).sort('due_date', 1)]


@router.post('/{receivable_id}/pay', response_model=AccountsReceivable)
async def pay_receivable(receivable_id: str, body: PaymentInput, user: dict = Depends(require_user)):
    return await pay(db.accounts_receivable, receivable_id, body, user)