# BengKasir — POS & Mini ERP Bengkel Ban & Servis Otomotif

## Ringkasan
Aplikasi kasir (POS) + mini-ERP untuk bengkel ban/servis otomotif. Aplikasi live berjalan dengan
FastAPI + MongoDB (backend) dan React 19 + Tailwind v4 + shadcn/ui (frontend) — padanan fungsional
dari permintaan Laravel 11 + Filament v3 + Livewire v3 + MySQL. Kode referensi Laravel lengkap
(perintah terminal, migration, model, Livewire POS, Filament widget/resource) ada di
`backend/laravel_reference/` dan dapat dilihat/diunduh dari halaman **/laravel** di aplikasi.

## Login
- POST /api/auth/login {username, password} → httpOnly cookie `bengkel_session` (Mongo `sessions`).
- Akun seed: **admin/admin123** (role admin) dan **kasir/kasir123** (role kasir).
- Semua endpoint /api/* kecuali /auth/* wajib sesi (dependency `require_user` → 401).
- Logout wajib lewat `frontend/src/lib/session.ts` → `endSession()` (POST /auth/logout + clear react-query cache).

## Data model (Mongo, `id` string uuid4, DB "app")
- `products`: type `barang|jasa`, sku, name, brand, size, stock (barang), cost_price (modal), selling_price, service_fee (komisi montir, khusus jasa)
- `customers`, `suppliers`: name, phone, address
- `transactions`: invoice_number unik `INV-YYMMDD-0001`, date (aware UTC) + date_key (YYYY-MM-DD, APP_TZ=Asia/Jakarta), customer_id/name, payment_method `cash|credit`, total_amount, barang_amount, jasa_amount, total_cost, service_fee, total_profit, status `completed|returned`, due_date (kredit, string ISO)
- `transaction_details`: snapshot product_id/name/type, qty, price, cost_price, service_fee, subtotal
- `accounts_receivable` (piutang): dibuat OTOMATIS saat checkout credit; transaction_id, invoice_number, customer_id/name, amount, due_date, status `unpaid|paid`
- `accounts_payable` (hutang): dicatat manual via halaman Piutang & Hutang; supplier_id/name, invoice_number, amount, due_date, status
- `expenses`: date, amount, category, description
- `users` (name, username unik, role admin|kasir, password_hash bcrypt), `sessions` (token unik, expires_at TTL)

## Logika bisnis
- Laba barang = (selling_price − cost_price) × qty; laba jasa = (selling_price − service_fee) × qty (komisi montir)
- Checkout credit → wajib customer_id + due_date (validasi Pydantic `credit_rule` → 422) → otomatis buat baris `accounts_receivable` unpaid
- Retur `POST /api/transactions/{id}/return` → status `returned`, stok barang dikembalikan ($inc), piutang unpaid terkait dianggap hangus (paid), dan dikecualikan dari pendapatan/laba dashboard
- Dashboard: Total Pendapatan, Laba Kotor barang (barang_amount − total_cost), Laba Bersih (total_profit − pengeluaran), piutang/hutang outstanding + overdue count, grafik 7 hari, stok menipis (≤4), transaksi terakhir
- Overdue = due_date < hari ini (server: `today_iso()` APP_TZ Asia/Jakarta; badge frontend display-only) → badge merah berdenyut "Lewat Jatuh Tempo"; ≤3 hari → badge kuning
- Struk thermal 80mm: modal `ThermalReceiptModal` (putih, mono, tepi gerigi, barcode dekoratif, `window.print()` + CSS `@media print` 80mm) — dipakai untuk cetak pertama & cetak ulang dari riwayat

## Endpoint utama (semua di api_router /api; `app.include_router(api_router)` terakhir di server.py)
- /auth/login | /auth/logout | /auth/me
- /products | /customers | /suppliers — CRUD
- /transactions (POST checkout, GET riwayat) | /transactions/{id} | /transactions/{id}/return
- /receivables (+ /{id}/pay) | /payables (POST catat + /{id}/pay) | /expenses (GET/POST/DELETE)
- /stock-in (GET riwayat, POST catat barang masuk) — stok naik + cost_price produk diperbarui + hutang otomatis
- /vehicles (daftar nopol + ringkasan) | /vehicles/{plate} (riwayat servis + ban/oli terakhir)
- /reports/monthly (JSON) | /reports/monthly/csv | /reports/monthly/pdf (reportlab, unduhan)
- /dashboard (agregasi keuangan) | /laravel-bundle (served from backend/laravel_reference/)

## Halaman frontend (React Router, layout AppShell sidebar)
/login · / (dashboard) · /pos (kasir: F2 cari, F4 bayar, input nopol opsional) · /transaksi (riwayat+retur+cetak ulang, kolom nopol) ·
/kendaraan (riwayat kendaraan per nopol) · /produk · /stok-masuk · /pelanggan · /distributor ·
/piutang-hutang · /pengeluaran · /laporan (laba-rugi bulanan + unduh CSV/PDF) · /laravel (viewer+unduh kode)

## Fitur tambahan (iterasi 2)
- **Riwayat Kendaraan**: `vehicle_plate` (opsional, disimpan UPPERCASE) diisi kasir saat checkout → tampil di struk
  thermal & kolom Nopol di Transaksi, dan bisa dicari. Halaman /kendaraan mengelompokkan transaksi `completed`
  per plat: jumlah kunjungan, total belanja, pemilik terakhir, serta **ban terakhir** (produk barang bernama/SKU `BAN*`)
  dan **oli terakhir** (`OLI*`) beserta tanggalnya — klasifikasi via regex di `routers/vehicles.py`.
- **Stok Masuk**: satu form multi-item (`/stok-masuk`). Satu submit → stok setiap barang naik, `cost_price` produk
  diperbarui ke harga beli terbaru, dan SATU baris `accounts_payable` dibuat otomatis (tersimpan di `stock_in.payable_id`).
  Referensi `SM-YYMMDD-0001` (unik). Jasa ditolak (400) karena tidak punya stok.
- **Laporan Bulanan**: `/laporan` menampilkan laba-rugi `?month=YYYY-MM` (pendapatan barang/jasa, HPP, laba kotor barang,
  komisi montir, pengeluaran per kategori, laba bersih, jumlah transaksi/retur, piutang baru & lunas, nilai barang masuk,
  5 produk terlaris). Unduhan **CSV** (`csv` module) dan **PDF** (reportlab/platypus, A4). Bulan tersedia dihitung dari
  `date_key` transaksi + tanggal pengeluaran. Format bulan salah → 400.

## Seed
`cd /app/backend && python seed.py` (idempotent — skip jika koleksi `users` tidak kosong):
2 user, 16 produk (11 barang + 5 jasa), 5 pelanggan, 3 distributor, 28 transaksi
(7 skenario tangan + 21 transaksi ritel deterministik selama 7 hari; 1 retur = INV-260924-0002),
6 piutang (1 lewat jatuh tempo), 3 hutang (1 lewat tempo, 1 H-2), 4 pengeluaran skala mingguan.
Reset penuh: drop koleksi lalu jalankan ulang `python seed.py`.

## Catatan implementasi (jangan diulang sebagai bug)- `due_date` HARUS disimpan sebagai string `YYYY-MM-DD` murni. Jangan pakai `datetime.strptime(...).isoformat()`
  (menghasilkan `...T00:00:00`) — gunakan `date.fromisoformat(today_iso())`. Tanggal ber-`T` pernah membuat
  `daysUntil()` di frontend mengembalikan 0 sehingga badge overdue salah tampil (kini `daysUntil` memakai `.slice(0,10)`).
- Transaksi `credit` WAJIB punya `customer_id`; dokumen piutang tanpa customer_id membuat
  `GET /api/receivables` gagal validasi Pydantic (500). Generator seed menjaga aturan ini.
- **PDF reportlab**: sel `Table` adalah string biasa (BUKAN `Paragraph`) — jangan tulis entity XML
  seperti `&amp;` di dalamnya, karena akan tampil literal. Pakai `&` biasa. Entity XML hanya untuk `Paragraph`.
- Laporan PDF harus muat 1 halaman: padding tabel 2.5pt, `h2.spaceBefore=7`, spacer footer 8pt.
  Menaikkan nilai-nilai ini membuat footer terdorong ke halaman 2 yang kosong.
- Verifikasi PDF wajib dirender jadi gambar (pymupdf, alat verifikasi saja — JANGAN masuk requirements.txt);
  cek byte/`%PDF-` saja tidak menangkap teks ter-escape ganda atau halaman kosong.
