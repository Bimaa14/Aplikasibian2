from typing import Optional
from fastapi import APIRouter, Depends
from lib.auth import require_user
from lib.db import db
from lib.debts import hydrate, pay
from models.finance import AccountsReceivable, CustomerReceivableSummary, PaymentInput

router = APIRouter(prefix='/receivables', tags=['receivables'], dependencies=[Depends(require_user)])


@router.get('', response_model=list[AccountsReceivable])
async def list_receivables(status: Optional[str] = None):
    query = {'status': status} if status in ('unpaid', 'partial', 'paid', 'void') else {}
    return [hydrate(d) async for d in db.accounts_receivable.find(query, {'_id': 0}).sort('due_date', 1)]


@router.get('/summary/by-customer', response_model=list[CustomerReceivableSummary])
async def summarize_receivables_by_customer():
    groups = {}
    async for raw in db.accounts_receivable.find({'status': {'$ne': 'void'}}, {'_id': 0}):
        debt = hydrate(raw)
        customer_id = (debt.get('customer_id') or '').strip()
        customer_name = ' '.join((debt.get('customer_name') or '').split())
        key = ('id', customer_id) if customer_id else ('name', customer_name.casefold())
        summary = groups.setdefault(key, dict(customer_id=customer_id or None, customer_name=customer_name,
                                             total_credit=0, total_paid=0, outstanding=0, invoice_count=0))
        summary['total_credit'] += debt['amount']
        summary['total_paid'] += debt['paid_amount']
        summary['outstanding'] += debt['remaining']
        summary['invoice_count'] += 1
    return sorted(({**summary, **{key: round(summary[key], 2) for key in ('total_credit', 'total_paid', 'outstanding')}}
                   for summary in groups.values()), key=lambda row: (-row['outstanding'], row['customer_name'].casefold()))


@router.post('/{receivable_id}/pay', response_model=AccountsReceivable)
async def pay_receivable(receivable_id: str, body: PaymentInput, user: dict = Depends(require_user)):
    return await pay(db.accounts_receivable, receivable_id, body, user)
