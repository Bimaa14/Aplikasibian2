"""Debt writes are atomic, including the payment audit trail and return refund."""
import uuid
from fastapi import APIRouter, HTTPException, Query
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from accounting_models import DebtCreate, PaymentCreate, ReturnCreate, EntryCreate, Debt, enrich_debt, timestamp, today


def accounting_router(db):
    router = APIRouter(prefix='/api')

    @router.post('/debts', response_model=Debt, status_code=201)
    async def create_debt(body: DebtCreate):
        doc = body.model_dump(mode='json')
        doc.update(id=str(uuid.uuid4()), paid_amount=0, remaining=body.total,
                   status='unpaid', payments=[], created_at=timestamp(), version=0,
                   reference_key=body.reference.casefold(), refund_amount=0)
        try:
            await db.accounting_debts.insert_one(doc.copy())
        except DuplicateKeyError:
            raise HTTPException(409, 'Nomor invoice sudah digunakan pada jenis tagihan ini.')
        return enrich_debt(doc)

    @router.get('/debts', response_model=list[Debt])
    async def list_debts(kind: str = Query(pattern='^(receivable|payable)$')):
        return [enrich_debt(d) async for d in db.accounting_debts.find({'kind': kind}, {'_id': 0}).sort('created_at', -1)]

    @router.get('/debts/{debt_id}', response_model=Debt)
    async def get_debt(debt_id: str):
        doc = await db.accounting_debts.find_one({'id': debt_id}, {'_id': 0})
        if not doc:
            raise HTTPException(404, 'Tagihan tidak ditemukan.')
        return enrich_debt(doc)

    @router.post('/debts/{debt_id}/pay', response_model=Debt)
    async def pay_debt(debt_id: str, body: PaymentCreate):
        doc = await db.accounting_debts.find_one({'id': debt_id}, {'_id': 0})
        if not doc:
            raise HTTPException(404, 'Tagihan tidak ditemukan.')
        previous = next((p for p in doc['payments'] if p['request_id'] == body.request_id), None)
        if previous:
            if any(previous[k] != body.model_dump(mode='json')[k] for k in ('amount', 'method', 'note', 'payment_date')):
                raise HTTPException(409, 'ID pembayaran sudah digunakan untuk nominal atau detail berbeda.')
            return enrich_debt(doc)
        if doc['status'] not in ('unpaid', 'partial'):
            raise HTTPException(409, 'Tagihan sudah lunas atau dibatalkan.')
        if body.amount > doc['remaining']:
            raise HTTPException(422, 'Nominal pembayaran melebihi sisa tagihan.')
        if body.payment_date.isoformat() < doc['issued_date']:
            raise HTTPException(422, 'Tanggal pembayaran tidak boleh sebelum transaksi.')
        payment = body.model_dump(mode='json')
        payment.update(id=str(uuid.uuid4()), created_at=timestamp())
        remaining = doc['remaining'] - body.amount
        updated = await db.accounting_debts.find_one_and_update(
            {'id': debt_id, 'version': doc['version'], 'status': {'$in': ['unpaid', 'partial']}},
            {'$inc': {'paid_amount': body.amount, 'version': 1},
             '$set': {'remaining': remaining, 'status': 'paid' if remaining == 0 else 'partial'},
             '$push': {'payments': payment}},
            projection={'_id': 0}, return_document=ReturnDocument.AFTER)
        if not updated:
            latest = await db.accounting_debts.find_one({'id': debt_id}, {'_id': 0})
            match = next((p for p in latest['payments'] if p['request_id'] == body.request_id), None)
            if match and all(match[k] == payment[k] for k in ('amount', 'method', 'note', 'payment_date')):
                return enrich_debt(latest)
            raise HTTPException(409, 'Tagihan berubah. Muat ulang sebelum membayar lagi.')
        return enrich_debt(updated)

    @router.post('/debts/{debt_id}/return', response_model=Debt)
    async def return_debt(debt_id: str, body: ReturnCreate):
        doc = await db.accounting_debts.find_one({'id': debt_id}, {'_id': 0})
        if not doc:
            raise HTTPException(404, 'Tagihan tidak ditemukan.')
        if doc['kind'] != 'receivable':
            raise HTTPException(422, 'Retur kredit hanya tersedia untuk piutang pelanggan.')
        if doc['status'] == 'void':
            raise HTTPException(409, 'Transaksi ini sudah diretur.')
        if doc['paid_amount'] and not body.refund_confirmed:
            raise HTTPException(422, 'Konfirmasikan pengembalian seluruh pembayaran pelanggan sebelum retur.')
        if any(p['payment_date'] > today().isoformat() for p in doc['payments']):
            raise HTTPException(422, 'Tanggal retur harus setelah pembayaran terakhir.')
        result = await db.accounting_debts.find_one_and_update(
            {'id': debt_id, 'version': doc['version'], 'status': {'$ne': 'void'}},
            {'$set': {'status': 'void', 'remaining': 0, 'return_date': today().isoformat(),
                      'return_reason': body.reason, 'refund_amount': doc['paid_amount']}, '$inc': {'version': 1}},
            projection={'_id': 0}, return_document=ReturnDocument.AFTER)
        if not result:
            raise HTTPException(409, 'Tagihan berubah. Periksa pembayaran terbaru sebelum retur.')
        return enrich_debt(result)

    @router.post('/entries', status_code=201)
    async def create_entry(body: EntryCreate):
        doc = body.model_dump(mode='json')
        previous = await db.accounting_entries.find_one({'request_id': body.request_id}, {'_id': 0})
        if previous:
            if any(previous[k] != v for k, v in doc.items()):
                raise HTTPException(409, 'ID pencatatan sudah digunakan untuk detail berbeda.')
            return previous
        doc.update(id=str(uuid.uuid4()), created_at=timestamp())
        try:
            await db.accounting_entries.insert_one(doc.copy())
        except DuplicateKeyError:
            raise HTTPException(409, 'Pencatatan sedang diproses. Muat ulang untuk memeriksa hasil.')
        return doc

    @router.get('/entries')
    async def entries():
        return await db.accounting_entries.find({}, {'_id': 0}).sort('entry_date', -1).to_list(None)

    return router