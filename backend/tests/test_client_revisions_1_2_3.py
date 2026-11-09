"""End-to-end tests for Client Revisions 1, 2, and 3:
1. POS Payment Mix (Tunai + Transfer) for direct Cash sales and Tempo down payments.
2. Debt Payment Tunai / Transfer / Mix + Kwitansi data integrity.
3. Data Reset / Zeroing ('NOLKAN') and Store re-sync.
"""
import uuid
import pytest
from lib.dates import today_iso
from tests.test_financial_safety import isolated, product, checkout, assert_clean


async def test_pos_mix_checkout_splits_cash_and_transfer_in_daily_report(isolated):
    db, api, user, _ = isolated
    user["role"] = "admin"
    pid = await product(db, stock=10, price=500000)

    # Validation: mix without matching cash_amount + transfer_amount fails
    bad = await api.post("/transactions", json=checkout(
        pid,
        payment_method="mix",
        cash_amount=200000,
        transfer_amount=200000,
        transfer_method="transfer_bca",
    ))
    assert bad.status_code == 422

    # Valid Mix checkout: Rp 300.000 Tunai + Rp 200.000 Transfer BCA = Rp 500.000
    res = await api.post("/transactions", json=checkout(
        pid,
        payment_method="mix",
        cash_received=500000,
        cash_amount=300000,
        transfer_amount=200000,
        transfer_method="transfer_bca",
    ))
    assert res.status_code == 201, res.text
    tx = res.json()
    assert tx["payment_method"] == "mix"
    assert tx["cash_amount"] == 300000
    assert tx["transfer_amount"] == 200000
    assert tx["transfer_method"] == "transfer_bca"
    assert tx["total_amount"] == 500000

    # Daily report should record 500,000 cash_sales, 200,000 transfer_payments (transfer_bca), and 300,000 net_cash
    daily = (await api.get("/books/daily", params={"date": today_iso()})).json()
    assert daily["cash_sales"] == 500000
    assert daily["non_cash_sales"] == 200000
    assert daily["transfer_payments"] == 200000
    assert daily["transfer_breakdown"]["transfer_bca"] == 200000
    assert daily["net_cash"] == 300000
    await assert_clean(db)


async def test_pos_credit_down_payment_mix_and_installment_mix(isolated):
    db, api, user, _ = isolated
    user["role"] = "admin"
    pid = await product(db, stock=10, price=600000)
    await db.customers.insert_one({"id": "cust-1", "name": "Budi Santoso", "phone": "08123", "address": "Majalaya"})

    # Credit checkout with Rp 200.000 Down Payment via Mix (Rp 80.000 Tunai + Rp 120.000 QRIS)
    res = await api.post("/transactions", json=checkout(
        pid,
        payment_method="credit",
        customer_id="cust-1",
        credit_term_days=14,
        down_payment_amount=200000,
        down_payment_method="mix",
        cash_amount=80000,
        transfer_amount=120000,
        transfer_method="qris",
    ))
    assert res.status_code == 201, res.text
    tx = res.json()
    assert tx["down_payment_amount"] == 200000
    assert tx["down_payment_method"] == "mix"
    assert tx["cash_amount"] == 80000
    assert tx["transfer_amount"] == 120000
    assert tx["transfer_method"] == "qris"

    recs = (await api.get("/receivables")).json()
    assert len(recs) == 1
    debt = recs[0]
    assert debt["remaining"] == 400000
    assert len(debt["payments"]) == 1
    dp = debt["payments"][0]
    assert dp["method"] == "mix"
    assert dp["cash_amount"] == 80000
    assert dp["transfer_amount"] == 120000
    assert dp["transfer_method"] == "qris"

    # Pay installment of Rp 250.000 via Mix (Rp 100.000 Tunai + Rp 150.000 Transfer BRI)
    pay_res = await api.post(f"/receivables/{debt['id']}/pay", json={
        "request_id": str(uuid.uuid4()),
        "amount": 250000,
        "payment_date": today_iso(),
        "method": "mix",
        "cash_amount": 100000,
        "transfer_amount": 150000,
        "transfer_method": "transfer_bri",
        "note": "Cicilan ke-1 mix",
    })
    assert pay_res.status_code == 200, pay_res.text
    updated_debt = pay_res.json()
    assert updated_debt["paid_amount"] == 450000
    assert updated_debt["remaining"] == 150000
    inst = updated_debt["payments"][1]
    assert inst["method"] == "mix"
    assert inst["cash_amount"] == 100000
    assert inst["transfer_amount"] == 150000
    assert inst["transfer_method"] == "transfer_bri"

    # Daily report should have receivable_payments = 450,000 and transfer_payments = 120,000 + 150,000 = 270,000
    daily = (await api.get("/books/daily", params={"date": today_iso()})).json()
    assert daily["receivable_payments"] == 450000
    assert daily["transfer_payments"] == 270000
    assert daily["transfer_breakdown"]["qris"] == 120000
    assert daily["transfer_breakdown"]["transfer_bri"] == 150000
    assert daily["net_cash"] == 180000  # 80,000 + 100,000 physical cash
    await assert_clean(db)


async def test_reset_data_zeroes_transactions_and_preserves_masters(isolated):
    db, api, user, _ = isolated
    user["role"] = "admin"
    pid = await product(db, stock=12, price=250000)
    await db.customers.insert_one({"id": "cust-1", "name": "Pelanggan Test", "phone": "", "address": ""})
    await db.suppliers.insert_one({"id": "sup-1", "name": "Distributor Test", "phone": "", "address": ""})

    # Create a sale and an expense
    sale_res = await api.post("/transactions", json=checkout(pid, payment_method="cash", cash_received=250000))
    assert sale_res.status_code == 201
    exp_res = await api.post("/expenses", json={
        "date": today_iso(),
        "amount": 50000,
        "category": "Operasional",
        "description": "Biaya test",
    })
    assert exp_res.status_code == 201

    # Wrong confirmation keyword is rejected
    bad_reset = await api.post("/imports/reset", json={
        "mode": "zero_transactions",
        "zero_product_stock": True,
        "confirmation": "SALAH",
    })
    assert bad_reset.status_code == 422

    # Valid reset with zero_transactions + zero_product_stock=True
    ok_reset = await api.post("/imports/reset", json={
        "mode": "zero_transactions",
        "zero_product_stock": True,
        "confirmation": "NOLKAN",
    })
    assert ok_reset.status_code == 200, ok_reset.text

    # Verify transactions, expenses, receivables, payables are 0
    assert await db.transactions.count_documents({}) == 0
    assert await db.transaction_details.count_documents({}) == 0
    assert await db.expenses.count_documents({}) == 0
    assert await db.accounts_receivable.count_documents({}) == 0
    assert await db.accounts_payable.count_documents({}) == 0

    # Master product, customer, supplier still exist, and product stock is 0
    prod = await db.products.find_one({"id": pid})
    assert prod is not None and prod["stock"] == 0
    assert await db.customers.count_documents({}) == 1
    assert await db.suppliers.count_documents({}) == 1

    # Daily and monthly reports should be completely 0
    daily = (await api.get("/books/daily", params={"date": today_iso()})).json()
    assert daily["cash_sales"] == 0
    assert daily["receivable_payments"] == 0
    assert daily["transfer_payments"] == 0
    assert daily["expenses"] == 0
    assert daily["net_cash"] == 0
    assert daily["final_cash"] == 0

    monthly = (await api.get("/books/monthly", params={"month": today_iso()[:7]})).json()
    assert monthly["omzet"] == 0
    assert monthly["expenses_total"] == 0
    assert monthly["stok_value"] == 0
    assert monthly["sisa_aset"] == 0
    await assert_clean(db)
