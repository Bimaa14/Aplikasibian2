import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
client = AsyncIOMotorClient('mongodb://localhost:27017')
db = client['aplikasi_bian']
async def main():
  print(f'Produk: {await db.products.count_documents({})}')
  print(f'Transaksi: {await db.transactions.count_documents({})}')
asyncio.run(main())
