"""Stok masuk: catat barang masuk dari distributor → stok naik, modal diperbarui, hutang dibuat."""

from datetime import date, datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from lib.auth import require_user
from lib.db import db
from lib.dates import today_iso
from lib.financial_operations import FinancialOperation, financial_lock
from models.finance import AccountsPayable
from models.stock_in import StockIn, StockInCreate, StockInItem

router = APIRouter(prefix="/stock-in", tags=["stock-in"], dependencies=[Depends(require_user)])


def _norm_dt(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("", response_model=List[StockIn])
async def list_stock_in():
    docs = await db.stock_in.find({}, {"_id": 0}).sort("date", -1).to_list(200)
    out = []
    for d in docs:
        d = dict(d)
        d["date"] = _norm_dt(d["date"])
        out.append(StockIn(**d))
    return out


@router.post("", response_model=StockIn, status_code=201)
async def create_stock_in(body: StockInCreate):
    async with financial_lock:
        async with FinancialOperation("stock_in") as operation:
            return await _create_stock_in(body, operation)


async def _create_stock_in(body: StockInCreate, operation: FinancialOperation):
    supplier = await db.suppliers.find_one({"id": body.supplier_id}, {"_id": 0})
    if not supplier:
        raise HTTPException(status_code=404, detail="Distributor tidak ditemukan")
    try:
        due = date.fromisoformat(body.due_date).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Format jatuh tempo harus YYYY-MM-DD")

    # gabungkan item duplikat (product terakhir menentukan modal)
    merged: dict = {}
    for item in body.items:
        prev = merged.get(item.product_id)
        merged[item.product_id] = {
            "qty": (prev["qty"] if prev else 0) + item.qty,
            "cost_price": item.cost_price,
        }

    products = await db.products.find({"id": {"$in": list(merged)}, "active": {"$ne": False}}, {"_id": 0}).to_list(500)
    by_id = {p["id"]: p for p in products}
    if len(by_id) != len(merged):
        raise HTTPException(status_code=400, detail="Ada produk yang tidak ditemukan")
    for pid, p in by_id.items():
        if p["type"] != "barang":
            raise HTTPException(status_code=400, detail=f"{p['name']} adalah jasa — tidak punya stok")

    items: List[StockInItem] = []
    total_amount = 0.0
    for pid, info in merged.items():
        p = by_id[pid]
        qty, cost = info["qty"], info["cost_price"]
        subtotal = qty * cost
        total_amount += subtotal
        stock_before = int(p.get("stock", 0))
        items.append(
            StockInItem(
                owner=p.get("owner"), tax=p.get("tax"), category=p.get("category"),
                product_id=pid,
                product_name=p["name"],
                sku=p["sku"],
                qty=qty,
                cost_price=cost,
                subtotal=subtotal,
                stock_before=stock_before,
                stock_after=stock_before + qty,
            )
        )

    if total_amount <= 0:
        raise HTTPException(422, "Total stok masuk harus lebih dari nol untuk membuat hutang")

    now = datetime.now(timezone.utc)
    date_key = today_iso()
    yymmdd = date_key.replace("-", "")[2:]
    base_seq = await db.stock_in.count_documents({"date_key": date_key})

    record = StockIn(
        invoice_date=body.invoice_date.isoformat() if body.invoice_date else date_key,
        reference="",
        date=now,
        date_key=date_key,
        supplier_id=body.supplier_id,
        supplier_name=supplier["name"],
        invoice_number=body.invoice_number.strip(),
        due_date=due,
        total_amount=total_amount,
        note=body.note.strip(),
        items=items,
    )
    doc = record.model_dump()
    payable = AccountsPayable(
        supplier_id=body.supplier_id, supplier_name=supplier["name"],
        invoice_number=record.invoice_number, amount=total_amount,
        remaining=total_amount, due_date=due,
    )
    record.payable_id = payable.id
    doc["payable_id"] = payable.id
    for attempt in range(5):
        record.reference = f"SM-{yymmdd}-{base_seq + 1 + attempt:04d}"
        doc["reference"] = record.reference
        try:
            await operation.insert("stock_in", doc)
            break
        except DuplicateKeyError:
            continue
    else:
        raise HTTPException(status_code=500, detail="Gagal membuat nomor referensi stok masuk")

    # stok naik + modal (cost_price) produk diperbarui ke harga beli terbaru
    for item in items:
        await operation.update(
            "products", item.product_id,
            {"$inc": {"stock": item.qty}, "$set": {"cost_price": item.cost_price}},
            condition={"type": "barang"},
        )

    # hutang distributor otomatis
    await operation.insert("accounts_payable", payable.model_dump())

    return record
