# Referensi: Mini-ERP & POS Bengkel — Laravel 11 + Filament v3 + Livewire v3 + MySQL

Bundle kode referensi sesuai permintaan (Laravel 11 + Filament v3 + Livewire v3 + Tailwind CSS).
Aplikasi demo yang berjalan di pod ini memakai FastAPI + MongoDB + React dengan logika bisnis
yang identik; semua file di bawah adalah padanan Laravel-nya.

## Langkah 1 — Instalasi proyek

```bash
composer create-project laravel/laravel bengkel-erp "11.*"
cd bengkel-erp
composer require filament/filament:"^3.2" livewire/livewire:"^3.5"

# siapkan database MySQL
mysql -u root -e "CREATE DATABASE IF NOT EXISTS bengkel_erp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
# sesuaikan .env: DB_CONNECTION=mysql DB_DATABASE=bengkel_erp DB_USERNAME=root DB_PASSWORD=

php artisan filament:install --panels
npm install && npm install -D tailwindcss @tailwindcss/forms
```

## Langkah 2 — Model + Migration

```bash
php artisan make:model Product -m
php artisan make:model Customer -m
php artisan make:model Supplier -m
php artisan make:model Transaction -m
php artisan make:model TransactionDetail -m
php artisan make:model AccountsReceivable -m
php artisan make:model AccountsPayable -m
php artisan make:model Expense -m
```

Salin isi file di `database/migrations/` dari bundle ini ke setiap migration, lalu:

```bash
php artisan migrate
```

## Langkah 3 — Panel Admin Filament (CRUD + Dashboard)

```bash
php artisan make:filament-user                          # akun admin pertama
php artisan make:filament-resource Product --generate
php artisan make:filament-resource Customer --generate
php artisan make:filament-resource Supplier --generate
php artisan make:filament-resource AccountsReceivable --generate
php artisan make:filament-resource AccountsPayable --generate
php artisan make:filament-resource Expense --generate
php artisan make:filament-widget FinancialStatsWidget --stats-overview
```

Salin file referensi `app/Filament/...` dari bundle ini (widget dashboard keuangan dan
resource piutang dengan indikator "Lewat Jatuh Tempo").

## Langkah 4 — Halaman POS Livewire

```bash
php artisan make:livewire Pos.PosPage
```

Salin `app/Livewire/Pos/PosPage.php` dan
`resources/views/livewire/pos/pos-page.blade.php` dari bundle ini.

## Langkah 5 — Jalankan

```bash
php artisan serve            # http://localhost:8000
npm run dev                  # Vite + Tailwind CSS
```

## Logika bisnis penting (diimplementasikan di kode bundle)

- **Laba barang** = (selling_price - cost_price) × qty
- **Laba jasa**   = (selling_price - service_fee) × qty — `service_fee` adalah komisi montir
- **Pembayaran credit (tempo)** → WAJIB memilih `customer_id` + `due_date`; sistem otomatis
  membuat baris `accounts_receivable` berstatus `unpaid`
- **Retur** → status transaksi menjadi `returned`, stok barang dikembalikan otomatis
  (`Transaction::markReturned()`), dan transaksi dikecualikan dari pendapatan kas
- **Struk** → dicetak pada kertas thermal 80mm (CSS `@page { size: 80mm auto; }`)
- **Piutang/Hutang** → baris dengan `due_date` lewat hari ini ditandai "Lewat Jatuh Tempo"
