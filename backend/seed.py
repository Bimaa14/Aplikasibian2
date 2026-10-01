"""Initialize accounts only; never fabricate products, balances, or sales."""
import asyncio
import os
import uuid
from lib.db import db, ensure_indexes
from lib.auth import hash_password


async def main():
    await ensure_indexes()
    for role, prefix in [('admin', 'ADMIN'), ('kasir', 'CASHIER')]:
        username = os.environ[f'BOOTSTRAP_{prefix}_USERNAME']
        if not await db.users.find_one({'username': username}, {'_id': 0}):
            await db.users.insert_one({'id': str(uuid.uuid4()), 'username': username,
                                      'name': f'{role.title()} Perkasa Jaya', 'role': role,
                                      'password_hash': hash_password(os.environ[f'BOOTSTRAP_{prefix}_PASSWORD'])})
            print(f'Created {role} account (no business data seeded)')


if __name__ == '__main__':
    asyncio.run(main())