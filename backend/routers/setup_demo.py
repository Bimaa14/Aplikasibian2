"""One-time, browser-based creation of the fixed demo administrator account."""

import hmac
import html
import os

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse
from pymongo.errors import DuplicateKeyError

from lib.auth import hash_password
from lib.db import db

router = APIRouter(prefix="/setup-demo", tags=["setup"])

_ACCOUNT_ID = "demo-admin"
_USERNAME = "demo-admin"
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def _setup_key() -> bytes | None:
    value = os.environ.get("DEMO_SETUP_KEY")
    if value is None:
        return None
    encoded = value.encode("utf-8")
    return encoded if len(encoded) >= 32 else None


def _page(message: str = "") -> HTMLResponse:
    notice = f'<p class="notice">{html.escape(message)}</p>' if message else ""
    content = f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Setup akun demo admin</title>
<style>
body{{font:16px system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:0 1rem;line-height:1.5}}
label,input,button{{display:block;width:100%;box-sizing:border-box}}input,button{{padding:.7rem;margin:.3rem 0 1rem}}
.warning{{border-left:.3rem solid #b42318;padding:.7rem 1rem;background:#fff1f0}}.notice{{font-weight:700}}
</style>
</head>
<body>
<h1>Setup akun demo admin</h1>
<div class="warning"><strong>Peringatan:</strong> akun ini memiliki akses admin penuh. Akun dapat melihat dan mengubah data nyata. Gunakan hanya pada deployment demo yang aman.</div>
{notice}
<p>Form ini hanya membuat akun tetap <code>{html.escape(_USERNAME)}</code> satu kali. Akun yang sudah ada tidak diubah. Setup tidak melakukan login otomatis.</p>
<form method="post" action="/api/setup-demo" autocomplete="off">
<label for="secret">DEMO_SETUP_KEY</label>
<input id="secret" name="secret" type="password" required autocomplete="off">
<label for="password">Password baru (minimal 12 karakter, maksimal 72 byte UTF-8)</label>
<input id="password" name="password" type="password" minlength="12" required autocomplete="new-password">
<button type="submit">Buat akun demo admin</button>
</form>
</body>
</html>"""
    return HTMLResponse(content, headers=_SECURITY_HEADERS)


def _require_enabled() -> bytes:
    key = _setup_key()
    if key is None:
        raise HTTPException(status_code=404, detail="Not found")
    return key


@router.get("", response_class=HTMLResponse)
async def setup_demo_form() -> HTMLResponse:
    _require_enabled()
    return _page()


@router.post("", response_class=HTMLResponse)
async def setup_demo(secret: str = Form(...), password: str = Form(...)) -> HTMLResponse:
    expected = _require_enabled()
    if not hmac.compare_digest(secret.encode("utf-8"), expected):
        raise HTTPException(status_code=403, detail="Setup ditolak")

    password_bytes = password.encode("utf-8")
    if len(password) < 12 or len(password_bytes) > 72:
        return _page("Password harus minimal 12 karakter dan maksimal 72 byte UTF-8.")

    document = {
        "_id": _ACCOUNT_ID,
        "id": _ACCOUNT_ID,
        "name": "Demo Admin",
        "username": _USERNAME,
        "role": "admin",
        "password_hash": hash_password(password),
    }
    try:
        await db.users.insert_one(document)
    except DuplicateKeyError:
        return _page("Akun demo admin sudah ada. Tidak ada akun yang diubah.")

    return _page("Akun demo admin berhasil dibuat. Tutup halaman ini lalu login secara terpisah.")
