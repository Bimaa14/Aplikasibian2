"""Seed data bengkel: users, produk, pelanggan, distributor, transaksi, piutang, hutang, pengeluaran.

Idempotent — dilewati jika data users sudah ada. Jalankan: cd /app/backend && python seed.py
"""

import asyncio
import os
import uuid
from datetime import date as date_cls, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from lib.auth import hash_password
from lib.db import db, ensure_indexes
from lib.dates import today_iso

USERS = [
    {"name": "Admin Bengkel", "username": "admin", "password": "admin123", "role": "admin"},
    {"name": "Kasir Bengkel", "username": "kasir", "password": "kasir123", "role": "kasir"},
]

PRODUCTS = [
    {"type": "barang", "sku": "BAN-001", "name": "Ban Mobil GT Champiro GX2", "brand": "GT Radial", "size": "185/65 R15", "stock": 24, "cost_price": 385000, "selling_price": 465000, "service_fee": 0},
    {"type": "barang", "sku": "BAN-002", "name": "Ban Mobil FDR Sport XR1", "brand": "FDR", "size": "165/70 R14", "stock": 18, "cost_price": 295000, "selling_price": 355000, "service_fee": 0},
    {"type": "barang", "sku": "BAN-003", "name": "Ban Mobil Corsa R183", "brand": "Corsa", "size": "195/55 R16", "stock": 10, "cost_price": 520000, "selling_price": 625000, "service_fee": 0},
    {"type": "barang", "sku": "BAN-004", "name": "Ban Motor IRC NR53", "brand": "IRC", "size": "90/80-14", "stock": 30, "cost_price": 185000, "selling_price": 235000, "service_fee": 0},
    {"type": "barang", "sku": "OLI-001", "name": "Oli Mesin Castrol Magnatec 10W-40 (4L)", "brand": "Castrol", "size": "4L", "stock": 40, "cost_price": 235000, "selling_price": 285000, "service_fee": 0},
    {"type": "barang", "sku": "OLI-002", "name": "Oli Motor Enduro Racing 20W-50 (1L)", "brand": "Enduro", "size": "1L", "stock": 60, "cost_price": 55000, "selling_price": 72000, "service_fee": 0},
    {"type": "barang", "sku": "OLI-003", "name": "Oli Mesin Shell Helix HX8 5W-30 (4L)", "brand": "Shell", "size": "4L", "stock": 15, "cost_price": 320000, "selling_price": 385000, "service_fee": 0},
    {"type": "barang", "sku": "SPR-001", "name": "Kampas Rem Depan (Set)", "brand": "NIBK", "size": "", "stock": 3, "cost_price": 95000, "selling_price": 150000, "service_fee": 0},
    {"type": "barang", "sku": "SPR-002", "name": "Busi NGK Iridium", "brand": "NGK", "size": "", "stock": 50, "cost_price": 45000, "selling_price": 68000, "service_fee": 0},
    {"type": "barang", "sku": "SPR-003", "name": "Filter Oli Toyota", "brand": "Toyota", "size": "", "stock": 25, "cost_price": 32000, "selling_price": 55000, "service_fee": 0},
    {"type": "barang", "sku": "SPR-004", "name": "Aki Kering Yuasa 12V 45Ah", "brand": "Yuasa", "size": "45Ah", "stock": 8, "cost_price": 690000, "selling_price": 850000, "service_fee": 0},
    {"type": "jasa", "sku": "JSV-001", "name": "Tambal Ban Mobil", "brand": "", "size": "", "stock": 0, "cost_price": 0, "selling_price": 35000, "service_fee": 15000},
    {"type": "jasa", "sku": "JSV-002", "name": "Ganti Ban + Balancing", "brand": "", "size": "", "stock": 0, "cost_price": 0, "selling_price": 60000, "service_fee": 25000},
    {"type": "jasa", "sku": "JSV-003", "name": "Ganti Oli Mesin", "brand": "", "size": "", "stock": 0, "cost_price": 0, "selling_price": 50000, "service_fee": 20000},
    {"type": "jasa", "sku": "JSV-004", "name": "Servis Rutin Ringan", "brand": "", "size": "", "stock": 0, "cost_price": 0, "selling_price": 120000, "service_fee": 45000},
    {"type": "jasa", "sku": "JSV-005", "name": "Servis AC / Tambah Freon", "brand": "", "size": "", "stock": 0, "cost_price": 0, "selling_price": 95000, "service_fee": 30000},
]

CUSTOMERS = [
    {"name": "Budi Santoso", "phone": "081234567801", "address": "Jl. Merdeka No. 12, Jakarta Timur"},
    {"name": "Siti Rahayu", "phone": "081234567802", "address": "Jl. Melati No. 8, Depok"},
    {"name": "Agus Wijaya", "phone": "081234567803", "address": "Jl. Kenanga No. 45, Bekasi"},
    {"name": "PT Trans Logistik Nusantara", "phone": "0215550123", "address": "Kawasan Industri Pulogadung Blok F-9, Jakarta"},
    {"name": "Dewi Lestari", "phone": "081234567805", "address": "Jl. Cempaka Putih No. 3, Jakarta Pusat"},
]

SUPPLIERS = [
    {"name": "PT Gajah Tunggal Distribusi", "phone": "0218502050", "address": "Jl. Gatot Subroto Kav. 7, Jakarta"},
    {"name": "CV Sumber Oli Nusantara", "phone": "0216392214", "address": "Jl. Pangeran Jayakarta No. 55, Jakarta"},
    {"name": "Toko Aksesoris Jaya Makmur", "phone": "0216004455", "address": "Pasar Gembrong Blok C, Jakarta Timur"},
]

# (kategori, jumlah, deskripsi, hari lalu) — skala mingguan agar seimbang dengan volume penjualan seed
EXPENSES = [
    ("Gaji Montir", 1200000, "Gaji 3 montir - minggu ini", 1),
    ("Operasional", 400000, "Listrik dan air bengkel", 2),
    ("Operasional", 350000, "Internet dan telepon", 3),
    ("Lainnya", 85000, "Alat tulis dan nota kwitansi", 0),
]

# nomor polisi contoh — dirotasi ke transaksi agar Riwayat Kendaraan terisi
PLATES = [
    "B 1234 XYZ", "B 5678 ABC", "D 9012 JKL", "B 3344 TRU", "F 7788 MNO",
]

# transaksi contoh: (hari_lalu, nama_pelanggan|None, metode, due_offset_hari|None, status, [(sku, qty)])
TRANSACTIONS = [
    (5, "Budi Santoso", "cash", None, "completed", [("BAN-001", 2), ("OLI-002", 1)]),
    (4, None, "cash", None, "completed", [("JSV-001", 1)]),
    (3, "Siti Rahayu", "cash", None, "completed", [("OLI-001", 1), ("JSV-003", 1)]),
    (2, "Agus Wijaya", "credit", 14, "completed", [("BAN-002", 2)]),
    (2, "Dewi Lestari", "cash", None, "returned", [("SPR-004", 1)]),
    (8, "PT Trans Logistik Nusantara", "credit", -5, "completed", [("BAN-003", 4)]),
    (0, None, "cash", None, "completed", [("JSV-004", 1), ("SPR-002", 2)]),
]


def _build_tx(products_by_sku, customer, spec, counters):
    items = [(products_by_sku[sku], qty) for sku, qty in spec["items"]]
    details = []
    total_amount = barang_amount = jasa_amount = total_cost = service_fee = total_profit = 0.0
    for p, qty in items:
        price = p["selling_price"]
        subtotal = price * qty
        if p["type"] == "barang":
            cost, fee = p["cost_price"], 0
            profit = (price - cost) * qty
            barang_amount += subtotal
            total_cost += cost * qty
        else:
            cost, fee = 0, p["service_fee"]
            profit = (price - fee) * qty
            jasa_amount += subtotal
            service_fee += fee * qty
        total_amount += subtotal
        total_profit += profit
        details.append({
            "id": str(uuid.uuid4()),
            "transaction_id": "",
            "product_id": p["id"],
            "product_name": p["name"],
            "product_type": p["type"],
            "qty": qty,
            "price": price,
            "cost_price": cost,
            "service_fee": fee,
            "subtotal": subtotal,
        })

    now_local = datetime.now(ZoneInfo(os.environ.get("APP_TZ", "UTC"))) - timedelta(days=spec["day"])
    date_key = now_local.strftime("%Y-%m-%d")
    counters[date_key] = counters.get(date_key, 0) + 1
    yymmdd = date_key.replace("-", "")[2:]
    tx = {
        "id": str(uuid.uuid4()),
        "invoice_number": f"INV-{yymmdd}-{counters[date_key]:04d}",
        "date": now_local,
        "date_key": date_key,
        "customer_id": customer["id"] if customer else None,
        "customer_name": customer["name"] if customer else None,
        "payment_method": spec["payment_method"],
        "total_amount": total_amount,
        "barang_amount": barang_amount,
        "jasa_amount": jasa_amount,
        "total_cost": total_cost,
        "service_fee": service_fee,
        "total_profit": total_profit,
        "status": spec["status"],
        "due_date": (today_iso_date() + timedelta(days=spec["due_offset"])).isoformat() if spec["due_offset"] is not None else None,
        "vehicle_plate": spec.get("plate"),
    }
    for d in details:
        d["transaction_id"] = tx["id"]
    return tx, details


def today_iso_date():
    """Hari ini (APP_TZ) sebagai objek date — .isoformat() menghasilkan YYYY-MM-DD murni (tanpa T00:00:00)."""
    return date_cls.fromisoformat(today_iso())


async def main():
    await ensure_indexes()
    if await db.users.count_documents({}) > 0:
        print("Seed dilewati — data sudah ada (koleksi users tidak kosong).")
        return

    users = [
        {"id": str(uuid.uuid4()), "name": u["name"], "username": u["username"],
         "role": u["role"], "password_hash": hash_password(u["password"])}
        for u in USERS
    ]
    await db.users.insert_many(users)

    product_docs = [{"id": str(uuid.uuid4()), **p} for p in PRODUCTS]
    await db.products.insert_many(product_docs)
    products_by_sku = {p["sku"]: p for p in product_docs}

    customer_docs = [{"id": str(uuid.uuid4()), **c} for c in CUSTOMERS]
    await db.customers.insert_many(customer_docs)
    customers_by_name = {c["name"]: c for c in customer_docs}

    supplier_docs = [{"id": str(uuid.uuid4()), **s} for s in SUPPLIERS]
    await db.suppliers.insert_many(supplier_docs)
    suppliers_by_name = {s["name"]: s for s in supplier_docs}

    async def commit(items: list, spec_extra: dict) -> None:
        customer = customers_by_name.get(spec_extra["customer_name"]) if spec_extra["customer_name"] else None
        tx, details = _build_tx(products_by_sku, customer, spec_extra, counters)
        await db.transactions.insert_one(tx)
        await db.transaction_details.insert_many(details)
        if spec_extra["status"] != "returned":
            for sku, qty in items:
                if products_by_sku[sku]["type"] == "barang":
                    await db.products.update_one({"id": products_by_sku[sku]["id"]}, {"$inc": {"stock": -qty}})
        if spec_extra["payment_method"] == "credit":
            receivables.append({
                "id": str(uuid.uuid4()),
                "transaction_id": tx["id"],
                "invoice_number": tx["invoice_number"],
                "customer_id": tx["customer_id"],
                "customer_name": tx["customer_name"],
                "amount": tx["total_amount"],
                "due_date": tx["due_date"],
                "status": "unpaid",
            })

    counters: dict = {}
    receivables = []
    for i, spec in enumerate(TRANSACTIONS):
        day, customer_name, method, due_offset, status, items = spec
        await commit(items, {
            "day": day, "customer_name": customer_name, "payment_method": method,
            "due_offset": due_offset, "status": status, "items": items,
            "plate": PLATES[i % len(PLATES)],
        })

    # transaksi ritel harian (deterministik): 3 per hari selama 7 hari terakhir
    COMBOS = [
        [("BAN-001", 4)],
        [("BAN-004", 1), ("JSV-002", 1)],
        [("OLI-001", 1), ("JSV-003", 1)],
        [("SPR-002", 2), ("SPR-003", 1)],
        [("JSV-001", 2)],
        [("OLI-002", 4)],
        [("SPR-001", 1), ("JSV-004", 1)],
        [("BAN-002", 2), ("OLI-002", 2)],
        [("BAN-003", 2)],
        [("JSV-005", 1), ("OLI-002", 1)],
    ]
    CUSTOMER_ROTATION = [None, "Budi Santoso", None, "Siti Rahayu", None, "Agus Wijaya", None]
    for idx in range(21):
        combo = COMBOS[idx % len(COMBOS)]
        method = "credit" if idx % 5 == 3 else "cash"
        cust_name = CUSTOMER_ROTATION[idx % len(CUSTOMER_ROTATION)]
        if method == "credit" and cust_name is None:
            cust_name = "Budi Santoso"  # aturan bisnis: kredit wajib punya pelanggan
        await commit(combo, {
            "day": 6 - idx // 3, "customer_name": cust_name,
            "payment_method": method, "due_offset": 10 if method == "credit" else None,
            "status": "completed", "items": combo,
            "plate": PLATES[idx % len(PLATES)] if idx % 3 != 2 else None,
        })

    if receivables:
        await db.accounts_receivable.insert_many(receivables)

    # hutang distributor: satu lewat jatuh tempo, satu menempuh 2 hari lagi, satu jauh
    payables = []
    for name, invoice, amount, due_offset in [
        ("PT Gajah Tunggal Distribusi", "GT/PO/2601", 12500000, -3),
        ("CV Sumber Oli Nusantara", "SON/INV/8812", 6750000, 2),
        ("Toko Aksesoris Jaya Makmur", "JM/INV/2210", 2100000, 20),
    ]:
        payables.append({
            "id": str(uuid.uuid4()),
            "supplier_id": suppliers_by_name[name]["id"],
            "supplier_name": name,
            "invoice_number": invoice,
            "amount": amount,
            "due_date": (today_iso_date() + timedelta(days=due_offset)).isoformat(),
            "status": "unpaid",
        })
    await db.accounts_payable.insert_many(payables)

    expense_docs = [
        {"id": str(uuid.uuid4()),
         "date": (today_iso_date() - timedelta(days=days_ago)).isoformat(),
         "amount": amount, "category": category, "description": description}
        for category, amount, description, days_ago in EXPENSES
    ]
    await db.expenses.insert_many(expense_docs)

    for name, count in [
        ("users", len(users)), ("produk", len(product_docs)), ("pelanggan", len(customer_docs)),
        ("distributor", len(supplier_docs)), ("transaksi", len(TRANSACTIONS)),
        ("piutang", len(receivables)), ("hutang", len(payables)), ("pengeluaran", len(expense_docs)),
    ]:
        print(f"  {name}: {count}")
    print("Seed selesai. Login: admin/admin123 (admin), kasir/kasir123 (kasir).")


if __name__ == "__main__":
    asyncio.run(main())
