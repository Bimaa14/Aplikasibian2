"""Tests for product 'owner' (pemilik) feature: Barang Bian vs Barang Ibu (Mamah Bian).

Covers:
- POST /api/products with owner='ibu' persists owner
- GET /api/products?owner=ibu filters correctly
- GET /api/products still returns all products (including owner=None legacy)
- POST /api/transactions -> details[].owner reflects product owner
- Cleanup created test products (transactions cannot be deleted)
"""
import os
import uuid

import httpx
import pytest

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API_URL = f"{BACKEND_URL}/api"


@pytest.fixture(scope="module")
def admin():
    # Session cookie is Secure; over http localhost httpx would drop it. Manually copy it.
    with httpx.Client(base_url=API_URL, timeout=30.0) as c:
        r = c.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200, f"admin login failed: {r.text[:200]}"
        sc = r.headers.get("set-cookie", "")
        token = sc.split("bengkel_session=", 1)[1].split(";", 1)[0]
        c.headers["Cookie"] = f"bengkel_session={token}"
        yield c


def _mk_sku(tag: str) -> str:
    return f"TEST-{tag}-{uuid.uuid4().hex[:6].upper()}"


def test_create_product_owner_ibu_persists(admin):
    sku = _mk_sku("IBU")
    payload = {
        "type": "barang",
        "sku": sku,
        "name": "TEST Ibu Product",
        "owner": "ibu",
        "stock": 10,
        "cost_price": 1000,
        "selling_price": 1500,
    }
    r = admin.post("/products", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["owner"] == "ibu"
    assert data["sku"] == sku
    pid = data["id"]

    # GET verifies persistence
    r2 = admin.get(f"/products/{pid}")
    assert r2.status_code == 200
    assert r2.json()["owner"] == "ibu"

    # cleanup
    admin.delete(f"/products/{pid}")


def test_create_product_owner_bian_default(admin):
    sku = _mk_sku("BIAN")
    r = admin.post("/products", json={
        "type": "barang", "sku": sku, "name": "TEST Bian Default",
        "stock": 5, "cost_price": 100, "selling_price": 200,
    })
    assert r.status_code == 201, r.text
    assert r.json()["owner"] == "bian"
    admin.delete(f"/products/{r.json()['id']}")


def test_owner_filter_narrows_list(admin):
    # Create one bian + one ibu tagged product
    sku_bian = _mk_sku("BIAN")
    sku_ibu = _mk_sku("IBU")
    p_bian = admin.post("/products", json={
        "type": "barang", "sku": sku_bian, "name": "TEST Bian Filter",
        "owner": "bian", "stock": 1, "cost_price": 100, "selling_price": 200,
    }).json()
    p_ibu = admin.post("/products", json={
        "type": "barang", "sku": sku_ibu, "name": "TEST Ibu Filter",
        "owner": "ibu", "stock": 1, "cost_price": 100, "selling_price": 200,
    }).json()

    try:
        # owner=ibu filter
        r = admin.get("/products", params={"owner": "ibu"})
        assert r.status_code == 200
        rows = r.json()
        owners = {row["owner"] for row in rows}
        assert owners == {"ibu"}, f"expected only ibu, got {owners}"
        assert any(row["id"] == p_ibu["id"] for row in rows)
        assert not any(row["id"] == p_bian["id"] for row in rows)

        # owner=bian filter
        r = admin.get("/products", params={"owner": "bian"})
        assert r.status_code == 200
        owners = {row["owner"] for row in r.json()}
        assert owners == {"bian"}

        # No filter: returns all (legacy products with owner=None must not error)
        r = admin.get("/products")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 400, f"expected 400+ existing products, got {len(rows)}"
        # includes owner=None legacy
        assert any(row.get("owner") is None for row in rows), "no legacy owner=None products found"
    finally:
        admin.delete(f"/products/{p_bian['id']}")
        admin.delete(f"/products/{p_ibu['id']}")


def test_update_product_owner_persists(admin):
    sku = _mk_sku("UPD")
    p = admin.post("/products", json={
        "type": "barang", "sku": sku, "name": "TEST Update Owner",
        "owner": "bian", "stock": 1, "cost_price": 100, "selling_price": 200,
    }).json()
    try:
        r = admin.put(f"/products/{p['id']}", json={"owner": "ibu"})
        assert r.status_code == 200, r.text
        assert r.json()["owner"] == "ibu"
        # GET verify
        assert admin.get(f"/products/{p['id']}").json()["owner"] == "ibu"
    finally:
        admin.delete(f"/products/{p['id']}")


def test_transaction_detail_carries_owner(admin):
    sku = _mk_sku("TX")
    p = admin.post("/products", json={
        "type": "barang", "sku": sku, "name": "TEST Tx Owner",
        "owner": "ibu", "stock": 5, "cost_price": 500, "selling_price": 1000,
    }).json()
    try:
        r = admin.post("/transactions", json={
            "items": [{"product_id": p["id"], "qty": 1}],
            "payment_method": "cash",
        })
        assert r.status_code == 201, r.text
        tx = r.json()
        tx_id = tx["id"]
        # response detail
        assert any(d.get("owner") == "ibu" for d in tx.get("details", [])), tx

        # GET verifies detail persistence
        r2 = admin.get(f"/transactions/{tx_id}")
        assert r2.status_code == 200
        details = r2.json()["details"]
        assert any(d.get("owner") == "ibu" for d in details), details
    finally:
        # cannot delete tx, but delete product to keep master clean
        admin.delete(f"/products/{p['id']}")
