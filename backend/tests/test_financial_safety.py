"""Real Mongo regressions. Every test owns a random disposable database.

Run: python -m pytest tests/test_financial_safety.py
TEST_MONGO_URL defaults to local Mongo; production DB_NAME is never used for writes.
"""

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.write_concern import WriteConcern

import server
from lib import db as database
from lib.auth import require_user
from lib.financial_operations import FinancialOperation, MARKER, financial_lock, recover_financial_operations
from lib.runtime_lock import single_writer


@pytest.fixture
async def isolated(monkeypatch):
    name = "bian_safety_test_" + uuid.uuid4().hex
    mongo_url = os.environ.get("TEST_MONGO_URL", "mongodb://127.0.0.1:27017")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
    await client.admin.command("ping")
    db = client.get_database(name, write_concern=WriteConcern(w=1, j=True))
    original = database.db
    for module in list(sys.modules.values()):
        if module and getattr(module, "__name__", "").startswith(("lib.", "routers.", "server")):
            if getattr(module, "db", None) is original:
                monkeypatch.setattr(module, "db", db)
    monkeypatch.setattr(financial_lock, "lock", asyncio.Lock())
    await database.ensure_indexes()
    user = {"id": "test-cashier", "username": "test-cashier", "name": "Test", "role": "kasir"}
    server.app.dependency_overrides[require_user] = lambda: user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app, raise_app_exceptions=False),
            base_url="http://test/api",
        ) as api:
            yield db, api, user, mongo_url
    finally:
        server.app.dependency_overrides.clear()
        # Only this fixture's generated database is ever dropped.
        assert name.startswith("bian_safety_test_") and db.name == name
        await client.drop_database(name)
        client.close()


async def product(db, stock=5, price=10000):
    pid = uuid.uuid4().hex
    await db.products.insert_one({
        "id": pid, "name": "Test tyre", "sku": pid, "type": "barang",
        "stock": stock, "cost_price": 5000, "selling_price": price,
        "brand": "", "size": "", "service_fee": 0,
    })
    return pid


def checkout(pid, **kwargs):
    return {"items": [{"product_id": pid, "qty": 1}], "payment_method": "cash", **kwargs}


async def assert_clean(db):
    assert await db.financial_operations.count_documents({}) == 0
    for collection in await db.list_collection_names():
        assert await db[collection].count_documents({MARKER: {"$exists": True}}) == 0


async def test_concurrent_checkout_cannot_oversell(isolated):
    db, api, _, _ = isolated
    pid = await product(db, stock=1)
    responses = await asyncio.gather(*[api.post("/transactions", json=checkout(pid)) for _ in range(8)])
    assert sorted(r.status_code for r in responses) == [201] + [400] * 7
    assert (await db.products.find_one({"id": pid}))["stock"] == 0
    assert await db.transactions.count_documents({}) == 1
    assert await db.transaction_details.count_documents({}) == 1
    await assert_clean(db)


async def test_checkout_retry_is_idempotent_and_rejects_changed_payload(isolated):
    db, api, _, _ = isolated
    pid = await product(db)
    body = checkout(pid, request_id=uuid.uuid4().hex)
    first, retry = await asyncio.gather(*[api.post("/transactions", json=body) for _ in range(2)])
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"]
    assert (await db.products.find_one({"id": pid}))["stock"] == 4
    body["items"][0]["qty"] = 2
    assert (await api.post("/transactions", json=body)).status_code == 409
    await assert_clean(db)


@pytest.mark.parametrize("target", ["transactions", "transaction_details", "products", "accounts_receivable", "checkout_requests"])
async def test_checkout_rolls_back_even_after_write_ack_is_lost(isolated, monkeypatch, target):
    db, api, _, _ = isolated
    pid = await product(db)
    await db.customers.insert_one({"id": "customer", "name": "Customer"})
    method = "update" if target == "products" else "insert"
    original = getattr(FinancialOperation, method)

    async def fail_after_write(self, collection, *args, **kwargs):
        result = await original(self, collection, *args, **kwargs)
        if collection == target:
            raise RuntimeError("simulated lost acknowledgement")
        return result

    monkeypatch.setattr(FinancialOperation, method, fail_after_write)
    body = checkout(pid, payment_method="credit", customer_id="customer", due_date="2099-01-01", request_id=uuid.uuid4().hex)
    assert (await api.post("/transactions", json=body)).status_code == 500
    assert (await db.products.find_one({"id": pid}))["stock"] == 5
    for collection in ("transactions", "transaction_details", "accounts_receivable", "checkout_requests"):
        assert await db[collection].count_documents({}) == 0
    await assert_clean(db)


async def test_conditional_stock_write_rolls_back_prior_items(isolated, monkeypatch):
    db, api, _, _ = isolated
    first, second = await product(db), await product(db)
    original = FinancialOperation.update

    async def simulate_external_stock_change(self, collection, document_id, *args, **kwargs):
        if collection == "products" and document_id == second:
            await db.products.update_one({"id": second}, {"$set": {"stock": 0}})
        return await original(self, collection, document_id, *args, **kwargs)

    monkeypatch.setattr(FinancialOperation, "update", simulate_external_stock_change)
    response = await api.post("/transactions", json={
        "items": [{"product_id": p, "qty": 1} for p in (first, second)], "payment_method": "cash",
    })
    assert response.status_code == 409
    assert (await db.products.find_one({"id": first}))["stock"] == 5
    assert (await db.products.find_one({"id": second}))["stock"] == 0
    assert await db.transactions.count_documents({}) == 0
    await assert_clean(db)


async def test_cashier_return_once_and_expense_delete_still_allowed(isolated):
    db, api, _, _ = isolated
    pid = await product(db)
    created = await api.post("/transactions", json=checkout(pid))
    assert created.status_code == 201
    url = f"/transactions/{created.json()['id']}/return"
    assert (await api.post(url, json={})).status_code == 422
    responses = await asyncio.gather(*[api.post(url, json={"refund_confirmed": True}) for _ in range(2)])
    assert sorted(r.status_code for r in responses) == [200, 400]
    assert (await db.products.find_one({"id": pid}))["stock"] == 5
    await db.expenses.insert_one({"id": "expense"})
    assert (await api.delete("/expenses/expense")).status_code == 200
    assert (await api.delete(f"/products/{pid}")).status_code == 403
    await assert_clean(db)


@pytest.mark.parametrize("target", ["products", "transactions", "accounts_receivable"])
async def test_failed_return_restores_stock_transaction_and_debt(isolated, monkeypatch, target):
    db, api, _, _ = isolated
    pid = await product(db)
    await db.customers.insert_one({"id": "customer", "name": "Customer"})
    created = await api.post("/transactions", json=checkout(pid, payment_method="credit", customer_id="customer", due_date="2099-01-01"))
    assert created.status_code == 201
    txid = created.json()["id"]
    before = await db.accounts_receivable.find_one({"transaction_id": txid})
    original = FinancialOperation.update

    async def fail(self, collection, *args, **kwargs):
        await original(self, collection, *args, **kwargs)
        if collection == target:
            raise RuntimeError("simulated return failure")

    monkeypatch.setattr(FinancialOperation, "update", fail)
    assert (await api.post(f"/transactions/{txid}/return", json={})).status_code == 500
    assert (await db.products.find_one({"id": pid}))["stock"] == 4
    assert (await db.transactions.find_one({"id": txid}))["status"] == "completed"
    assert await db.accounts_receivable.find_one({"transaction_id": txid}) == before
    await assert_clean(db)


@pytest.mark.parametrize("fail", [False, True])
async def test_stock_in_and_payable_are_saved_or_rolled_back_together(isolated, monkeypatch, fail):
    db, api, _, _ = isolated
    pid = await product(db)
    await db.suppliers.insert_one({"id": "supplier", "name": "Supplier"})
    if fail:
        original = FinancialOperation.insert

        async def fail_payable(self, collection, *args, **kwargs):
            await original(self, collection, *args, **kwargs)
            if collection == "accounts_payable":
                raise RuntimeError("simulated payable failure")

        monkeypatch.setattr(FinancialOperation, "insert", fail_payable)
    response = await api.post("/stock-in", json={
        "supplier_id": "supplier", "invoice_number": "SUP-1", "due_date": "2099-01-01",
        "items": [{"product_id": pid, "qty": 2, "cost_price": 6000}],
    })
    assert response.status_code == (500 if fail else 201), response.text
    p = await db.products.find_one({"id": pid})
    assert (p["stock"], p["cost_price"]) == ((5, 5000) if fail else (7, 6000))
    assert await db.stock_in.count_documents({}) == (0 if fail else 1)
    assert await db.accounts_payable.count_documents({}) == (0 if fail else 1)
    await assert_clean(db)


@pytest.mark.parametrize("committed", [False, True])
async def test_recovery_after_process_exit_is_idempotent(isolated, committed):
    db, _, _, mongo_url = isolated
    pid = await product(db)
    script = '''
import asyncio, os
from lib.financial_operations import FinancialOperation
from lib.db import db
async def main():
    op = await FinancialOperation("crash-test").__aenter__()
    await op.insert("transactions", {"id": "interrupted", "status": "completed"})
    await op.update("products", os.environ["TEST_PRODUCT"], {"$inc": {"stock": -1}})
    if os.environ["TEST_COMMITTED"] == "True":
        await db.financial_operations.update_one({"_id": op.record["_id"]}, {"$set": {"committed": True}})
    os._exit(0)
asyncio.run(main())
'''
    env = {**os.environ, "MONGO_URL": mongo_url, "DB_NAME": db.name,
           "TEST_PRODUCT": pid, "TEST_COMMITTED": str(committed)}
    result = await asyncio.to_thread(subprocess.run, [sys.executable, "-c", script],
                                    cwd=Path(__file__).parents[1], env=env, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode()
    assert await db.financial_operations.count_documents({}) == 1
    await recover_financial_operations()
    await recover_financial_operations()
    assert (await db.products.find_one({"id": pid}))["stock"] == (4 if committed else 5)
    assert await db.transactions.count_documents({}) == (1 if committed else 0)
    await assert_clean(db)


async def test_runtime_rejects_second_writer_and_releases_lock(isolated):
    db, _, _, _ = isolated
    with single_writer(db.name):
        with pytest.raises(RuntimeError, match="satu worker"):
            with single_writer(db.name):
                pass
    with single_writer(db.name):
        pass


async def test_zero_value_credit_is_rejected_without_writes(isolated):
    db, api, _, _ = isolated
    pid = await product(db, price=0)
    await db.customers.insert_one({"id": "customer", "name": "Customer"})
    response = await api.post("/transactions", json=checkout(pid, payment_method="credit", customer_id="customer", due_date="2099-01-01"))
    assert response.status_code == 422
    assert await db.transactions.count_documents({}) == 0
    assert (await db.products.find_one({"id": pid}))["stock"] == 5
    await assert_clean(db)


async def test_partial_payment_then_return_voids_debt_and_refunds_paid_amount(isolated):
    db, api, _, _ = isolated
    from lib.dates import today_iso
    pid = await product(db)
    await db.customers.insert_one({"id": "customer", "name": "Customer"})
    created = await api.post("/transactions", json=checkout(pid, payment_method="credit", customer_id="customer", due_date="2099-01-01"))
    txid = created.json()["id"]
    debt = await db.accounts_receivable.find_one({"transaction_id": txid})
    paid = await api.post(f"/receivables/{debt['id']}/pay", json={
        "amount": 4000, "payment_date": today_iso(), "request_id": uuid.uuid4().hex,
    })
    assert paid.status_code == 200, paid.text
    assert paid.json()["remaining"] == 6000
    url = f"/transactions/{txid}/return"
    assert (await api.post(url, json={})).status_code == 422
    returned = await api.post(url, json={"refund_confirmed": True})
    assert returned.status_code == 200, returned.text
    assert returned.json()["refund_amount"] == 4000
    debt = await db.accounts_receivable.find_one({"id": debt["id"]})
    assert (debt["status"], debt["remaining"], debt["paid_amount"], len(debt["payments"])) == ("void", 0, 4000, 1)
    assert (await db.products.find_one({"id": pid}))["stock"] == 5
    await assert_clean(db)


async def test_reads_wait_for_failed_checkout_rollback(isolated, monkeypatch):
    db, api, _, _ = isolated
    pid = await product(db)
    entered, release = asyncio.Event(), asyncio.Event()
    original = FinancialOperation.update

    async def interrupted(self, collection, *args, **kwargs):
        await original(self, collection, *args, **kwargs)
        if collection == "products":
            entered.set()
            await release.wait()
            raise RuntimeError("checkout interrupted before commit")

    monkeypatch.setattr(FinancialOperation, "update", interrupted)
    write = asyncio.create_task(api.post("/transactions", json=checkout(pid)))
    await asyncio.wait_for(entered.wait(), 5)
    read = asyncio.create_task(api.get(f"/products/{pid}"))
    try:
        await asyncio.sleep(0.05)
        assert not read.done()
    finally:
        release.set()
    assert (await write).status_code == 500
    result = await read
    assert result.status_code == 200
    assert result.json()["stock"] == 5
    await assert_clean(db)


async def test_commit_ack_loss_preserves_success_for_retry(isolated, monkeypatch):
    db, api, _, _ = isolated
    from motor.motor_asyncio import AsyncIOMotorCollection
    pid = await product(db)
    original = AsyncIOMotorCollection.update_one
    failed = False

    async def lose_commit_ack(collection, query, update, *args, **kwargs):
        nonlocal failed
        result = await original(collection, query, update, *args, **kwargs)
        if collection.database.name == db.name and collection.name == "financial_operations" and update.get("$set", {}).get("committed") and not failed:
            failed = True
            raise RuntimeError("commit acknowledgement lost")
        return result

    monkeypatch.setattr(AsyncIOMotorCollection, "update_one", lose_commit_ack)
    body = checkout(pid, request_id=uuid.uuid4().hex)
    assert (await api.post("/transactions", json=body)).status_code == 500
    retry = await api.post("/transactions", json=body)
    assert retry.status_code == 201, retry.text
    assert await db.transactions.count_documents({}) == 1
    assert (await db.products.find_one({"id": pid}))["stock"] == 4
    await assert_clean(db)


async def test_interrupted_rollback_can_resume_without_double_stock_restore(isolated, monkeypatch):
    db, _, _, _ = isolated
    from motor.motor_asyncio import AsyncIOMotorCollection
    pid = await product(db)
    operation = await FinancialOperation("test-recovery").__aenter__()
    await operation.insert("transactions", {"id": "interrupted"})
    await operation.update("products", pid, {"$inc": {"stock": -1}})
    original = AsyncIOMotorCollection.delete_one

    async def fail_delete(collection, *args, **kwargs):
        if collection.database.name == db.name and collection.name == "transactions":
            raise RuntimeError("database unavailable during rollback")
        return await original(collection, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(AsyncIOMotorCollection, "delete_one", fail_delete)
        with pytest.raises(RuntimeError):
            await recover_financial_operations()
    assert (await db.products.find_one({"id": pid}))["stock"] == 5
    await recover_financial_operations()
    assert (await db.products.find_one({"id": pid}))["stock"] == 5
    assert await db.transactions.count_documents({}) == 0
    await assert_clean(db)


async def test_note_saves_sku_tender_and_change_for_reprint(isolated):
    db, api, _, _ = isolated
    pid = await product(db)
    body = checkout(pid, cash_received=20000, request_id=uuid.uuid4().hex)
    response = await api.post("/transactions", json=body)
    assert response.status_code == 201, response.text
    result = response.json()
    assert (result["total_amount"], result["cash_received"], result["change_amount"]) == (10000, 20000, 10000)
    assert result["details"][0]["product_sku"] == pid
    await db.products.update_one({"id": pid}, {"$set": {"sku": "new-code", "selling_price": 30000}})
    reprint = (await api.get(f"/transactions/{result['id']}")).json()
    assert reprint["details"][0]["product_sku"] == pid
    assert (reprint["total_amount"], reprint["cash_received"], reprint["change_amount"]) == (10000, 20000, 10000)
    assert (await api.post("/transactions", json=body)).json()["id"] == result["id"]
    await assert_clean(db)


@pytest.mark.parametrize("received", [0, 9999, -1, 1e13])
async def test_insufficient_or_invalid_cash_does_not_change_stock(isolated, received):
    db, api, _, _ = isolated
    pid = await product(db)
    response = await api.post("/transactions", json=checkout(pid, cash_received=received))
    assert response.status_code == 422, response.text
    assert (await db.products.find_one({"id": pid}))["stock"] == 5
    assert await db.transactions.count_documents({}) == 0
    await assert_clean(db)


async def test_old_transaction_does_not_invent_cash_or_sku(isolated):
    db, api, _, _ = isolated
    pid = await product(db)
    created = (await api.post("/transactions", json=checkout(pid))).json()
    await db.transactions.update_one({"id": created["id"]}, {"$unset": {"cash_received": "", "change_amount": ""}})
    await db.transaction_details.update_many({"transaction_id": created["id"]}, {"$unset": {"product_sku": ""}})
    result = (await api.get(f"/transactions/{created['id']}")).json()
    assert result["cash_received"] is None and result["change_amount"] is None
    assert result["details"][0]["product_sku"] is None


async def test_real_auth_cookie_logout_and_admin_boundary(isolated, monkeypatch):
    db, api, _, _ = isolated
    from lib import auth
    server.app.dependency_overrides.clear()
    monkeypatch.setattr(auth, "COOKIE_SECURE", False)
    password = uuid.uuid4().hex
    await db.users.insert_one({
        "id": "cashier", "username": "cashier", "name": "Test", "role": "kasir",
        "password_hash": auth.hash_password(password),
    })
    assert (await api.get("/products")).status_code == 401
    login = await api.post("/auth/login", json={"username": "cashier", "password": password})
    assert login.status_code == 200
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert "password_hash" not in login.json()
    assert (await api.get("/products")).status_code == 200
    assert (await api.get("/reports/monthly")).status_code == 403
    assert (await api.post("/auth/logout")).status_code == 200
    assert (await api.get("/products")).status_code == 401


async def test_credit_checkout_rejects_cash_tender(isolated):
    db, api, _, _ = isolated
    pid = await product(db)
    await db.customers.insert_one({"id": "customer", "name": "Customer"})
    response = await api.post("/transactions", json=checkout(pid, payment_method="credit", customer_id="customer", due_date="2099-01-01", cash_received=10000))
    assert response.status_code == 422
    assert await db.transactions.count_documents({}) == 0
    assert (await db.products.find_one({"id": pid}))["stock"] == 5
