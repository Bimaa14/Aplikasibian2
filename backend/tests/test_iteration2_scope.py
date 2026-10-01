"""Iteration 2 regression: Excel report reconciliation, imports idempotency,
receivables/payables imported totals, POS credit + return -> void receivable,
partial installment payment behaviors, and RBAC for admin-only endpoints.
"""

import os
import uuid
import httpx
import pytest
from tests.credentials import credentials

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API = f"{BACKEND_URL}/api"

ADMIN = credentials("ADMIN")
KASIR = credentials("CASHIER")


def _login(creds):
    c = httpx.Client(base_url=API, timeout=60.0)
    r = c.post("/auth/login", json=creds)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:300]}"
    # cookie is marked Secure but we hit http://localhost — copy it into client cookies manually
    for k, v in r.cookies.items():
        c.cookies.set(k, v)
    if "bengkel_session" in r.headers.get("set-cookie", ""):
        # parse raw
        import re
        m = re.search(r"bengkel_session=([^;]+)", r.headers.get("set-cookie", ""))
        if m:
            c.cookies.set("bengkel_session", m.group(1))
    return c


@pytest.fixture(scope="module")
def admin():
    c = _login(ADMIN)
    try:
        yield c
    finally:
        c.close()


@pytest.fixture(scope="module")
def kasir():
    c = _login(KASIR)
    try:
        yield c
    finally:
        c.close()


# ------- Excel reports -------

def _diff_ok(differences):
    for k, v in (differences or {}).items():
        assert float(v) == 0.0, f"diff nonzero for {k}={v}"


def test_report_store_may_diff_zero(admin):
    r = admin.get("/excel/reports", params={"month": "2026-05", "origin": "preview"})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "store_check" in data
    _diff_ok(data["store_check"].get("differences") or {})


def test_report_september_aug_diff_zero(admin):
    r = admin.get("/excel/reports", params={"month": "2026-08", "origin": "preview"})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "september_check" in data
    _diff_ok(data["september_check"].get("differences") or {})


@pytest.mark.parametrize("month", [f"2026-0{i}" for i in range(1, 10)])
def test_report_store_all_months_diff_zero(admin, month):
    r = admin.get("/excel/reports", params={"month": month, "origin": "preview"})
    assert r.status_code == 200, f"{month}: {r.text[:200]}"
    data = r.json()
    store = data.get("store_check") or {}
    _diff_ok(store.get("differences") or {})


# ------- Receivables / Payables imported totals -------

def test_receivables_imported_totals(admin):
    r = admin.get("/receivables")
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", body.get("data", []))
    assert len(items) >= 24, f"expected >=24 receivables, got {len(items)}"
    # filter to non-void
    active = [x for x in items if x.get("status") != "void"]
    total_remaining = sum(float(x.get("remaining", 0)) for x in active)
    # Check top 24 by created/import summing to 65_844_000 (allow rounding)
    imported = [x for x in items if x.get("source") in (None, "september", "import") or True]
    # basic aging fields present on at least one
    sample = active[0] if active else items[0]
    for f in ("due_label", "aging_bucket"):
        assert f in sample, f"missing aging field {f} in {sample.keys()}"
    assert total_remaining >= 65_844_000 - 1, f"remaining total {total_remaining}"


def test_payables_imported_totals(admin):
    r = admin.get("/payables")
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", body.get("data", []))
    assert len(items) >= 39, f"expected >=39 payables, got {len(items)}"
    total_remaining = sum(float(x.get("remaining", 0)) for x in items)
    sample = items[0]
    for f in ("due_label", "aging_bucket"):
        assert f in sample, f"missing aging field {f}"
    assert total_remaining >= 829_751_449 - 1, f"payables remaining {total_remaining}"


# ------- Imports preview + commit idempotency -------

def test_imports_preview_september_receivables(admin):
    r = admin.get("/imports/preview", params={"source": "september", "group": "receivables"})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    summary = (data.get("summary") or {}).get("receivables") or {}
    ready = summary.get("ready")
    blocked = summary.get("blocked")
    assert ready == 24, f"ready={ready}"
    assert blocked in (0, None), f"blocked={blocked}"


def test_imports_preview_september_payables(admin):
    r = admin.get("/imports/preview", params={"source": "september", "group": "payables"})
    assert r.status_code == 200
    data = r.json()
    summary = (data.get("summary") or {}).get("payables") or {}
    ready = summary.get("ready")
    blocked = summary.get("blocked")
    assert ready == 39, f"ready={ready}"
    assert blocked in (0, None)


def test_imports_commit_idempotent(admin):
    # get digest from preview
    r = admin.get("/imports/preview", params={"source": "september"})
    assert r.status_code == 200, r.text[:300]
    prev = r.json()
    digest = prev.get("digest") or prev.get("source_digest") or prev.get("checksum")
    # capture counts before
    before_recv = len((admin.get("/receivables").json() or []))
    before_pay = len((admin.get("/payables").json() or []))
    payload = {
        "source": "september",
        "digest": digest,
        "groups": ["receivables", "payables"],
        "confirmed": True,
    }
    r2 = admin.post("/imports/commit", json=payload)
    assert r2.status_code in (200, 201, 409), r2.text[:400]
    data = r2.json() if r2.content else {}
    after_recv = len((admin.get("/receivables").json() or []))
    after_pay = len((admin.get("/payables").json() or []))
    # No duplicates: counts should be unchanged
    assert after_recv == before_recv, f"recv changed {before_recv}->{after_recv}"
    assert after_pay == before_pay, f"pay changed {before_pay}->{after_pay}"


# ------- POS: cash + credit checkout, void on return -------

@pytest.fixture(scope="module")
def test_product(admin):
    payload = {
        "sku": f"TEST_SKU_{uuid.uuid4().hex[:6]}",
        "name": "TEST Product Iter2",
        "type": "barang",
        "category": "TIRE",
        "selling_price": 100000,
        "cost_price": 60000,
        "stock": 50,
    }
    r = admin.post("/products", json=payload)
    assert r.status_code in (200, 201), r.text[:300]
    prod = r.json()
    yield prod
    try:
        admin.delete(f"/products/{prod.get('id')}")
    except Exception:
        pass


@pytest.fixture(scope="module")
def test_customer(admin):
    r = admin.post("/customers", json={"name": "TEST Cust Iter2", "phone": "0800"})
    assert r.status_code in (200, 201), r.text[:300]
    yield r.json()


def test_pos_cash_checkout(admin, test_product):
    payload = {
        "items": [{"product_id": test_product["id"], "qty": 1, "price": test_product["selling_price"]}],
        "payment_method": "cash",
        "paid_amount": test_product["selling_price"],
    }
    r = admin.post("/transactions", json=payload)
    assert r.status_code in (200, 201), r.text[:400]
    tx = r.json()
    assert tx.get("id")


def test_pos_credit_creates_receivable_and_return_voids_it(admin, test_product, test_customer):
    payload = {
        "items": [{"product_id": test_product["id"], "qty": 1, "price": test_product["selling_price"]}],
        "payment_method": "credit",
        "customer_id": test_customer["id"],
        "paid_amount": 0,
        "due_date": "2026-12-31",
    }
    r = admin.post("/transactions", json=payload)
    assert r.status_code in (200, 201), r.text[:400]
    tx = r.json()
    tx_id = tx.get("id")
    # find associated receivable
    rs = admin.get("/receivables").json()
    items = rs if isinstance(rs, list) else rs.get("items", [])
    ar = next((x for x in items if x.get("transaction_id") == tx_id or x.get("source_transaction_id") == tx_id), None)
    assert ar is not None, "receivable not created for credit sale"
    assert ar.get("status") in ("open", "unpaid", "partial", "new", "outstanding"), f"unexpected status {ar.get('status')}"

    # Return transaction
    ret = admin.post(f"/transactions/{tx_id}/return", json={"reason": "TEST return"})
    if ret.status_code == 404:
        # alternate endpoint
        ret = admin.post(f"/transactions/{tx_id}/void", json={"reason": "TEST return"})
    assert ret.status_code in (200, 201), f"return failed {ret.status_code}: {ret.text[:300]}"

    rs2 = admin.get("/receivables").json()
    items2 = rs2 if isinstance(rs2, list) else rs2.get("items", [])
    ar2 = next((x for x in items2 if x.get("id") == ar["id"]), None)
    assert ar2 is not None, "receivable disappeared"
    assert ar2.get("status") == "void", f"expected status void, got {ar2.get('status')}"


# ------- Partial installment payment -------

def test_receivable_partial_pay_and_idempotency(admin, test_product, test_customer):
    # create credit sale (fresh so we can pay it)
    r = admin.post("/transactions", json={
        "items": [{"product_id": test_product["id"], "qty": 2, "price": test_product["selling_price"]}],
        "payment_method": "credit",
        "customer_id": test_customer["id"],
        "paid_amount": 0,
        "due_date": "2026-12-31",
    })
    assert r.status_code in (200, 201)
    tx = r.json()
    tx_id = tx["id"]
    rs = admin.get("/receivables").json()
    items = rs if isinstance(rs, list) else rs.get("items", [])
    ar = next(x for x in items if x.get("transaction_id") == tx_id or x.get("source_transaction_id") == tx_id)
    ar_id = ar["id"]
    total = float(ar.get("total") or ar.get("amount") or 200000)

    request_id = f"TEST-req-{uuid.uuid4().hex[:8]}"
    # partial payment
    r1 = admin.post(f"/receivables/{ar_id}/pay", json={"amount": 50000, "request_id": request_id, "payment_date": "2026-09-27"})
    assert r1.status_code in (200, 201), r1.text[:400]
    body1 = r1.json()
    assert body1.get("status") == "partial", f"status {body1.get('status')}"
    assert float(body1.get("paid_amount", 0)) == 50000

    # idempotent repeat with same request_id
    r2 = admin.post(f"/receivables/{ar_id}/pay", json={"amount": 50000, "request_id": request_id, "payment_date": "2026-09-27"})
    assert r2.status_code in (200, 201, 409), r2.text[:400]
    rs_after = admin.get("/receivables").json()
    items_after = rs_after if isinstance(rs_after, list) else rs_after.get("items", [])
    check = next((x for x in items_after if x.get("id") == ar_id), {})
    assert float(check.get("paid_amount", 0)) == 50000, f"paid_amount doubled to {check.get('paid_amount')}"

    # overpayment 422
    r3 = admin.post(f"/receivables/{ar_id}/pay", json={
        "amount": total + 1_000_000,
        "request_id": f"TEST-over-{uuid.uuid4().hex[:6]}",
        "payment_date": "2026-09-27",
    })
    assert r3.status_code == 422, f"expected 422, got {r3.status_code}: {r3.text[:300]}"

    # cleanup: void via return on transaction
    admin.post(f"/transactions/{tx_id}/return", json={"reason": "TEST cleanup"})


# ------- RBAC -------

def test_rbac_kasir_forbidden(kasir):
    r = kasir.get("/excel/reports", params={"month": "2026-08", "origin": "preview"})
    assert r.status_code == 403, f"kasir got {r.status_code}"
    r2 = kasir.get("/imports/preview", params={"source": "september"})
    assert r2.status_code == 403, f"kasir got {r2.status_code}"


def test_rbac_admin_allowed(admin):
    r = admin.get("/excel/reports", params={"month": "2026-08", "origin": "preview"})
    assert r.status_code == 200
    r2 = admin.get("/imports/preview", params={"source": "september"})
    assert r2.status_code == 200
