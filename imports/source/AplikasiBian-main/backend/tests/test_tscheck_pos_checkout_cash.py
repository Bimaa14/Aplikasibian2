"""POS checkout tunai: creates transaction with INV-YYMMDD-XXXX, decrements stock."""

import uuid

from tests.conftest import api_url


def test_checkout_cash_creates_invoice_and_decrements_stock(admin_client):
    sku = f"TSCHECK-{uuid.uuid4().hex[:6]}"
    prod = admin_client.post(
        "/products",
        json={
            "type": "barang",
            "sku": sku,
            "name": f"tscheck-cash-product-{sku}",
            "brand": "TestBrand",
            "size": "1x",
            "stock": 10,
            "cost_price": 5000,
            "selling_price": 10000,
            "service_fee": 0,
        },
    )
    assert prod.status_code == 201, f"product create failed: {prod.text[:200]}"
    product_id = prod.json()["id"]

    tx = admin_client.post(
        "/transactions",
        json={"items": [{"product_id": product_id, "qty": 3}], "payment_method": "cash", "customer_id": None, "due_date": None},
    )
    assert tx.status_code == 201, f"checkout failed: {tx.text[:200]}"
    body = tx.json()
    assert body["invoice_number"].startswith("INV-"), body["invoice_number"]
    parts = body["invoice_number"].split("-")
    assert len(parts) == 3 and len(parts[1]) == 6 and len(parts[2]) == 4, body["invoice_number"]
    assert body["total_amount"] == 30000
    assert body["status"] == "completed"

    prod_after = admin_client.get(f"/products/{product_id}")
    assert prod_after.status_code == 200
    assert prod_after.json()["stock"] == 7, f"stock did not decrement: {prod_after.json()}"
