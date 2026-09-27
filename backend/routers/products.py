"""Products (barang & jasa) CRUD."""

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import require_admin, require_user
from lib.db import db
from models.product import Product, ProductCreate, ProductUpdate

# Baca produk: semua user login (kasir butuh untuk POS). Tulis/hapus: admin saja.
router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(require_user)])


@router.get("", response_model=List[Product])
async def list_products(search: Optional[str] = None, type: Optional[str] = None, owner: Optional[str] = None):
    query: dict = {}
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        query["$or"] = [{"name": rx}, {"sku": rx}, {"brand": rx}]
    if type in ("barang", "jasa"):
        query["type"] = type
    if owner in ("bian", "ibu"):
        query["owner"] = owner
    docs = await db.products.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    return [Product(**d) for d in docs]


@router.post("", response_model=Product, status_code=201, dependencies=[Depends(require_admin)])
async def create_product(body: ProductCreate):
    product = Product(**body.model_dump())
    await db.products.insert_one(product.model_dump())
    return product


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: str):
    doc = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    return Product(**doc)


@router.put("/{product_id}", response_model=Product, dependencies=[Depends(require_admin)])
async def update_product(product_id: str, body: ProductUpdate):
    doc = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    doc.pop("details", None)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    doc.update(updates)
    product = Product(**doc)
    await db.products.replace_one({"id": product_id}, product.model_dump())
    return product


@router.delete("/{product_id}", dependencies=[Depends(require_admin)])
async def delete_product(product_id: str):
    result = await db.products.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    return {"ok": True}
