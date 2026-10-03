"""Session auth: httpOnly cookie + server-side session docs in Mongo. Frontend never sees a token."""

import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response
from passlib.context import CryptContext

from lib.db import db

SESSION_COOKIE = "bengkel_session"
SESSION_TTL = timedelta(days=7)
# Cookie Secure flag: on by default; set COOKIE_SECURE=false only for plain-HTTP local dev.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax").strip().lower()
if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError("COOKIE_SAMESITE must be one of: lax, strict, none")
if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise RuntimeError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
# Brute-force guard on /auth/login
MAX_LOGIN_ATTEMPTS = 8
LOGIN_WINDOW = timedelta(minutes=15)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


async def create_session(user_id: str, response: Response) -> None:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + SESSION_TTL
    await db.sessions.insert_one(
        {"token": token, "user_id": user_id, "expires_at": expires_at}
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
        max_age=int(SESSION_TTL.total_seconds()),
    )


async def destroy_session(request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await db.sessions.delete_one({"token": token})
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )


async def require_user(request: Request) -> dict:
    """FastAPI dependency: 401 unless a live session cookie resolves to a user."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Belum login")
    session = await db.sessions.find_one({"token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Sesi tidak valid, silakan login")
    expires_at = session.get("expires_at")
    if expires_at is not None:
        # motor hands back naive datetimes — normalise before comparing (aware vs naive raises)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login kembali")
    user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Pengguna tidak ditemukan")
    user.pop("password_hash", None)
    return user


# --- Authorization (RBAC, single-tenant: dua tingkat hak akses admin & kasir) ---------------
# Satu titik keputusan. Role SELALU dibaca ulang dari dokumen user (via require_user), bukan
# dari cookie/body/query, sehingga role yang dicabut langsung berlaku pada request berikutnya.

async def require_admin(user: dict = Depends(require_user)) -> dict:
    """Hanya role 'admin'. Kasir mendapat 403 (boleh lihat menu, tidak boleh aksi ini)."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak — tindakan ini hanya untuk admin bengkel",
        )
    return user


async def register_login_failure(username: str) -> None:
    """Catat kegagalan login untuk rate limiting per username."""
    await db.login_attempts.insert_one(
        {"username": username, "at": datetime.now(timezone.utc)}
    )


async def clear_login_failures(username: str) -> None:
    await db.login_attempts.delete_many({"username": username})


async def assert_login_allowed(username: str) -> None:
    """Tolak sementara bila terlalu banyak percobaan login gagal dalam LOGIN_WINDOW."""
    since = datetime.now(timezone.utc) - LOGIN_WINDOW
    recent = await db.login_attempts.count_documents({"username": username, "at": {"$gte": since}})
    if recent >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan login gagal. Coba lagi dalam beberapa menit.",
        )
