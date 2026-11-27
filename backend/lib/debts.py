import uuid
import re
from datetime import date, datetime, timezone
from fastapi import HTTPException
from pymongo import ReturnDocument
from lib.db import db
from lib.dates import today_iso
from lib.financial_operations import financial_lock
from lib.excel_rules import line_snapshot_values, n

# This runtime is configured with one uvicorn worker. Mongo version checks also
# protect payment writes; this lock serializes multi-document POS returns/payments.


def hydrate(doc):
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['paid_amount'] = d.get('paid_amount', d['amount'] if d.get('status') == 'paid' else 0)
    d['remaining'] = 0 if d.get('status') in ('paid', 'void') else round(d['amount'] - d['paid_amount'], 2)
    d.setdefault('payments', [])
    d.setdefault('version', 0)
    d.setdefault('issued_date', '')
    d.setdefault('note', '')
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
        existing = next((p for p in d['payments'] if p.get('request_id') == body.request_id), None)
        if existing:
            if (any(existing.get(k) != getattr(body, k) for k in ('amount', 'method', 'note', 'cash_amount', 'transfer_amount', 'transfer_method'))
                    or existing['payment_date'] != body.payment_date.isoformat()
                    or (body.profit_amount is not None and existing['profit_amount'] != body.profit_amount)
                    or (existing.get('profit_is_manual') is not None
                        and existing['profit_is_manual'] != (body.profit_amount is not None))):
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
        if collection.name == 'accounts_receivable':
            available_profit = await remaining_credit_profit(d, tx)
            automatic_profit = min(n(body.amount), available_profit or n(0))
            if profit is None:
                profit = float(automatic_profit)
            elif n(profit) > n(body.amount) or (available_profit is not None and n(profit) > available_profit):
                raise HTTPException(422, 'Porsi laba melebihi pembayaran atau sisa laba transaksi')
        elif profit is None:
            profit = 0
        p = body.model_dump(mode='json')
        p.update(id=str(uuid.uuid4()), profit_amount=profit, profit_is_manual=body.profit_amount is not None,
                 recorded_by=user['id'], created_at=datetime.now(timezone.utc).isoformat())
        if collection.name == 'accounts_receivable':
            p['profit_allocation'] = 'invoice'
        remaining = round(d['remaining'] - body.amount, 2)
        query = {'id': debt_id, 'version': raw.get('version', {'$exists': False})}
        result = await collection.find_one_and_update(query,
            {'$set': {'paid_amount': round(d['paid_amount'] + body.amount, 2), 'remaining': remaining,
                      'status': 'paid' if remaining == 0 else 'partial', 'version': d['version'] + 1},
             '$push': {'payments': p}}, projection={'_id': 0}, return_document=ReturnDocument.AFTER)
        if not result:
            raise HTTPException(409, 'Tagihan berubah. Muat ulang sebelum membayar lagi')
        return hydrate(result)


async def update_debt(collection, debt_id, updates, user):
    async with financial_lock:
        raw = await collection.find_one({'id': debt_id}, {'_id': 0})
        if not raw:
            raise HTTPException(404, 'Tagihan tidak ditemukan')
        d = hydrate(raw)
        if d['status'] == 'void':
            raise HTTPException(409, 'Tagihan berstatus Void/Retur tidak dapat diubah')

        new_amount = round(float(updates['amount']), 2)
        paid_amount = round(float(d['paid_amount']), 2)
        if new_amount < paid_amount:
            raise HTTPException(
                422,
                f'Nominal tagihan tidak boleh lebih kecil dari total yang sudah dibayar ({paid_amount:g})',
            )

        new_issued_date = updates.get('issued_date') or d.get('issued_date') or today_iso()
        payment_dates = [p['payment_date'] for p in d.get('payments', []) if p.get('payment_date')]
        if payment_dates and new_issued_date > min(payment_dates):
            raise HTTPException(
                422,
                'Tanggal tagihan tidak boleh setelah tanggal pembayaran yang sudah tercatat',
            )

        remaining = round(new_amount - paid_amount, 2)
        new_status = 'paid' if remaining == 0 else ('partial' if paid_amount > 0 else 'unpaid')
        fields = {
            **updates,
            'amount': new_amount,
            'issued_date': new_issued_date,
            'remaining': remaining,
            'status': new_status,
            'version': d['version'] + 1,
            'updated_by': user['id'],
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        query = {'id': debt_id, 'version': raw.get('version', {'$exists': False})}
        result = await collection.find_one_and_update(
            query,
            {'$set': fields},
            projection={'_id': 0},
            return_document=ReturnDocument.AFTER,
        )
        if not result:
            raise HTTPException(409, 'Tagihan berubah. Muat ulang sebelum menyimpan perubahan')
        return hydrate(result)


async def remaining_credit_profit(debt, transaction=None):
    """Recognize each invoice's saved profit before its capital, including fees."""
    tx = transaction
    if tx is None and debt.get('transaction_id'):
        tx = await db.transactions.find_one({'id': debt['transaction_id']}, {'_id': 0})
    if not tx:
        return None
    if tx.get('status', 'completed') != 'completed' or debt.get('status') == 'void':
        return n(0)
    payments = debt.get('payments', [])
    known_paid = sum((n(p.get('amount')) for p in payments), n(0))
    if n(debt.get('paid_amount')) > known_paid or any('profit_amount' not in p for p in payments):
        return n(0)
    if tx.get('import_source'):
        invoice_date = tx.get('date_key') or debt.get('issued_date', '')
        customer = tx.get('customer_name') or debt.get('customer_name', '')
        # Source receipts have no reliable invoice allocation; never repeat their profit.
        if customer and await db.excel_events.find_one({
            'kind': 'credit_payment', 'invoice_date': invoice_date,
            'customer': {'$regex': '^' + re.escape(customer) + '$', '$options': 'i'},
        }):
            return n(0)
    profit = await invoice_credit_profit(tx)
    # Excluded historical receipts still consume profit already recognized elsewhere.
    recognized = sum((max(n(0), n(p.get('profit_amount'))) for p in payments), n(0))
    remaining = max(n(0), profit - recognized)
    if remaining and await legacy_group_profit_already_recognized(debt, tx):
        return n(0)
    return remaining


async def invoice_credit_profit(transaction):
    details = await db.transaction_details.find({'transaction_id': transaction['id']}, {'_id': 0}).to_list(None)
    profit = n(0)
    for detail in details:
        saved = {**detail, **({'import_source': transaction['import_source']} if transaction.get('import_source') else {})}
        values = line_snapshot_values(saved, credit=True)
        profit += n(values['spreadsheet_profit']) + n(values['spreadsheet_fee'])
    if not details:
        profit = n(transaction.get('spreadsheet_profit', transaction.get('total_profit', 0))) + n(transaction.get('service_fee', 0))
    return profit


def _timestamp(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


async def legacy_group_profit_already_recognized(debt, transaction):
    customer = transaction.get('customer_name') or debt.get('customer_name', '')
    if not customer:
        return False
    group = await db.transactions.find({
        'payment_method': 'credit', 'date_key': transaction.get('date_key') or debt.get('issued_date'),
        'customer_name': {'$regex': '^' + re.escape(customer) + '$', '$options': 'i'},
    }, {'_id': 0}).to_list(None)
    siblings = {tx['id']: tx for tx in group if tx['id'] != transaction['id']}
    if not siblings:
        return False
    sold_at = _timestamp(transaction.get('date'))
    async for sibling in db.accounts_receivable.find({'transaction_id': {'$in': list(siblings)}, 'status': {'$ne': 'void'}}, {'_id': 0}):
        candidates = [p for p in sibling.get('payments', [])
                      if p.get('profit_is_manual') is False and not p.get('is_down_payment')
                      and p.get('profit_allocation') != 'invoice']
        if not candidates:
            continue
        own_profit = max(n(0), await invoice_credit_profit(siblings[sibling['transaction_id']]))
        for payment in candidates:
            recorded_at = _timestamp(payment.get('created_at'))
            if sold_at and recorded_at and sold_at > recorded_at:
                continue
            # W14 could recognize every older invoice's profit on one sibling receipt.
            if n(payment.get('profit_amount')) > own_profit:
                return True
    return False


async def migrate_returned_debts():
    ids = await db.transactions.distinct('id', {'status': 'returned'})
    if ids:
        await db.accounts_receivable.update_many({'transaction_id': {'$in': ids}, 'status': {'$ne': 'void'}},
                                                {'$set': {'status': 'void', 'remaining': 0, 'legacy_return_migrated': True}})
