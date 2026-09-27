# BengKasir / AplikasiBian — Perkasa Jaya POS + Pembukuan

## Original problem statement
Lanjutkan aplikasi BengKasir (POS bengkel ban & servis "Perkasa Jaya"). Stack tetap: React + TypeScript (Vite, Tailwind, shadcn/ui) · FastAPI · MongoDB. Pakai aplikasi kasir yang sudah ada, dan samakan pembukuan PERSIS dengan dua spreadsheet milik user. Impor produk/stok/transaksi/piutang/hutang dengan pratinjau sebelum simpan. Bahasa komunikasi: Indonesia (informal gua/lo OK).

## User choices (confirmed)
- Laporan acuan utama:
  - "Store Information System" → sheet REPORT: Total pendapatan TANPA oli; Modal/Laba/Spooring dipisah; NETT modal = Modal − Pembayaran Supplier; NETT laba = Laba − Pengeluaran; NETT spooring = Spooring; pembayaran piutang masuk berdasarkan tanggal pembayaran.
  - "09 - Laporan Bulan September" → sheet "Laporan Laba - Rugi": Total pendapatan TERMASUK oli; Sisa uang modal = Modal − Pembayaran Distributor; Laba bersih = Laba − Gaji − Pajak − Operasional − Pengeluaran; Sisa spooring = Spooring − Cicilan Mesin; Jumlah aset & Sisa aset.
- Impor: siapkan produk/stok/transaksi/piutang/hutang dengan pratinjau dulu sebelum disimpan.
- (Turn terbaru) Impor piutang & hutang SEKARANG, maksimalkan baris di sheet (boleh diedit/tambah nanti). Produk/stok ditunda dulu.
- Setuju tes otomatis menyeluruh.
- Windows XP offline: dibahas nanti (belum dikerjakan; stack sekarang tidak jalan di XP).

## Architecture (current, accurate)
- Backend FastAPI, semua route prefix `/api`, port 8001 (supervisor). Auth: session cookie httpOnly (`bengkel_session`), RBAC admin/kasir. Mongo via MONGO_URL/DB_NAME.
- Akun bootstrap dari backend/.env via seed.py: admin & kasir (kredensial di /app/memory/test_credentials.md).
- Routers: auth, products, customers, suppliers, transactions, receivables, payables, expenses, dashboard, stock_in, vehicles, reports (laba margin POS), excel_reports (laporan sesuai Excel), imports (pratinjau+commit), laravel_bundle.
- lib/excel_rules.py: `store_report()` & `september_report()` = formula literal dari sheet REPORT & Laba-Rugi.
- lib/workbooks.py: `dataset()` baca store-1.xlsx & september-1.xlsx dari WORKBOOK_DIR (/app/imports/workbooks), rekonsiliasi cell cached vs formula (semua selisih 0.0).
- lib/debts.py: `hydrate()` aging (0-30/31-60/61-90/90+, due_label), `pay()` cicilan idempotent + anti-overpayment, `migrate_returned_debts()` set piutang retur → void.
- Frontend pages: LoginPage, DashboardPage, PosPage, TransactionsPage, ProductsPage, CustomersPage, SuppliersPage, DebtPage (Piutang & Hutang), ExpensesPage, StockInPage, VehiclesPage, ReportsPage (Laba Margin POS), ExcelReportsPage (Laporan Excel), ImportPage (Impor & Pemeriksaan), LaravelBundlePage.

## Implemented & verified (2026-06)
- [2026-06 iter3] Impor RIWAYAT TRANSAKSI store ke ledger: 7505 transaksi (bulk_write ~3 dtk, product name→id di-preload). Baris qty0/amount0 nyampah dibuang. Laporan LIVE bulan lampau (2026-01..09) kini cocok 0.0 dengan preview/spreadsheet.
- [2026-06 iter3] Impor PRODUK & STOK store: 468 produk (dari 473; 5 ditahan = nama ganda perlu merge manual). Stok negatif/pecahan di-clamp ke 0 + catatan non-blokir; kategori kosong default TIRE. Sumber stok = DATABASE Store.
- [2026-06 iter3] KWITANSI CICILAN cetak: tombol per pembayaran di riwayat Piutang/Hutang (receipt.ts + terbilang). Teruji: popup berisi 'KWITANSI PEMBAYARAN' + nama + terbilang.
- [FIX] Backend crash saat startup: server.py membuat index `id` (nama default `id_1`) sedangkan ensure_indexes sudah bikin `id_unique` → IndexOptionsConflict mematikan app. Diperbaiki: name='id_unique' + try/except. App boot normal, login jalan.
- [VERIFIED 0.0 diff] Laporan Excel cocok 100% dengan spreadsheet: Store REPORT 2026-01..2026-12 dan September Laba-Rugi 2026-08 (Modal/Laba/Spooring/Oli, NETT, Laba bersih −Rp2.816.000, Sisa aset −Rp514.093.962).
- [DONE] Impor piutang & hutang dari workbook September: parser dilonggarkan (SISA kosong = belum dibayar, sisa=total). Committed 24 piutang (Rp65.844.000 = B21) + 39 hutang (Rp829.751.449 = B23), commit idempotent (tanpa duplikat), aging terhitung.
- [VERIFIED] Testing agent iteration_2: backend 21/21, frontend 100%, tanpa isu. POS tunai+kredit, kredit→AR, retur→AR void (bukan paid), bayar cicilan parsial idempotent + tolak overpayment, RBAC kasir 403.

## Prioritized backlog
### P0 (menunggu keputusan/aksi user)
- Windows XP offline: stack modern tidak kompatibel XP. Butuh keputusan arsitektur (belum dikerjakan; jangan diam-diam ganti ke SQLite/Electron/komputer kedua).
### P1
- 5 produk nama-ganda + saldo piutang/hutang agregat DATABASE Store sengaja TIDAK diimpor (butuh merge/pemetaan manual, hindari dobel dengan detail September).
- Snapshot stok September (Laporan Data Barang, 2 Juni 2026) masih ditahan (beda tanggal dari stok akhir Store).
### P2
- Kategori pendapatan Spooring/Oli/Ban lebih detail di UI; modul bagi laba pemilik (Subsidi Modal 50/50, Cicilan BNI, min laba ibu 10jt) bila aturan bisnis final.
- GET /api/receivables/{id} single lookup; default payment_date=today di UI.

## Next action
Tawarkan ke user: impor produk/stok, atau bahas arsitektur Windows XP offline. Tidak ada bug terbuka.
