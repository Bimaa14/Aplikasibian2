"""CRUD data master: Produk, Pelanggan, Distributor, Pengeluaran; and tandai lunas piutang/hutang."""

import uuid


def test_product_crud(admin_client):
    sku = f"TSCHECK-{uuid.uuid4().hex[:6]}"
    created = admin_client.post(
        "/products",
        json={
            "type": "barang",
            "sku": sku,
            "name": f"tscheck-product-{sku}",
            "brand": "B",
            "size": "S",
            "stock": 2,
            "cost_price": 100,
            "selling_price": 200,
            "service_fee": 0,
        },
    )
    assert created.status_code == 201, created.text[:200]
    pid = created.json()["id"]

    updated = admin_client.put(f"/products/{pid}", json={"name": f"tscheck-product-{sku}-updated", "stock": 9})
    assert updated.status_code == 200, updated.text[:200]
    assert updated.json()["name"].endswith("-updated")
    assert updated.json()["stock"] == 9

    deleted = admin_client.delete(f"/products/{pid}")
    assert deleted.status_code == 200
    gone = admin_client.get(f"/products/{pid}")
    assert gone.status_code == 404


def test_customer_and_supplier_crud(admin_client):
    cname = f"tscheck-customer-{uuid.uuid4().hex[:6]}"
    customer = admin_client.post("/customers", json={"name": cname, "phone": "0811", "address": "Jl. Test"})
    assert customer.status_code == 201, customer.text[:200]
    cid = customer.json()["id"]
    c_update = admin_client.put(f"/customers/{cid}", json={"name": cname + "-edit", "phone": "0822", "address": ""})
    assert c_update.status_code == 200
    assert c_update.json()["name"] == cname + "-edit"
    c_delete = admin_client.delete(f"/customers/{cid}")
    assert c_delete.status_code == 200

    sname = f"tscheck-supplier-{uuid.uuid4().hex[:6]}"
    supplier = admin_client.post("/suppliers", json={"name": sname, "phone": "0833", "address": "Jl. Test 2"})
    assert supplier.status_code == 201, supplier.text[:200]
    sid = supplier.json()["id"]
    s_update = admin_client.put(f"/suppliers/{sid}", json={"name": sname + "-edit", "phone": "0844", "address": ""})
    assert s_update.status_code == 200
    assert s_update.json()["name"] == sname + "-edit"
    s_delete = admin_client.delete(f"/suppliers/{sid}")
    assert s_delete.status_code == 200


def test_expense_create_and_appears_in_list(admin_client):
    desc = f"tscheck-expense-{uuid.uuid4().hex[:6]}"
    created = admin_client.post("/expenses", json={"amount": 12345, "category": "Operasional", "description": desc})
    assert created.status_code == 201, created.text[:200]
    listing = admin_client.get("/expenses")
    assert listing.status_code == 200
    match = [e for e in listing.json() if e["description"] == desc]
    assert len(match) == 1, f"expense not found in list: {desc}"
    assert match[0]["amount"] == 12345


def test_mark_receivable_and_payable_paid(admin_client):
    # create a credit transaction to get a real receivable row
    sku = f"TSCHECK-{uuid.uuid4().hex[:6]}"
    prod = admin_client.post(
        "/products",
        json={"type": "barang", "sku": sku, "name": f"tscheck-payrx-{sku}", "brand": "B", "size": "S", "stock": 5, "cost_price": 100, "selling_price": 1000, "service_fee": 0},
    )
    assert prod.status_code == 201
    product_id = prod.json()["id"]
    customer = admin_client.post("/customers", json={"name": f"tscheck-customer-{uuid.uuid4().hex[:6]}", "phone": "", "address": ""})
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    tx = admin_client.post(
        "/transactions",
        json={"items": [{"product_id": product_id, "qty": 1}], "payment_method": "credit", "customer_id": customer_id, "due_date": "2026-12-15"},
    )
    assert tx.status_code == 201
    receivables = admin_client.get("/receivables").json()
    rx_row = next(r for r in receivables if r["transaction_id"] == tx.json()["id"])
    pay_rx = admin_client.post(f"/receivables/{rx_row['id']}/pay")
    assert pay_rx.status_code == 200, pay_rx.text[:200]
    assert pay_rx.json()["status"] == "paid"

    # payable: create then mark paid
    supplier = admin_client.post("/suppliers", json={"name": f"tscheck-supplier-{uuid.uuid4().hex[:6]}", "phone": "", "address": ""})
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]
    invoice = f"tscheck-po-{uuid.uuid4().hex[:6]}"
    payable = admin_client.post("/payables", json={"supplier_id": supplier_id, "invoice_number": invoice, "amount": 50000, "due_date": "2026-12-20"})
    assert payable.status_code == 201, payable.text[:200]
    pay_px = admin_client.post(f"/payables/{payable.json()['id']}/pay")
    assert pay_px.status_code == 200
    assert pay_px.json()["status"] == "paid"
