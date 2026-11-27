from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import require_user
from lib.dates import today_iso
from lib.db import db
from lib.debts import hydrate, pay, update_debt
from models.finance import (
    AccountsReceivable,
    CustomerReceivableSummary,
    PaymentInput,
    ReceivableCreate,
    ReceivableUpdate,
)

router = APIRouter(prefix='/receivables', tags=['receivables'], dependencies=[Depends(require_user)])


async def _resolve_customer(customer_id: Optional[str], customer_name: Optional[str]):
    if customer_id:
        customer = await db.customers.find_one({'id': customer_id}, {'_id': 0})
        if not customer:
            raise HTTPException(404, 'Pelanggan tidak ditemukan')
        return customer['id'], customer['name']
    return '', (customer_name or '').strip()


@router.get('', response_model=list[AccountsReceivable])
async def list_receivables(status: Optional[str] = None):
    query = {'status': status} if status in ('unpaid', 'partial', 'paid', 'void') else {}
    return [hydrate(d) async for d in db.accounts_receivable.find(query, {'_id': 0}).sort('due_date', 1)]


@router.post('', response_model=AccountsReceivable, status_code=201)
async def create_receivable(body: ReceivableCreate, user: dict = Depends(require_user)):
    customer_id, customer_name = await _resolve_customer(body.customer_id, body.customer_name)
    due = date.fromisoformat(body.due_date).isoformat()
    issued = date.fromisoformat(body.issued_date).isoformat() if body.issued_date else today_iso()
    receivable = AccountsReceivable(
        transaction_id='',
        invoice_number=body.invoice_number,
        customer_id=customer_id,
        customer_name=customer_name,
        amount=body.amount,
        remaining=body.amount,
        issued_date=issued,
        due_date=due,
        note=body.note,
    )
    doc = {**receivable.model_dump(), 'created_by': user['id']}
    await db.accounts_receivable.insert_one(doc)
    return AccountsReceivable(**hydrate(doc))


@router.put('/{receivable_id}', response_model=AccountsReceivable)
async def update_receivable(receivable_id: str, body: ReceivableUpdate, user: dict = Depends(require_user)):
    customer_id, customer_name = await _resolve_customer(body.customer_id, body.customer_name)
    updates = {
        'customer_id': customer_id,
        'customer_name': customer_name,
        'invoice_number': body.invoice_number,
        'amount': body.amount,
        'due_date': date.fromisoformat(body.due_date).isoformat(),
        'note': body.note,
    }
    if body.issued_date:
        updates['issued_date'] = date.fromisoformat(body.issued_date).isoformat()
    return await update_debt(db.accounts_receivable, receivable_id, updates, user)


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
