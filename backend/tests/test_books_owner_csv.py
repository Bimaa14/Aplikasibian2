"""Iteration 8: owner_summary in monthly + daily/monthly CSV endpoints + owner attribution e2e."""
import os
import re
import pytest
import requests
from tests.credentials import credentials

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login(username, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password}, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(**credentials("ADMIN"))


@pytest.fixture(scope="module")
def kasir():
    return _login(**credentials("CASHIER"))


# --- owner_summary in /monthly ---
class TestOwnerSummary:
    def test_monthly_aug_2026_owner_summary(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/monthly?month=2026-08", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "owner_summary" in d
        os_ = {o["owner"]: o for o in d["owner_summary"]}
        assert set(os_.keys()) == {"bian", "ibu", "unassigned"}
        assert os_["unassigned"]["omzet"] == 346172000, os_
        assert os_["unassigned"]["laba"] == 52797000, os_
        assert os_["bian"]["omzet"] == 0
        assert os_["bian"]["laba"] == 0
        assert os_["ibu"]["omzet"] == 0
        assert os_["ibu"]["laba"] == 0


# --- CSV endpoints ---
class TestCsvEndpoints:
    def test_daily_csv_admin_200_text_csv(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/daily/csv?date=2026-09-25", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "Laporan Kas Harian" in r.text

    def test_monthly_csv_admin_200_and_contains_ringkasan_pemilik(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/monthly/csv?month=2026-08", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "Ringkasan Per Pemilik" in r.text
        assert "Belum ditandai" in r.text or "Belum" in r.text

    def test_daily_csv_kasir_403(self, kasir):
        r = kasir.get(f"{BASE_URL}/api/books/daily/csv?date=2026-09-25", timeout=30)
        assert r.status_code == 403

    def test_monthly_csv_kasir_403(self, kasir):
        r = kasir.get(f"{BASE_URL}/api/books/monthly/csv?month=2026-08", timeout=30)
        assert r.status_code == 403

    def test_daily_csv_bad_date_422(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/daily/csv?date=2026/09/25", timeout=20)
        assert r.status_code == 422

    def test_monthly_csv_bad_month_422(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/monthly/csv?month=2026-8", timeout=20)
        assert r.status_code == 422


# --- E2E owner attribution ---
class TestOwnerAttributionE2E:
    def test_ibu_sale_increments_ibu_bucket(self, admin):
        import uuid
        sku = f"TEST-IBU-{uuid.uuid4().hex[:6].upper()}"
        # Create ibu product
        p = admin.post(f"{BASE_URL}/api/products", json={
            "type": "barang", "sku": sku, "name": "TEST Ibu Attribution",
            "owner": "ibu", "stock": 5, "cost_price": 5000, "selling_price": 10000,
        }, timeout=20)
        assert p.status_code == 201, p.text
        pid = p.json()["id"]

        # Get server "today" month via daily endpoint
        rday = admin.get(f"{BASE_URL}/api/books/daily", timeout=20).json()
        cur_month = rday["date"][:7]

        # Baseline
        base = admin.get(f"{BASE_URL}/api/books/monthly?month={cur_month}", timeout=30).json()
        base_ibu = {o["owner"]: o for o in base["owner_summary"]}["ibu"]

        tx_id = None
        try:
            # POS checkout (cash)
            tx = admin.post(f"{BASE_URL}/api/transactions", json={
                "items": [{"product_id": pid, "qty": 1}],
                "payment_method": "cash",
            }, timeout=20)
            assert tx.status_code == 201, tx.text
            txd = tx.json()
            tx_id = txd["id"]
            assert txd.get("invoice_number", "").startswith("INV-"), txd

            after = admin.get(f"{BASE_URL}/api/books/monthly?month={cur_month}", timeout=30).json()
            aft_ibu = {o["owner"]: o for o in after["owner_summary"]}["ibu"]

            # Expect omzet increased by 10000, laba by 5000 (Excel spreadsheet_profit)
            assert aft_ibu["omzet"] == base_ibu["omzet"] + 10000, (base_ibu, aft_ibu)
            assert aft_ibu["laba"] == base_ibu["laba"] + 5000, (base_ibu, aft_ibu)
        finally:
            # Cleanup: delete tx + its details + any receivable directly from Mongo, then product
            if tx_id:
                _cleanup_tx(tx_id)
            admin.delete(f"{BASE_URL}/api/products/{pid}")

        # Final safety check: counts back to 468 / 7505
        counts = _counts()
        assert counts["products"] == 468, counts
        assert counts["transactions"] == 7505, counts


def _cleanup_tx(tx_id: str):
    """Delete a POS transaction + its details + receivables directly from Mongo."""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]

    async def run():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        await db.transactions.delete_one({"id": tx_id})
        await db.transaction_details.delete_many({"transaction_id": tx_id})
        await db.receivables.delete_many({"transaction_id": tx_id})
        client.close()
    asyncio.run(run())


def _counts():
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]

    async def run():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        p = await db.products.count_documents({})
        t = await db.transactions.count_documents({})
        client.close()
        return {"products": p, "transactions": t}
    return asyncio.run(run())
