"""Tests for /api/books/{daily,monthly,tax} — Laporan Kas & Pajak."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login(username: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {username}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin", "admin123")


@pytest.fixture(scope="module")
def kasir():
    return _login("kasir", "kasir123")


# --- Access control ---
class TestBooksAccessControl:
    def test_daily_admin_200(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/daily?date=2026-09-25", timeout=30)
        assert r.status_code == 200, r.text

    def test_monthly_admin_200(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/monthly?month=2026-08", timeout=30)
        assert r.status_code == 200, r.text

    def test_tax_admin_200(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/tax?month=2026-08", timeout=30)
        assert r.status_code == 200, r.text

    def test_daily_kasir_403(self, kasir):
        r = kasir.get(f"{BASE_URL}/api/books/daily?date=2026-09-25", timeout=30)
        assert r.status_code == 403, r.text

    def test_monthly_kasir_403(self, kasir):
        r = kasir.get(f"{BASE_URL}/api/books/monthly?month=2026-08", timeout=30)
        assert r.status_code == 403, r.text

    def test_tax_kasir_403(self, kasir):
        r = kasir.get(f"{BASE_URL}/api/books/tax?month=2026-08", timeout=30)
        assert r.status_code == 403, r.text


# --- Validation ---
class TestBooksValidation:
    def test_daily_bad_format(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/daily?date=2026/09/25", timeout=20)
        assert r.status_code == 422

    def test_monthly_bad_format(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/monthly?month=2026-8", timeout=20)
        assert r.status_code == 422

    def test_tax_bad_format(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/tax?month=202608", timeout=20)
        assert r.status_code == 422


# --- Business figures ---
class TestBooksFigures:
    def test_daily_2026_09_25(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/daily?date=2026-09-25", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["date"] == "2026-09-25"
        # figures from problem statement
        assert d["cash_sales"] == 15025000, d
        assert d["montir_fee"] == 125000, d
        assert d["expenses"] == 15000, d
        assert d["net_cash"] == 14885000, d
        # Consistency: net_cash = cash+recv-transfer-montir-expenses
        expected = (d["cash_sales"] + d["receivable_payments"]
                    - d["transfer_payments"] - d["montir_fee"] - d["expenses"])
        assert d["net_cash"] == expected

    def test_monthly_2026_08(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/monthly?month=2026-08", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["month"] == "2026-08"
        assert d["omzet"] == 346172000, d
        assert d["distributor_payment"] == 295583930, d
        assert d["expenses"] == 38780500, d
        assert d["sisa_aset"] == -503175032, d
        assert d["pph_final"] == 1730860, d
        # funding buckets
        assert d["funding"]["modal"]["label"] == "Uang Modal"
        assert d["funding"]["modal"]["total"] == 295583930
        assert d["funding"]["laba"]["label"] == "Uang Laba"
        # laba total = pengeluaran + pph + gaji
        assert d["funding"]["laba"]["total"] == d["expenses"] + d["pph_final"] + d["gaji"]

    def test_tax_2026_08(self, admin):
        r = admin.get(f"{BASE_URL}/api/books/tax?month=2026-08", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["month"] == "2026-08"
        assert d["rate"] == 0.005
        assert d["omzet_base"] == 346172000, d
        assert d["pph_final"] == 1730860, d
