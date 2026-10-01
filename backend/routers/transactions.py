"""POS transactions: checkout (with stock + credit rule), history, detail, return (retur)."""

import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from lib.debts import financial_lock, hydrate
from lib.financial_operations import FinancialOperation
from lib.excel_rules import line_values
from lib.pricing import cents, allocate_discount
from pymongo.errors import DuplicateKeyError

from lib.auth import require_user
from lib.db import db
from lib.dates import today_iso
from models.finance import AccountsReceivable
from models.transaction import Transaction, TransactionCreate, TransactionDetail

router = APIRouter(prefix="/transactions", tags=["transactions"], dependencies=[Depends(require_user)])


def _norm_dt(dt: datetime) -> datetime:
    """Motor returns naive datetimes — normalise to aware UTC so Pydantic/JS handle them."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _app_tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("APP_TZ", "UTC"))


async def _load_details(tx_ids: List[str]) -> dict:
    if not tx_ids:
        return {}
    docs = await db.transaction_details.find(
        {"transaction_id": {"$in": tx_ids}}, {"_id": 0}
    ).to_list(10000)
    grouped: dict = {}
    for d in docs:
        grouped.setdefault(d["transaction_id"], []).append(d)
    return grouped


def _to_model(doc: dict, details: Optional[List[dict]] = None) -> Transaction:
    doc = dict(doc)
    doc.pop("details", None)
    doc["date"] = _norm_dt(doc["date"])
    return Transaction(**doc, details=[TransactionDetail(**d) for d in (details or [])])


@router.get("", response_model=List[Transaction])
async def list_transactions(search: Optional[str] = None, status: Optional[str] = None):
    query: dict = {}
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        query["$or"] = [{"invoice_number": rx}, {"customer_name": rx}, {"vehicle_plate": rx}]
    if status in ("completed", "returned"):
        query["status"] = status
    docs = await db.transactions.find(query, {"_id": 0}).sort("date", -1).to_list(100)
    grouped = await _load_details([d["id"] for d in docs])
    return [_to_model(d, grouped.get(d["id"], [])) for d in docs]


@router.get("/{transaction_id}", response_model=Transaction)
async def get_transaction(transaction_id: str):
    doc = await db.transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    grouped = await _load_details([transaction_id])
    return _to_model(doc, grouped.get(transaction_id, []))


@router.post("", response_model=Transaction, status_code=201)
async def create_transaction(body: TransactionCreate, user: dict = Depends(require_user)):
    async with financial_lock:
        async with FinancialOperation("checkout") as operation:
            return await _create_transaction(body, user, operation)


async def _create_transaction(body: TransactionCreate, user: dict, operation: FinancialOperation):
    request_key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"checkout:{user['id']}:{body.request_id}")) if body.request_id else None
    payload = body.model_dump(mode="json", exclude={"request_id"})
    if request_key:
        previous = await db.checkout_requests.find_one({"id": request_key})
        if previous:
            stored_payload = TransactionCreate(**previous["payload"]).model_dump(mode="json", exclude={"request_id"})
            if stored_payload != payload:
                raise HTTPException(409, "ID checkout sudah dipakai untuk transaksi berbeda")
            return await get_transaction(previous["transaction_id"])
    # merge duplicate products in the cart
    merged: dict = {}
    surcharges: dict = {}
    item_discounts: dict = {}
    for item in body.items:
        if item.product_id in surcharges and surcharges[item.product_id] != item.credit_surcharge:
            raise HTTPException(422, "Tambahan harga item yang sama harus sama")
        surcharges[item.product_id] = item.credit_surcharge
        merged[item.product_id] = merged.get(item.product_id, 0) + item.qty
        item_discounts[item.product_id] = item_discounts.get(item.product_id, 0) + cents(item.discount_amount)

    product_docs = await db.products.find({"id": {"$in": list(merged)}, "active": {"$ne": False}}, {"_id": 0}).to_list(1000)
    by_id = {p["id"]: p for p in product_docs}
    missing = [pid for pid in merged if pid not in by_id]
    if missing:
        raise HTTPException(status_code=400, detail="Ada produk yang tidak ditemukan")

    customer_name = None
    customer_address = ""
    if body.customer_id:
        customer = await db.customers.find_one({"id": body.customer_id}, {"_id": 0})
        if not customer:
            raise HTTPException(status_code=400, detail="Pelanggan tidak ditemukan")
        customer_name = customer["name"]
        customer_address = customer.get("address", "")

    gross = [cents(by_id[pid]["selling_price"] + surcharges[pid]) * qty for pid, qty in merged.items()]
    remaining = [amount - item_discounts[pid] for pid, amount in zip(merged, gross)]
    if any(amount < 0 for amount in remaining):
        raise HTTPException(422, "Potongan item tidak boleh melebihi jumlah item")
    try:
        discounts = {pid: item_discounts[pid] + extra for pid, extra in
                     zip(merged, allocate_discount(remaining, cents(body.discount_total)))}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    details: List[TransactionDetail] = []
    total_amount = total_cost = service_fee = total_profit = barang_amount = jasa_amount = 0.0
    for pid, qty in merged.items():
        p = by_id[pid]
        if p["type"] == "barang" and p.get("stock", 0) < qty:
            raise HTTPException(status_code=400, detail=f"Stok {p['name']} tidak cukup (sisa {p.get('stock', 0)})")
        price = cents(p["selling_price"] + surcharges[pid]) / 100
        cost = p.get("cost_price", 0) if p["type"] == "barang" else 0
        discount = discounts[pid] / 100
        subtotal = (cents(price) * qty - discounts[pid]) / 100
        values = line_values({**p, "selling_price": price}, qty, body.payment_method == 'credit', discount)
        line_fee = values['spreadsheet_fee']
        fee = line_fee / qty
        profit = subtotal - cost * qty - line_fee
        details.append(
            TransactionDetail(
                **values,
                tax=p.get("tax"),
                base_price=p["selling_price"],
                credit_surcharge=surcharges[pid],
                discount_amount=discount,
                transaction_id="",  # filled after the transaction id exists
                product_id=pid,
                product_name=p["name"],
                product_sku=p.get("sku"),
                product_size=p.get("size", ""),
                product_brand=p.get("brand", ""),
                product_type=p["type"],
                owner=p.get("owner"),
                qty=qty,
                price=price,
                cost_price=cost,
                service_fee=fee,
                subtotal=subtotal,
            )
        )
        total_amount += subtotal
        if p["type"] == "barang":
            barang_amount += subtotal
            total_cost += cost * qty
        else:
            jasa_amount += subtotal
        service_fee += line_fee
        total_profit += profit

    total_amount = round(total_amount, 2)
    if body.payment_method == "credit" and total_amount <= 0:
        raise HTTPException(422, "Transaksi tempo harus memiliki total lebih dari nol")
    if body.cash_received is not None and body.cash_received < round(total_amount, 2):
        raise HTTPException(422, "Uang diterima kurang dari total transaksi")

    now = datetime.now(timezone.utc)
    date_key = today_iso()  # server-side "today" in APP_TZ
    tx = Transaction(
        invoice_number="",
        date=now,
        date_key=date_key,
        customer_id=body.customer_id,
        customer_name=customer_name,
        customer_address=customer_address,
        payment_method=body.payment_method,
        total_amount=total_amount,
        discount_total=sum(discounts.values()) / 100,
        cash_received=body.cash_received,
        change_amount=max(0, round(body.cash_received - total_amount, 2)) if body.cash_received is not None else None,
        barang_amount=barang_amount,
        jasa_amount=jasa_amount,
        total_cost=total_cost,
        service_fee=service_fee,
        total_profit=total_profit,
        spreadsheet_profit=sum(d.spreadsheet_profit for d in details),
        due_date=body.due_date.isoformat() if body.due_date else None,
        vehicle_plate=(body.vehicle_plate or "").strip().upper() or None,
    )

    # sequential invoice number per day, retry on the unique index
    yymmdd = date_key.replace("-", "")[2:]
    base_seq = await db.transactions.count_documents({"date_key": date_key})
    tx_doc = tx.model_dump(exclude={"details"})
    tx_doc["recorded_by"] = user["id"]
    for attempt in range(5):
        tx.invoice_number = f"INV-{yymmdd}-{base_seq + 1 + attempt:04d}"
        tx_doc["invoice_number"] = tx.invoice_number
        try:
            await operation.insert("transactions", tx_doc)
            break
        except DuplicateKeyError:
            continue
    else:
        raise HTTPException(status_code=500, detail="Gagal membuat nomor invoice")

    tx_details = []
    for d in details:
        d.transaction_id = tx.id
        tx_details.append(d.model_dump())
    for detail in tx_details:
        await operation.insert("transaction_details", detail)

    for pid, qty in merged.items():
        if by_id[pid]["type"] == "barang":
            await operation.update("products", pid, {"$inc": {"stock": -qty}},
                                   condition={"stock": {"$gte": qty}, "type": "barang"})

    # kredit (tempo) → otomatis buat piutang
    if body.payment_method == "credit":
        receivable = AccountsReceivable(
            transaction_id=tx.id,
            invoice_number=tx.invoice_number,
            customer_id=body.customer_id or "",
            customer_name=customer_name,
            amount=total_amount,
            remaining=total_amount,
            due_date=body.due_date.isoformat() if body.due_date else today_iso(),
        )
        await operation.insert("accounts_receivable", receivable.model_dump())

    if request_key:
        await operation.insert("checkout_requests", {
            "id": request_key, "payload": payload, "transaction_id": tx.id,
        })
    return _to_model(tx_doc, tx_details)


class ReturnInput(BaseModel):
    reason: str = Field(default='Retur transaksi', min_length=3, max_length=500)
    refund_confirmed: bool = False


@router.post("/{transaction_id}/return", response_model=Transaction)
async def return_transaction(transaction_id: str, body: Optional[ReturnInput] = None):
    async with financial_lock:
        async with FinancialOperation("return") as operation:
            return await _return_transaction(transaction_id, body or ReturnInput(), operation)


async def _return_transaction(transaction_id: str, body: ReturnInput, operation: FinancialOperation):
    doc = await db.transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    if doc.get("status") == "returned":
        raise HTTPException(status_code=400, detail="Transaksi sudah diretur sebelumnya")

    if doc.get('import_source'):
        raise HTTPException(409, 'Riwayat impor memakai saldo stok akhir Excel. Retur historis perlu rekonsiliasi, bukan menambah stok otomatis.')
    debt = await db.accounts_receivable.find_one({'transaction_id': transaction_id}, {'_id': 0})
    refund = hydrate(debt)['paid_amount'] if debt else (doc['total_amount'] if doc['payment_method'] != 'credit' else 0)
    if refund > 0 and not body.refund_confirmed:
        raise HTTPException(422, f'Konfirmasikan pengembalian pembayaran Rp {refund:,.0f} kepada pelanggan sebelum retur')

    details = await db.transaction_details.find({"transaction_id": transaction_id}, {"_id": 0}).to_list(1000)
    quantities = {}
    for d in details:
        if d["product_type"] == "barang":
            quantities[d["product_id"]] = quantities.get(d["product_id"], 0) + d["qty"]
    for product_id, qty in quantities.items():
        await operation.update("products", product_id, {"$inc": {"stock": qty}})

    await operation.update(
        "transactions", transaction_id,
        {"$set": {"status": "returned", "returned_at": datetime.now(timezone.utc), "return_date": today_iso(), "return_reason": body.reason, "refund_amount": refund}},
        condition={"status": "completed"},
    )
    # piutang dari transaksi yang diretur dianggap hangus
    async for receivable in db.accounts_receivable.find({"transaction_id": transaction_id}):
        await operation.update(
            "accounts_receivable", receivable["id"],
            {"$set": {"status": "void", "remaining": 0, "return_date": today_iso(), "refund_amount": refund}, "$inc": {"version": 1}},
        )

    doc["status"] = "returned"
    doc.update(return_date=today_iso(), return_reason=body.reason, refund_amount=refund)
    return _to_model(doc, details)
