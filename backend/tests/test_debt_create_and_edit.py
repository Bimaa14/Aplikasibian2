"""End-to-end tests for creating and editing accounts receivable (piutang) and accounts payable (hutang)."""
import uuid
from datetime import date, timedelta
from lib.dates import today_iso
from tests.test_financial_safety import isolated, assert_clean


async def test_create_and_edit_receivable_with_customer_and_manual_name(isolated):
    db, api, user, _ = isolated
    user["role"] = "admin"
    await db.customers.insert_many([
        {"id": "cust-1", "name": "CV Maju Jaya", "phone": "08111", "address": "Bandung"},
        {"id": "cust-2", "name": "Bengkel Rahayu", "phone": "08222", "address": "Majalaya"},
    ])
    today = date.fromisoformat(today_iso())
    issued = (today - timedelta(days=5)).isoformat()
    due = (today + timedelta(days=10)).isoformat()

    # Create receivable linked to registered customer
    res1 = await api.post("/receivables", json={
        "customer_id": "cust-1",
        "invoice_number": "INV-MAN-001",
        "amount": 750000,
        "issued_date": issued,
        "due_date": due,
        "note": "Saldo awal piutang",
    })
    assert res1.status_code == 201, res1.text
    r1 = res1.json()
    assert r1["customer_id"] == "cust-1"
    assert r1["customer_name"] == "CV Maju Jaya"
    assert r1["invoice_number"] == "INV-MAN-001"
    assert r1["amount"] == 750000
    assert r1["remaining"] == 750000
    assert r1["status"] == "unpaid"
    assert r1["note"] == "Saldo awal piutang"

    # Create receivable with manual customer name (without customer_id)
    res2 = await api.post("/receivables", json={
        "customer_name": "Pak Ahmad",
        "invoice_number": "INV-MAN-002",
        "amount": 300000,
        "due_date": due,
    })
    assert res2.status_code == 201, res2.text
    r2 = res2.json()
    assert r2["customer_id"] == ""
    assert r2["customer_name"] == "Pak Ahmad"

    # Validation: missing both customer_id and customer_name fails
    bad_empty = await api.post("/receivables", json={
        "invoice_number": "INV-BAD",
        "amount": 100000,
        "due_date": due,
    })
    assert bad_empty.status_code == 422

    # Record a partial installment of Rp 250.000 on r1
    pay_date = (today - timedelta(days=2)).isoformat()
    pay_res = await api.post(f"/receivables/{r1['id']}/pay", json={
        "request_id": str(uuid.uuid4()),
        "amount": 250000,
        "payment_date": pay_date,
        "method": "cash",
        "note": "Cicilan 1",
    })
    assert pay_res.status_code == 200, pay_res.text
    assert pay_res.json()["status"] == "partial"
    assert pay_res.json()["remaining"] == 500000

    # Reject edit if new amount < paid_amount
    bad_amt = await api.put(f"/receivables/{r1['id']}", json={
        "customer_id": "cust-1",
        "invoice_number": "INV-MAN-001",
        "amount": 200000,
        "issued_date": issued,
        "due_date": due,
    })
    assert bad_amt.status_code == 422

    # Reject edit if new issued_date > earliest payment_date
    bad_issued = await api.put(f"/receivables/{r1['id']}", json={
        "customer_id": "cust-1",
        "invoice_number": "INV-MAN-001",
        "amount": 750000,
        "issued_date": today.isoformat(),
        "due_date": due,
    })
    assert bad_issued.status_code == 422

    # Valid edit: change customer, invoice_number, amount to match paid_amount -> becomes paid
    new_due = (today + timedelta(days=20)).isoformat()
    edit_paid = await api.put(f"/receivables/{r1['id']}", json={
        "customer_id": "cust-2",
        "invoice_number": "INV-MAN-001-REV",
        "amount": 250000,
        "issued_date": issued,
        "due_date": new_due,
        "note": "Koreksi nominal lunas",
    })
    assert edit_paid.status_code == 200, edit_paid.text
    updated = edit_paid.json()
    assert updated["customer_id"] == "cust-2"
    assert updated["customer_name"] == "Bengkel Rahayu"
    assert updated["invoice_number"] == "INV-MAN-001-REV"
    assert updated["amount"] == 250000
    assert updated["paid_amount"] == 250000
    assert updated["remaining"] == 0
    assert updated["status"] == "paid"
    assert updated["note"] == "Koreksi nominal lunas"

    # Valid edit: increase amount back above paid_amount -> transitions back to partial
    reopen = await api.put(f"/receivables/{r1['id']}", json={
        "customer_id": "cust-2",
        "invoice_number": "INV-MAN-001-REV",
        "amount": 600000,
        "issued_date": issued,
        "due_date": new_due,
        "note": "Penyesuaian tambahan jasa",
    })
    assert reopen.status_code == 200, reopen.text
    reopened = reopen.json()
    assert reopened["status"] == "partial"
    assert reopened["remaining"] == 350000

    # Summary by customer reflects updated customer & balances
    summary = (await api.get("/receivables/summary/by-customer")).json()
    by_name = {row["customer_name"]: row for row in summary}
    assert by_name["Bengkel Rahayu"]["outstanding"] == 350000
    assert by_name["Pak Ahmad"]["outstanding"] == 300000

    # Void receivable cannot be edited
    await db.accounts_receivable.update_one({"id": r2["id"]}, {"$set": {"status": "void", "remaining": 0}})
    void_edit = await api.put(f"/receivables/{r2['id']}", json={
        "customer_name": "Pak Ahmad",
        "invoice_number": "INV-MAN-002",
        "amount": 350000,
        "due_date": due,
    })
    assert void_edit.status_code == 409
    await assert_clean(db)


async def test_create_and_edit_payable_with_notes_and_partial_payment(isolated):
    db, api, user, _ = isolated
    user["role"] = "admin"
    await db.suppliers.insert_many([
        {"id": "sup-1", "name": "PT Ban Nusantara", "phone": "022111", "address": "Jakarta"},
        {"id": "sup-2", "name": "CV Oli Sejahtera", "phone": "022222", "address": "Bandung"},
    ])
    today = date.fromisoformat(today_iso())
    issued = (today - timedelta(days=4)).isoformat()
    due = (today + timedelta(days=15)).isoformat()

    res = await api.post("/payables", json={
        "supplier_id": "sup-1",
        "invoice_number": "SUP-INV-01",
        "amount": 1200000,
        "issued_date": issued,
        "due_date": due,
        "note": "Faktur ban ring 15",
    })
    assert res.status_code == 201, res.text
    p = res.json()
    assert p["supplier_name"] == "PT Ban Nusantara"
    assert p["amount"] == 1200000
    assert p["remaining"] == 1200000
    assert p["issued_date"] == issued
    assert p["note"] == "Faktur ban ring 15"
    assert p["days_remaining"] == 15

    # Pay partial Rp 400.000
    pay_res = await api.post(f"/payables/{p['id']}/pay", json={
        "request_id": str(uuid.uuid4()),
        "amount": 400000,
        "payment_date": (today - timedelta(days=1)).isoformat(),
        "method": "transfer_bca",
    })
    assert pay_res.status_code == 200, pay_res.text
    assert pay_res.json()["remaining"] == 800000

    # Reject edit below paid_amount
    bad = await api.put(f"/payables/{p['id']}", json={
        "supplier_id": "sup-1",
        "invoice_number": "SUP-INV-01",
        "amount": 350000,
        "issued_date": issued,
        "due_date": due,
    })
    assert bad.status_code == 422

    # Valid edit: update supplier, invoice, amount, due_date, note
    new_due = (today + timedelta(days=30)).isoformat()
    edit_res = await api.put(f"/payables/{p['id']}", json={
        "supplier_id": "sup-2",
        "invoice_number": "SUP-INV-01-FIX",
        "amount": 1000000,
        "issued_date": issued,
        "due_date": new_due,
        "note": "Koreksi distributor dan potongan faktur",
    })
    assert edit_res.status_code == 200, edit_res.text
    updated = edit_res.json()
    assert updated["supplier_id"] == "sup-2"
    assert updated["supplier_name"] == "CV Oli Sejahtera"
    assert updated["invoice_number"] == "SUP-INV-01-FIX"
    assert updated["amount"] == 1000000
    assert updated["paid_amount"] == 400000
    assert updated["remaining"] == 600000
    assert updated["status"] == "partial"
    assert updated["note"] == "Koreksi distributor dan potongan faktur"
    await assert_clean(db)
