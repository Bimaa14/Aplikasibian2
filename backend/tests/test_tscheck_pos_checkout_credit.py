"""POS checkout tempo (credit): requires customer + due_date, auto-creates a receivable."""

import uuid


def test_checkout_credit_requires_customer_and_due_date(admin_client):
    sku = f"TSCHECK-{uuid.uuid4().hex[:6]}"
    prod = admin_client.post(
        "/products",
        json={
            "type": "barang",
            "sku": sku,
            "name": f"tscheck-credit-product-{sku}",
            "brand": "TestBrand",
            "size": "1x",
            "stock": 10,
            "cost_price": 5000,
            "selling_price": 20000,
            "service_fee": 0,
        },
    )
    assert prod.status_code == 201, prod.text[:200]
    product_id = prod.json()["id"]

    customer = admin_client.post("/customers", json={"name": f"tscheck-customer-{uuid.uuid4().hex[:6]}", "phone": "0800", "address": ""})
    assert customer.status_code == 201, customer.text[:200]
    customer_id = customer.json()["id"]

    # missing customer + due_date -> rejected (422 validation)
    rejected = admin_client.post(
        "/transactions",
        json={"items": [{"product_id": product_id, "qty": 1}], "payment_method": "credit", "customer_id": None, "due_date": None},
    )
    assert rejected.status_code == 422, f"expected validation rejection, got {rejected.status_code}: {rejected.text[:200]}"

    tx = admin_client.post(
        "/transactions",
        json={
            "items": [{"product_id": product_id, "qty": 1}],
            "payment_method": "credit",
            "customer_id": customer_id,
            "due_date": "2026-12-01",
        },
    )
    assert tx.status_code == 201, tx.text[:200]
    tx_body = tx.json()
    assert tx_body["payment_method"] == "credit"
    assert tx_body["total_amount"] == 20000

    receivables = admin_client.get("/receivables")
    assert receivables.status_code == 200
    match = [r for r in receivables.json() if r["transaction_id"] == tx_body["id"]]
    assert len(match) == 1, f"expected receivable row for tx, got: {match}"
    assert match[0]["status"] == "unpaid"
    assert match[0]["amount"] == 20000
    assert match[0]["customer_name"] == customer.json()["name"]
