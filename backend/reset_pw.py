import asyncio, os
from lib.db import db
from lib.auth import hash_password

async def main():
    updates = {"admin": "admin123", "kasir": "kasir123"}
    for username, pw in updates.items():
        res = await db.users.update_one({"username": username}, {"$set": {"password_hash": hash_password(pw)}})
        print(username, "matched", res.matched_count, "modified", res.modified_count)
    # clear any brute-force lockout records
    await db.login_attempts.delete_many({})
    print("login_attempts cleared")

asyncio.run(main())
