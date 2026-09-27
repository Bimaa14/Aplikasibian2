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

## Restore log (2026-06, pod baru)
- Pod datang sebagai template CRA kosong. App asli user ada di github.com/Bimaa14/Aplikasibian2 (React+TS/Vite + FastAPI). Repo di-migrasi ke /app (pertahankan /app/.git & /app/.emergent; buat backend/.env + frontend/.env).
- Hapus sisa config CRA (postcss/craco/tailwind.config.js/jsconfig/plugins) + komponen .jsx lama yang bikin Vite gagal build. Install deps (buang emergentintegrations+litellm yang tak dipakai & konflik).
- Seed akun admin/kasir. Re-impor data via /api/imports: 468 produk, 7505 transaksi, 24 piutang (Rp65.844.000), 39 hutang (Rp829.751.449), + snapshot Laba-Rugi & Laporan Data Barang (2 Juni). Semua rekonsiliasi 0.0.
- Testing agent iteration_4: backend 6/6, frontend 7/7 — login admin/kasir, dashboard aging+KPI, transaksi, piutang/hutang, snapshot, RBAC semua LULUS. Tidak ada bug.

## Status fitur plan (A→B→C)
- Fitur A (Ringkasan Aging di Dashboard): SUDAH ADA & jalan (dashboard.py aging_buckets + DashboardPage aging card).
- Fitur B (Merge 5 produk ganda): BELUM dibangun. Saat impor, duplikat nama digabung otomatis di level workbook, jadi tidak ada UI review/merge master. Perlu fitur baru: review pasangan nama-sama, pilih master, gabung stok + samakan harga, idempotent/reversible, jangan yatim-kan referensi ledger.
- Fitur C (Snapshot Stok 2 Juni, read-only): SUDAH ADA & jalan (StockSnapshotPage + /api/excel/stock-snapshot). Read-only, tidak ubah stok.

## Menunggu user (non-blocking)
- Foto storefront Perkasa Jaya/Dunlop untuk panel login (revisi login) — belum diupload.
- Backup GitHub ke repo private Aplikasi-Bian-Backu — butuh akses/collaborator; hanya zip berpassword yang di-push.
- Deployment offline Win11+XP — di luar env cloud; disiapkan skrip/dokumen. CATATAN PENTING: untuk LAN http, backend/.env COOKIE_SECURE harus =false (cookie Secure tidak terkirim di http → login loop di XP).

## Next action
Tawarkan ke user: (1) bangun Fitur B (merge produk ganda), (2) revisi foto login (butuh foto), (3) siapkan skrip backup GitHub + panduan deploy offline Win11/XP.

## Update 2026-06 (lanjutan)
- LOGIN: foto storefront asli (Dunlop/Perkasa Jaya) terpasang di panel kiri (crop fokus plang brand, disimpan lokal /storefront-login.jpg). Kredensial direset & terverifikasi: admin/admin123, kasir/kasir123.
- FITUR PEMILIK BARANG (Bian/Ibu): produk punya atribut owner ('bian'|'ibu'); produk baru wajib pilih pemilik (default Bian); 468 produk lama sengaja dibiarkan owner=None. Transaksi ikut pemilik produk (owner tersimpan per baris detail). Filter Semua/Bian/Ibu + badge di halaman Produk. Terverifikasi testing agent iteration_6 (BE+FE 100%). Data tetap 7505 tx / 468 produk.
## Update 2026-06 (Laporan Kas & Pajak — SELESAI)
Menu baru admin "Laporan Kas & Pajak" (/laporan-kas), sumber data = live_events (konsisten dgn Laporan Excel):
- Laporan Harian: pendapatan tunai + bayar piutang − bayar transfer − komisi montir − pengeluaran = kas bersih.
- Laporan Bulanan: (1) Total omzet semua kecuali oli, (2) Pembayaran distributor, (3) Pengeluaran, (4) Sisa aset (stok snapshot B19 + piutang − hutang) + rincian sumber uang (Modal→distributor; Laba→pengeluaran+pajak+gaji).
- Laporan Pajak: PPh final 0,5% dari total omzet (non-oli).
Terverifikasi testing agent iteration_7 (BE 12/12, FE 13/13). Read-only, data tetap 7505 tx / 468 produk.
Angka Agustus 2026: omzet 346.172.000, distributor 295.583.930, pengeluaran 38.780.500, PPh 1.730.860, sisa aset −503.175.032.
