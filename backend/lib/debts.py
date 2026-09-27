import asyncio
import uuid
from datetime import date, datetime, timezone
from fastapi import HTTPException
from pymongo import ReturnDocument
from lib.db import db
from lib.dates import today_iso

# This runtime is configured with one uvicorn worker. Mongo version checks also
# protect payment writes; this lock serializes multi-document POS returns/payments.
financial_lock = asyncio.Lock()


def hydrate(doc):
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['paid_amount'] = d.get('paid_amount', d['amount'] if d.get('status') == 'paid' else 0)
    d['remaining'] = 0 if d.get('status') in ('paid', 'void') else round(d['amount'] - d['paid_amount'], 2)
    d.setdefault('payments', [])
    d.setdefault('version', 0)
    d.setdefault('issued_date', '')
    d['legacy_payment_history_missing'] = bool(d['paid_amount'] and not d['payments'])
    active = d['status'] in ('unpaid', 'partial')
    delta = (date.fromisoformat(d['due_date']) - date.fromisoformat(today_iso())).days
    overdue = max(0, -delta) if active else 0
    d.update(days_overdue=overdue, days_remaining=delta if active else 0, aging_bucket=None,
             due_label='Retur / Void' if d['status'] == 'void' else 'Lunas')
    if active:
        d['due_label'] = f'Telat {overdue} hari' if delta < 0 else 'Jatuh tempo hari ini' if delta == 0 else f'Belum jatuh tempo ({delta} hari lagi)'
        if delta <= 0:
            d['aging_bucket'] = '0-30' if overdue <= 30 else '31-60' if overdue <= 60 else '61-90' if overdue <= 90 else '90+'
    return d


async def pay(collection, debt_id, body, user):
    async with financial_lock:
        raw = await collection.find_one({'id': debt_id}, {'_id': 0})
        if not raw:
            raise HTTPException(404, 'Tagihan tidak ditemukan')
        d = hydrate(raw)
        existing = next((p for p in d['payments'] if p['request_id'] == body.request_id), None)
        if existing:
            if any(existing.get(k) != getattr(body, k) for k in ('amount', 'method', 'note')) or existing['payment_date'] != body.payment_date.isoformat() or (body.profit_amount is not None and existing['profit_amount'] != body.profit_amount):
                raise HTTPException(409, 'ID pembayaran sudah dipakai untuk rincian berbeda')
            return d
        if d['status'] not in ('unpaid', 'partial'):
            raise HTTPException(409, 'Tagihan sudah lunas atau Void')
        if body.amount > d['remaining']:
            raise HTTPException(422, 'Pembayaran melebihi sisa tagihan')
        paid_on = body.payment_date.isoformat()
        if paid_on > today_iso() or paid_on < d.get('issued_date', ''):
            raise HTTPException(422, 'Tanggal pembayaran harus antara tanggal transaksi dan hari ini')
        tx = None
        if d.get('transaction_id'):
            tx = await db.transactions.find_one({'id': d['transaction_id']}, {'_id': 0})
            if tx and tx.get('status') != 'completed':
                raise HTTPException(409, 'Transaksi sudah diretur')
        profit = body.profit_amount
        if profit is None:
            profit = round((tx or {}).get('spreadsheet_profit', (tx or {}).get('total_profit', 0)) * body.amount / d['amount'], 2)
        p = body.model_dump(mode='json')
        p.update(id=str(uuid.uuid4()), profit_amount=profit, recorded_by=user['id'], created_at=datetime.now(timezone.utc).isoformat())
        remaining = round(d['remaining'] - body.amount, 2)
        query = {'id': debt_id, 'version': raw.get('version', {'$exists': False})}
        result = await collection.find_one_and_update(query,
            {'$set': {'paid_amount': round(d['paid_amount'] + body.amount, 2), 'remaining': remaining,
                      'status': 'paid' if remaining == 0 else 'partial', 'version': d['version'] + 1},
             '$push': {'payments': p}}, projection={'_id': 0}, return_document=ReturnDocument.AFTER)
        if not result:
            raise HTTPException(409, 'Tagihan berubah. Muat ulang sebelum membayar lagi')
        return hydrate(result)


async def migrate_returned_debts():
    ids = await db.transactions.distinct('id', {'status': 'returned'})
    if ids:
        await db.accounts_receivable.update_many({'transaction_id': {'$in': ids}, 'status': {'$ne': 'void'}},
                                                {'$set': {'status': 'void', 'remaining': 0, 'legacy_return_migrated': True}})