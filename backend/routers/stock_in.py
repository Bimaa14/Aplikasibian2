"""Stok masuk: catat barang masuk dari distributor → stok naik, modal diperbarui, hutang dibuat."""

from datetime import date, datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from lib.auth import require_user
from lib.db import db
from lib.dates import today_iso
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

    products = await db.products.find({"id": {"$in": list(merged)}}, {"_id": 0}).to_list(500)
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

    now = datetime.now(timezone.utc)
    date_key = today_iso()
    yymmdd = date_key.replace("-", "")[2:]
    base_seq = await db.stock_in.count_documents({"date_key": date_key})

    record = StockIn(
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
    for attempt in range(5):
        record.reference = f"SM-{yymmdd}-{base_seq + 1 + attempt:04d}"
        doc["reference"] = record.reference
        try:
            await db.stock_in.insert_one(doc)
            break
        except DuplicateKeyError:
            continue
    else:
        raise HTTPException(status_code=500, detail="Gagal membuat nomor referensi stok masuk")

    # stok naik + modal (cost_price) produk diperbarui ke harga beli terbaru
    for item in items:
        await db.products.update_one(
            {"id": item.product_id},
            {"$inc": {"stock": item.qty}, "$set": {"cost_price": item.cost_price}},
        )

    # hutang distributor otomatis
    payable = AccountsPayable(
        supplier_id=body.supplier_id,
        supplier_name=supplier["name"],
        invoice_number=record.invoice_number,
        amount=total_amount,
        remaining=total_amount,
        due_date=due,
    )
    await db.accounts_payable.insert_one(payable.model_dump())
    await db.stock_in.update_one({"id": record.id}, {"$set": {"payable_id": payable.id}})
    record.payable_id = payable.id

    return record
