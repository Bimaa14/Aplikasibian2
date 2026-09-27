"""Retur: marking a completed transaction as returned restores stock and excludes it from dashboard revenue."""

import uuid


def test_return_restores_stock_and_excludes_from_dashboard(admin_client):
    sku = f"TSCHECK-{uuid.uuid4().hex[:6]}"
    prod = admin_client.post(
        "/products",
        json={
            "type": "barang",
            "sku": sku,
            "name": f"tscheck-retur-product-{sku}",
            "brand": "TestBrand",
            "size": "1x",
            "stock": 5,
            "cost_price": 1000,
            "selling_price": 5000,
            "service_fee": 0,
        },
    )
    assert prod.status_code == 201, prod.text[:200]
    product_id = prod.json()["id"]

    tx = admin_client.post(
        "/transactions",
        json={"items": [{"product_id": product_id, "qty": 2}], "payment_method": "cash", "customer_id": None, "due_date": None},
    )
    assert tx.status_code == 201, tx.text[:200]
    tx_id = tx.json()["id"]

    # stats_before still counts this tx as completed revenue
    stats_before = admin_client.get("/dashboard")
    assert stats_before.status_code == 200
    revenue_before = stats_before.json()["total_revenue"]

    ret = admin_client.post(f"/transactions/{tx_id}/return")
    assert ret.status_code == 200, ret.text[:200]
    assert ret.json()["status"] == "returned"

    prod_after = admin_client.get(f"/products/{product_id}")
    assert prod_after.status_code == 200
    assert prod_after.json()["stock"] == 5, f"stock not restored after return: {prod_after.json()}"

    # after return, dashboard revenue should drop by exactly this tx's amount (excluded from KPI)
    stats_after = admin_client.get("/dashboard")
    assert stats_after.status_code == 200
    revenue_after = stats_after.json()["total_revenue"]
    assert revenue_after == revenue_before - 10000, (
        f"returned transaction should be excluded from total_revenue: before={revenue_before} after={revenue_after}"
    )

    # returning again is rejected
    dup = admin_client.post(f"/transactions/{tx_id}/return")
    assert dup.status_code == 400, f"expected 400 re-returning, got {dup.status_code}"
