"""Critical accounting API regression tests for debts, payments, returns, aging, and reports."""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL is required for public endpoint tests", allow_module_level=True)
BASE_URL = BASE_URL.rstrip("/")


# Modules/features under test: debts lifecycle, installments, idempotency, aging buckets, and cash-vs-accrual reports.


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def server_today(api_client: requests.Session) -> date:
    response = api_client.get(f"{BASE_URL}/api/health", timeout=20)
    assert response.status_code == 200
    return date.fromisoformat(response.json()["today"])


@pytest.fixture
def tracker():
    data = {"debt_ids": [], "entry_ids": []}
    yield data

    env = dotenv_values("/app/backend/.env")
    mongo_url = env.get("MONGO_URL")
    db_name = env.get("DB_NAME")
    if not mongo_url or not db_name:
        return
    client = MongoClient(mongo_url)
    db = client[db_name]
    if data["debt_ids"]:
        db.accounting_debts.delete_many({"id": {"$in": data["debt_ids"]}})
    if data["entry_ids"]:
        db.accounting_entries.delete_many({"id": {"$in": data["entry_ids"]}})
    client.close()


def _create_debt(api_client: requests.Session, tracker, kind: str, today: date, **overrides):
    payload = {
        "kind": kind,
        "party": f"TEST_AUTO_{kind}_{uuid.uuid4().hex[:8]}",
        "reference": f"TEST_AUTO_{kind.upper()}_{uuid.uuid4().hex[:8]}",
        "description": "TEST_AUTO_debt",
        "total": 100_000,
        "hpp": 20_000 if kind == "receivable" else 0,
        "issued_date": (today - timedelta(days=3)).isoformat(),
        "due_date": today.isoformat(),
    }
    payload.update(overrides)
    response = api_client.post(f"{BASE_URL}/api/debts", json=payload, timeout=20)
    if response.status_code == 201:
        tracker["debt_ids"].append(response.json()["id"])
    return response


def _pay(api_client: requests.Session, debt_id: str, amount: int, today: date, request_id: str | None = None, **overrides):
    payload = {
        "amount": amount,
        "method": "cash",
        "note": "TEST_AUTO_payment",
        "payment_date": today.isoformat(),
        "request_id": request_id or f"req-{uuid.uuid4().hex[:12]}",
    }
    payload.update(overrides)
    return api_client.post(f"{BASE_URL}/api/debts/{debt_id}/pay", json=payload, timeout=20)


def _create_entry(api_client: requests.Session, tracker, today: date, **overrides):
    payload = {
        "kind": "sale",
        "description": f"TEST_AUTO_entry_{uuid.uuid4().hex[:6]}",
        "amount": 1_000,
        "hpp": 400,
        "entry_date": today.isoformat(),
        "request_id": f"entry-{uuid.uuid4().hex[:12]}",
    }
    payload.update(overrides)
    response = api_client.post(f"{BASE_URL}/api/entries", json=payload, timeout=20)
    if response.status_code == 201:
        tracker["entry_ids"].append(response.json()["id"])
    return response


def test_debt_create_validation_duplicate_and_cross_kind(api_client, server_today, tracker):
    future = (server_today + timedelta(days=1)).isoformat()
    valid_due = server_today.isoformat()

    missing_party = {
        "kind": "receivable", "party": "", "reference": "TEST_AUTO_REQ_A", "description": "x",
        "total": 10_000, "hpp": 1_000, "issued_date": valid_due, "due_date": valid_due,
    }
    assert api_client.post(f"{BASE_URL}/api/debts", json=missing_party, timeout=20).status_code == 422

    base = {
        "kind": "receivable", "party": "TEST_AUTO_party", "reference": "TEST_AUTO_REQ_B",
        "description": "x", "hpp": 1_000, "issued_date": valid_due, "due_date": valid_due,
    }
    assert api_client.post(f"{BASE_URL}/api/debts", json={**base, "total": 0}, timeout=20).status_code == 422
    assert api_client.post(f"{BASE_URL}/api/debts", json={**base, "total": 10.5}, timeout=20).status_code == 422
    assert api_client.post(f"{BASE_URL}/api/debts", json={**base, "total": 1000, "issued_date": future}, timeout=20).status_code == 422
    assert api_client.post(
        f"{BASE_URL}/api/debts",
        json={**base, "total": 1000, "issued_date": valid_due, "due_date": (server_today - timedelta(days=1)).isoformat()},
        timeout=20,
    ).status_code == 422

    first = _create_debt(api_client, tracker, "receivable", server_today, reference="TEST_AUTO_INV_DUP", total=77_000)
    assert first.status_code == 201
    assert first.json()["reference"] == "TEST_AUTO_INV_DUP"

    dup_same_kind = _create_debt(api_client, tracker, "receivable", server_today, reference="test_auto_inv_dup", total=88_000)
    assert dup_same_kind.status_code == 409

    cross_kind = _create_debt(api_client, tracker, "payable", server_today, reference="test_auto_inv_dup", total=66_000, hpp=0)
    assert cross_kind.status_code == 201


def test_payment_validation_rejects_missing_and_invalid_amount_dates(api_client, server_today, tracker):
    created = _create_debt(api_client, tracker, "receivable", server_today)
    assert created.status_code == 201
    debt_id = created.json()["id"]

    missing_amount = {
        "method": "cash", "note": "TEST_AUTO_missing_amount", "payment_date": server_today.isoformat(), "request_id": f"req-{uuid.uuid4().hex[:12]}"
    }
    assert api_client.post(f"{BASE_URL}/api/debts/{debt_id}/pay", json=missing_amount, timeout=20).status_code == 422

    latest = api_client.get(f"{BASE_URL}/api/debts/{debt_id}", timeout=20).json()
    assert latest["status"] == "unpaid"
    assert latest["paid_amount"] == 0

    assert _pay(api_client, debt_id, 0, server_today).status_code == 422
    assert _pay(api_client, debt_id, -1, server_today).status_code == 422
    fractional = {
        "amount": 10.7,
        "method": "cash",
        "note": "TEST_AUTO_fractional",
        "payment_date": server_today.isoformat(),
        "request_id": f"req-{uuid.uuid4().hex[:12]}",
    }
    assert api_client.post(f"{BASE_URL}/api/debts/{debt_id}/pay", json=fractional, timeout=20).status_code == 422
    assert _pay(api_client, debt_id, 100_001, server_today).status_code == 422
    assert _pay(api_client, debt_id, 1000, server_today, payment_date=(server_today + timedelta(days=1)).isoformat()).status_code == 422
    assert _pay(api_client, debt_id, 1000, server_today, payment_date=(server_today - timedelta(days=10)).isoformat()).status_code == 422


def test_partial_and_full_payment_updates_status_and_history(api_client, server_today, tracker):
    created = _create_debt(api_client, tracker, "receivable", server_today, total=100_000)
    assert created.status_code == 201
    debt_id = created.json()["id"]

    first = _pay(api_client, debt_id, 40_000, server_today, note="TEST_AUTO_first")
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["status"] == "partial"
    assert first_data["paid_amount"] == 40_000
    assert first_data["remaining"] == 60_000
    assert len(first_data["payments"]) == 1
    assert first_data["payments"][0]["note"] == "TEST_AUTO_first"

    second = _pay(api_client, debt_id, 60_000, server_today, note="TEST_AUTO_second")
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["status"] == "paid"
    assert second_data["paid_amount"] == 100_000
    assert second_data["remaining"] == 0
    assert len(second_data["payments"]) == 2

    blocked = _pay(api_client, debt_id, 1, server_today)
    assert blocked.status_code == 409


def test_payment_idempotency_same_key_and_conflict(api_client, server_today, tracker):
    created = _create_debt(api_client, tracker, "receivable", server_today, total=50_000)
    assert created.status_code == 201
    debt_id = created.json()["id"]
    req_id = f"idem-{uuid.uuid4().hex[:12]}"

    first = _pay(api_client, debt_id, 20_000, server_today, request_id=req_id, note="TEST_AUTO_idem")
    assert first.status_code == 200

    replay = _pay(api_client, debt_id, 20_000, server_today, request_id=req_id, note="TEST_AUTO_idem")
    assert replay.status_code == 200
    assert replay.json()["paid_amount"] == 20_000
    assert len(replay.json()["payments"]) == 1

    conflict = _pay(api_client, debt_id, 25_000, server_today, request_id=req_id, note="TEST_AUTO_idem")
    assert conflict.status_code == 409


def test_concurrent_payments_cannot_overpay_or_duplicate_audit(api_client, server_today, tracker):
    created = _create_debt(api_client, tracker, "receivable", server_today, total=100_000)
    assert created.status_code == 201
    debt_id = created.json()["id"]

    def pay_once(rid: str):
        return _pay(api_client, debt_id, 80_000, server_today, request_id=rid).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(pay_once, [f"req-{uuid.uuid4().hex[:8]}", f"req-{uuid.uuid4().hex[:8]}"]))

    assert 200 in statuses
    assert any(code in (409, 422) for code in statuses)

    latest = api_client.get(f"{BASE_URL}/api/debts/{debt_id}", timeout=20).json()
    assert latest["paid_amount"] == 80_000
    assert latest["remaining"] == 20_000
    assert len(latest["payments"]) == 1


def test_concurrent_duplicate_idempotency_does_not_create_duplicate_payment(api_client, server_today, tracker):
    created = _create_debt(api_client, tracker, "receivable", server_today, total=100_000)
    assert created.status_code == 201
    debt_id = created.json()["id"]
    req_id = f"req-{uuid.uuid4().hex[:10]}"

    def pay_dup():
        return _pay(api_client, debt_id, 50_000, server_today, request_id=req_id, note="TEST_AUTO_dup").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: pay_dup(), [1, 2]))

    assert all(code in (200, 409) for code in statuses)
    latest = api_client.get(f"{BASE_URL}/api/debts/{debt_id}", timeout=20).json()
    assert latest["paid_amount"] == 50_000
    assert len(latest["payments"]) == 1


def test_return_unpaid_receivable_becomes_void_and_rejects_repeat_and_pay(api_client, server_today, tracker):
    created = _create_debt(api_client, tracker, "receivable", server_today, total=42_000)
    assert created.status_code == 201
    debt_id = created.json()["id"]

    returned = api_client.post(
        f"{BASE_URL}/api/debts/{debt_id}/return",
        json={"reason": "TEST_AUTO_customer_return", "refund_confirmed": False},
        timeout=20,
    )
    assert returned.status_code == 200
    data = returned.json()
    assert data["status"] == "void"
    assert data["remaining"] == 0
    assert data["paid_amount"] == 0
    assert data["refund_amount"] == 0

    assert _pay(api_client, debt_id, 1000, server_today).status_code == 409
    repeat = api_client.post(
        f"{BASE_URL}/api/debts/{debt_id}/return",
        json={"reason": "TEST_AUTO_again", "refund_confirmed": False},
        timeout=20,
    )
    assert repeat.status_code == 409


def test_return_paid_receivable_requires_refund_confirmation_and_keeps_history(api_client, server_today, tracker):
    created = _create_debt(api_client, tracker, "receivable", server_today, total=100_000)
    assert created.status_code == 201
    debt_id = created.json()["id"]
    assert _pay(api_client, debt_id, 30_000, server_today, note="TEST_AUTO_refund_case").status_code == 200

    reject = api_client.post(
        f"{BASE_URL}/api/debts/{debt_id}/return",
        json={"reason": "TEST_AUTO_needs_refund", "refund_confirmed": False},
        timeout=20,
    )
    assert reject.status_code == 422

    ok = api_client.post(
        f"{BASE_URL}/api/debts/{debt_id}/return",
        json={"reason": "TEST_AUTO_refund_done", "refund_confirmed": True},
        timeout=20,
    )
    assert ok.status_code == 200
    data = ok.json()
    assert data["status"] == "void"
    assert data["remaining"] == 0
    assert data["refund_amount"] == 30_000
    assert len(data["payments"]) == 1

    assert _pay(api_client, debt_id, 1, server_today).status_code == 409


def test_return_not_available_for_payable(api_client, server_today, tracker):
    created = _create_debt(api_client, tracker, "payable", server_today, total=31_000, hpp=0)
    assert created.status_code == 201
    debt_id = created.json()["id"]

    response = api_client.post(
        f"{BASE_URL}/api/debts/{debt_id}/return",
        json={"reason": "TEST_AUTO_not_allowed", "refund_confirmed": False},
        timeout=20,
    )
    assert response.status_code == 422


def test_overview_aging_boundaries_today_upcoming_and_exclusions(api_client, server_today, tracker):
    month = server_today.strftime("%Y-%m")
    baseline = api_client.get(f"{BASE_URL}/api/overview?month={month}", timeout=20).json()["summary"]["receivable"]
    amounts = {0: 10_000, 30: 30_000, 31: 31_000, 60: 60_000, 61: 61_000, 90: 90_000, 91: 91_000}
    for overdue, amount in amounts.items():
        due = server_today - timedelta(days=overdue)
        issued = due - timedelta(days=3)
        created = _create_debt(
            api_client, tracker, "receivable", server_today,
            total=amount, hpp=0,
            issued_date=issued.isoformat(), due_date=due.isoformat(),
            reference=f"TEST_AUTO_AGE_{overdue}_{uuid.uuid4().hex[:6]}"
        )
        assert created.status_code == 201

    upcoming = _create_debt(
        api_client, tracker, "receivable", server_today,
        total=55_000, hpp=0,
        issued_date=(server_today - timedelta(days=1)).isoformat(),
        due_date=(server_today + timedelta(days=5)).isoformat(),
        reference=f"TEST_AUTO_AGE_UP_{uuid.uuid4().hex[:6]}"
    )
    assert upcoming.status_code == 201

    paid = _create_debt(
        api_client, tracker, "receivable", server_today,
        total=22_000, hpp=0,
        issued_date=(server_today - timedelta(days=3)).isoformat(),
        due_date=(server_today - timedelta(days=2)).isoformat(),
        reference=f"TEST_AUTO_AGE_PAID_{uuid.uuid4().hex[:6]}"
    )
    assert paid.status_code == 201
    assert _pay(api_client, paid.json()["id"], 22_000, server_today, note="TEST_AUTO_paid_excluded").status_code == 200

    voided = _create_debt(
        api_client, tracker, "receivable", server_today,
        total=44_000, hpp=0,
        issued_date=(server_today - timedelta(days=3)).isoformat(),
        due_date=(server_today - timedelta(days=2)).isoformat(),
        reference=f"TEST_AUTO_AGE_VOID_{uuid.uuid4().hex[:6]}"
    )
    assert voided.status_code == 201
    assert api_client.post(
        f"{BASE_URL}/api/debts/{voided.json()['id']}/return",
        json={"reason": "TEST_AUTO_aging_void", "refund_confirmed": False},
        timeout=20,
    ).status_code == 200

    month = server_today.strftime("%Y-%m")
    overview = api_client.get(f"{BASE_URL}/api/overview?month={month}", timeout=20)
    assert overview.status_code == 200
    rec = overview.json()["summary"]["receivable"]

    assert rec["buckets"]["0-30"] - baseline["buckets"]["0-30"] == amounts[0] + amounts[30]
    assert rec["buckets"]["31-60"] - baseline["buckets"]["31-60"] == amounts[31] + amounts[60]
    assert rec["buckets"]["61-90"] - baseline["buckets"]["61-90"] == amounts[61] + amounts[90]
    assert rec["buckets"]["90+"] - baseline["buckets"]["90+"] == amounts[91]
    assert rec["due_today"] - baseline["due_today"] == amounts[0]
    assert rec["total"] - baseline["total"] == sum(amounts.values()) + 55_000


def test_reports_cash_margin_and_receivables_paid_use_real_payment_rules(api_client, server_today, tracker):
    current_month = server_today.strftime("%Y-%m")
    prior_month_anchor = (server_today.replace(day=1) - timedelta(days=1)).replace(day=min(server_today.day, 28))
    prior_month = prior_month_anchor.strftime("%Y-%m")
    baseline = api_client.get(f"{BASE_URL}/api/reports?month={current_month}", timeout=20).json()
    prior_baseline = api_client.get(f"{BASE_URL}/api/reports?month={prior_month}", timeout=20).json()

    e_sale = _create_entry(api_client, tracker, server_today, kind="sale", amount=1_000, hpp=400, description="TEST_AUTO_sale_cash")
    e_expense = _create_entry(api_client, tracker, server_today, kind="expense", amount=200, hpp=0, description="TEST_AUTO_expense")
    e_supplier_cash = _create_entry(api_client, tracker, server_today, kind="supplier_payment", amount=300, hpp=0, description="TEST_AUTO_supplier_cash")
    assert e_sale.status_code == 201 and e_expense.status_code == 201 and e_supplier_cash.status_code == 201

    rec_active = _create_debt(
        api_client, tracker, "receivable", server_today,
        total=500, hpp=200,
        issued_date=server_today.isoformat(), due_date=server_today.isoformat(),
        reference=f"TEST_AUTO_REP_A_{uuid.uuid4().hex[:5]}"
    )
    assert rec_active.status_code == 201
    assert _pay(api_client, rec_active.json()["id"], 200, server_today, note="TEST_AUTO_rep_a").status_code == 200

    rec_void = _create_debt(
        api_client, tracker, "receivable", server_today,
        total=700, hpp=250,
        issued_date=prior_month_anchor.isoformat(), due_date=prior_month_anchor.isoformat(),
        reference=f"TEST_AUTO_REP_B_{uuid.uuid4().hex[:5]}"
    )
    assert rec_void.status_code == 201
    assert _pay(api_client, rec_void.json()["id"], 300, server_today, note="TEST_AUTO_rep_b").status_code == 200
    assert api_client.post(
        f"{BASE_URL}/api/debts/{rec_void.json()['id']}/return",
        json={"reason": "TEST_AUTO_report_refund", "refund_confirmed": True},
        timeout=20,
    ).status_code == 200

    payable = _create_debt(
        api_client, tracker, "payable", server_today,
        total=450, hpp=0,
        issued_date=server_today.isoformat(), due_date=server_today.isoformat(),
        reference=f"TEST_AUTO_REP_P_{uuid.uuid4().hex[:5]}"
    )
    assert payable.status_code == 201
    assert _pay(api_client, payable.json()["id"], 150, server_today, note="TEST_AUTO_rep_payable").status_code == 200

    report = api_client.get(f"{BASE_URL}/api/reports?month={current_month}", timeout=20)
    assert report.status_code == 200
    data = report.json()

    expected_cash_delta = {"cash_sales": 1000, "receivable_collections": 500,
                           "supplier_payments": 450, "expenses": 200, "refunds": 300,
                           "income": 1500, "outgoing": 950, "net": 550}
    for key, amount in expected_cash_delta.items():
        assert data["cash"][key] - baseline["cash"][key] == amount, key
    # Prior-period credit sale is reversed in CURRENT accrual, not deleted from history.
    expected_accrual_delta = {"revenue": 800, "hpp": 350, "expenses": 200,
                             "gross_profit": 450, "net": 250}
    for key, amount in expected_accrual_delta.items():
        assert data["accrual"][key] - baseline["accrual"][key] == amount, key
    assert data["receivables_paid"] - baseline["receivables_paid"] == 200
    assert sum(d["income"] for d in data["series"]) == data["cash"]["income"]
    assert sum(d["outgoing"] for d in data["series"]) == data["cash"]["outgoing"]
    prior = api_client.get(f"{BASE_URL}/api/reports?month={prior_month}", timeout=20).json()
    assert prior["accrual"]["revenue"] - prior_baseline["accrual"]["revenue"] == 700
    assert prior["accrual"]["hpp"] - prior_baseline["accrual"]["hpp"] == 250
    assert prior["accrual"]["net"] - prior_baseline["accrual"]["net"] == 450
    assert prior["cash"]["net"] == prior_baseline["cash"]["net"]


def test_backup_payload_has_no_mongodb_object_ids(api_client):
    response = api_client.get(f"{BASE_URL}/api/backup", timeout=20)
    assert response.status_code == 200
    payload = response.json()

    def has_object_id(node):
        if isinstance(node, dict):
            if "_id" in node:
                return True
            return any(has_object_id(v) for v in node.values())
        if isinstance(node, list):
            return any(has_object_id(x) for x in node)
        return False

    assert payload.get("schema_version") == 1
    assert has_object_id(payload) is False
