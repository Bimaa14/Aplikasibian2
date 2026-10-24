"""Checkout regressions run against an in-memory database with no network writes."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

from fastapi import FastAPI
import httpx
import pytest

from lib import debts, financial_operations
from lib.auth import require_user
from lib.financial_operations import FinancialOperation, MARKER, financial_lock
from routers import transactions


MISSING = object()


def matches(document, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(matches(document, part) for part in expected):
                return False
            continue
        actual = document.get(key, MISSING)
        if isinstance(expected, dict):
            for operator, value in expected.items():
                if operator == "$exists" and (actual is not MISSING) != value:
                    return False
                if operator == "$in" and actual not in value:
                    return False
                if operator == "$ne" and actual == value:
                    return False
                if operator == "$gte" and (actual is MISSING or actual < value):
                    return False
        elif actual != expected:
            return False
    return True


class Cursor:
    def __init__(self, rows):
        self.rows = deepcopy(rows)

    def sort(self, field, direction):
        self.rows.sort(key=lambda row: row[field], reverse=direction == -1)
        return self

    async def to_list(self, length):
        return self.rows if length is None else self.rows[:length]

    def __aiter__(self):
        self.iterator = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration:
            raise StopAsyncIteration


class Collection:
    def __init__(self, name):
        self.name = name
        self.documents = []

    def find(self, query, projection=None):
        return Cursor([row for row in self.documents if matches(row, query)])

    async def find_one(self, query, projection=None):
        return next((deepcopy(row) for row in self.documents if matches(row, query)), None)

    async def count_documents(self, query):
        return sum(matches(row, query) for row in self.documents)

    async def insert_one(self, document):
        self.documents.append(deepcopy(document))

    async def update_one(self, query, changes):
        row = next((row for row in self.documents if matches(row, query)), None)
        if row is None:
            return SimpleNamespace(matched_count=0)
        for key, value in changes.get("$set", {}).items():
            row[key] = deepcopy(value)
        for key, value in changes.get("$inc", {}).items():
            row[key] = row.get(key, 0) + value
        for key in changes.get("$unset", {}):
            row.pop(key, None)
        for key, value in changes.get("$push", {}).items():
            row.setdefault(key, []).append(deepcopy(value))
        return SimpleNamespace(matched_count=1)

    async def delete_one(self, query):
        row = next((row for row in self.documents if matches(row, query)), None)
        if row is not None:
            self.documents.remove(row)


class Database:
    def __init__(self):
        self.collections = {}

    def __getattr__(self, name):
        return self[name]

    def __getitem__(self, name):
        return self.collections.setdefault(name, Collection(name))


@pytest.fixture
async def isolated_checkout(monkeypatch):
    database = Database()
    for module in (transactions, debts, financial_operations):
        monkeypatch.setattr(module, "db", database)
    monkeypatch.setattr(financial_lock, "lock", asyncio.Lock())
    monkeypatch.setattr(transactions, "today_iso", lambda: "2026-10-24")
    monkeypatch.setattr(debts, "today_iso", lambda: "2026-10-24")
    await database.products.insert_one({
        "id": "tire", "name": "Test tire", "sku": "T-1", "type": "barang",
        "stock": 5, "cost_price": 5000, "selling_price": 10000, "service_fee": 0,
    })
    await database.customers.insert_one({"id": "customer", "name": "Customer"})
    app = FastAPI()
    app.include_router(transactions.router)
    app.dependency_overrides[require_user] = lambda: {"id": "cashier", "role": "kasir"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
    ) as api:
        yield database, api


def credit(**changes):
    return {
        "request_id": "checkout-dp-test", "payment_method": "credit", "customer_id": "customer",
        "credit_term_days": 14, "items": [{"product_id": "tire", "qty": 1}], **changes,
    }


def assert_clean(database):
    assert not database.financial_operations.documents
    assert all(MARKER not in row for collection in database.collections.values() for row in collection.documents)


@pytest.mark.parametrize("days,due", [(14, "2026-11-07"), (40, "2026-12-03"), (3650, "2036-10-21")])
async def test_terms_use_server_date_and_leave_full_receivable(isolated_checkout, days, due):
    database, api = isolated_checkout
    response = await api.post("/transactions", json=credit(credit_term_days=days, due_date="2099-01-01"))
    assert response.status_code == 201, response.text
    tx = response.json()
    assert tx["credit_term_days"] == days and tx["due_date"] == due
    assert tx["down_payment_amount"] == 0 and tx["down_payment_method"] is None
    debt = database.accounts_receivable.documents[0]
    assert (debt["amount"], debt["remaining"], debt["paid_amount"], debt["status"], debt["payments"]) == (10000, 10000, 0, "unpaid", [])
    assert debt["due_date"] == due
    assert_clean(database)


@pytest.mark.parametrize("method", ["cash", "edc", "transfer_bca", "transfer_bri", "transfer_bni", "qris"])
@pytest.mark.parametrize("amount,profit", [(3000, 3000), (7000, 5000)])
async def test_down_payment_is_saved_once_with_profit_cap_and_reprint(isolated_checkout, monkeypatch, method, amount, profit):
    database, api = isolated_checkout
    body = credit(down_payment_amount=amount, down_payment_method=method, vehicle_plate=" b 1234 xy ")
    first = await api.post("/transactions", json=body)
    assert first.status_code == 201, first.text
    tx = first.json()
    assert tx["payment_method"] == "credit" and tx["vehicle_plate"] == "B 1234 XY"
    assert tx["down_payment_amount"] == amount and tx["down_payment_method"] == method
    assert tx["cash_received"] is None and tx["change_amount"] is None
    debt = database.accounts_receivable.documents[0]
    assert (debt["amount"], debt["remaining"], debt["paid_amount"], debt["status"]) == (10000, 10000 - amount, amount, "partial")
    payment = debt["payments"][0]
    assert payment["amount"] == amount and payment["profit_amount"] == profit
    assert payment["method"] == method and payment["payment_date"] == "2026-10-24"
    assert payment["is_down_payment"] is True and payment["profit_is_manual"] is False
    monkeypatch.setattr(transactions, "today_iso", lambda: "2026-10-25")
    retry = await api.post("/transactions", json=body)
    reprint = await api.get("/transactions/" + tx["id"])
    assert retry.json() == reprint.json() == tx
    assert len(database.transactions.documents) == len(database.accounts_receivable.documents) == 1
    assert len(database.accounts_receivable.documents[0]["payments"]) == 1
    assert database.products.documents[0]["stock"] == 4
    changed = await api.post("/transactions", json={**body, "down_payment_amount": amount + 1})
    assert changed.status_code == 409
    assert_clean(database)


async def test_legacy_due_date_and_cash_checkout_remain_supported(isolated_checkout):
    database, api = isolated_checkout
    legacy = await api.post("/transactions", json=credit(credit_term_days=None, due_date="2026-12-01"))
    assert legacy.status_code == 201, legacy.text
    assert legacy.json()["due_date"] == "2026-12-01" and legacy.json()["credit_term_days"] is None
    cash = await api.post("/transactions", json={
        "items": [{"product_id": "tire", "qty": 1}], "payment_method": "cash", "cash_received": 20000,
    })
    assert cash.status_code == 201, cash.text
    assert (cash.json()["cash_received"], cash.json()["change_amount"]) == (20000, 10000)
    assert len(database.accounts_receivable.documents) == 1
    assert_clean(database)


@pytest.mark.parametrize("price,fee,amount,remaining,profit", [
    (10000, 500, 7000, 3000, 5500),
    (4000, 0, 3000, 1000, 0),
    (10000.10, 0, 3333.33, 6666.77, 3333.33),
])
async def test_down_payment_profit_fee_loss_and_cent_rounding(isolated_checkout, price, fee, amount, remaining, profit):
    database, api = isolated_checkout
    database.products.documents[0].update(selling_price=price, service_fee=fee)
    response = await api.post("/transactions", json=credit(down_payment_amount=amount, down_payment_method="cash"))
    assert response.status_code == 201, response.text
    debt = database.accounts_receivable.documents[0]
    assert debt["remaining"] == remaining and debt["payments"][0]["profit_amount"] == profit
    assert_clean(database)


@pytest.mark.parametrize("changes", [
    {"credit_term_days": 0}, {"credit_term_days": 3651}, {"credit_term_days": 1.5},
    {"credit_term_days": True}, {"credit_term_days": None}, {"customer_id": None},
    {"down_payment_amount": -1}, {"down_payment_amount": 0.001},
    {"down_payment_amount": 10000, "down_payment_method": "cash"},
    {"down_payment_amount": 10001, "down_payment_method": "cash"},
    {"down_payment_amount": 1000}, {"down_payment_amount": 1000, "down_payment_method": "credit"},
    {"cash_received": 1000}, {"payment_method": "cash"},
    {"payment_method": "cash", "credit_term_days": None, "down_payment_amount": 1000, "down_payment_method": "cash"},
])
async def test_invalid_terms_or_down_payment_do_not_write(isolated_checkout, changes):
    database, api = isolated_checkout
    response = await api.post("/transactions", json=credit(**changes))
    assert response.status_code == 422, response.text
    assert not database.transactions.documents and not database.accounts_receivable.documents
    assert database.products.documents[0]["stock"] == 5
    assert_clean(database)


@pytest.mark.parametrize("target", ["transactions", "transaction_details", "products", "accounts_receivable", "checkout_requests"])
async def test_lost_checkout_write_ack_rolls_back_down_payment(isolated_checkout, monkeypatch, target):
    database, api = isolated_checkout
    method = "update" if target == "products" else "insert"
    original = getattr(FinancialOperation, method)

    async def fail_after_write(operation, collection, *args, **kwargs):
        await original(operation, collection, *args, **kwargs)
        if collection == target:
            raise RuntimeError("lost write acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(FinancialOperation, method, fail_after_write)
        failed = await api.post("/transactions", json=credit(down_payment_amount=3000, down_payment_method="cash"))
    assert failed.status_code == 500
    for name in ("transactions", "transaction_details", "accounts_receivable", "checkout_requests"):
        assert not database[name].documents
    assert database.products.documents[0]["stock"] == 5
    assert_clean(database)
    retry = await api.post("/transactions", json=credit(down_payment_amount=3000, down_payment_method="cash"))
    assert retry.status_code == 201, retry.text
    assert database.accounts_receivable.documents[0]["paid_amount"] == 3000
    assert_clean(database)


async def test_return_requires_refund_confirmation_for_down_payment(isolated_checkout):
    database, api = isolated_checkout
    created = await api.post("/transactions", json=credit(down_payment_amount=3000, down_payment_method="qris"))
    tx = created.json()
    url = "/transactions/" + tx["id"] + "/return"
    rejected = await api.post(url, json={})
    assert rejected.status_code == 422
    assert database.accounts_receivable.documents[0]["status"] == "partial"
    returned = await api.post(url, json={"refund_confirmed": True, "reason": "Barang dikembalikan"})
    assert returned.status_code == 200, returned.text
    assert returned.json()["refund_amount"] == returned.json()["down_payment_amount"] == 3000
    debt = database.accounts_receivable.documents[0]
    assert debt["status"] == "void" and debt["remaining"] == 0 and debt["paid_amount"] == 3000
    assert database.products.documents[0]["stock"] == 5
    assert_clean(database)
