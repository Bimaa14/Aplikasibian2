"""Auth: login admin/kasir sets session cookie; protected routes 401 without session."""

import httpx

from tests.conftest import api_url


def test_login_admin_and_protected_route_without_session():
    # No cookie at all -> protected route rejects
    r = httpx.get(api_url("/products"), timeout=30.0)
    assert r.status_code == 401, f"expected 401 without session, got {r.status_code}: {r.text[:200]}"

    with httpx.Client(base_url=api_url(), timeout=30.0) as c:
        login = c.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert login.status_code == 200, f"admin login failed: {login.status_code} {login.text[:200]}"
        body = login.json()
        assert body["role"] == "admin"
        assert "bengkel_session" in c.cookies

        me = c.get("/auth/me")
        assert me.status_code == 200, f"/auth/me failed after login: {me.text[:200]}"
        assert me.json()["username"] == "admin"

        products = c.get("/products")
        assert products.status_code == 200, f"/products failed with session: {products.text[:200]}"


def test_login_kasir_and_wrong_password_rejected():
    with httpx.Client(base_url=api_url(), timeout=30.0) as c:
        login = c.post("/auth/login", json={"username": "kasir", "password": "kasir123"})
        assert login.status_code == 200, f"kasir login failed: {login.status_code} {login.text[:200]}"
        assert login.json()["role"] == "kasir"

        bad = c.post("/auth/login", json={"username": "kasir", "password": "wrong-password"})
        assert bad.status_code == 401, f"expected 401 for wrong password, got {bad.status_code}"
