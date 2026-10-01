> **Update migrasi 29 September 2026:** sumber Store `(1).xlsx` sudah aktif. Lihat [data, Get Data, nota tempo, dan backup](refrensi-spreadsheet/MIGRASI-AKTIF.md).

# Pembukuan POS aktif ? revisi September 2026

- **Laporan Kas & Pajak ? Transaksi Bulanan**: pilih bulan, pemilik, kategori, TAX, dan tipe pembayaran. Ringkasan serta CSV menghitung semua baris yang cocok, tidak hanya halaman yang terlihat.
- TAX di master barang/jasa: `1` masuk dasar pajak laporan, `0` tidak. Tarif tetap **0,5%**, tanpa tambahan pajak pada tagihan pelanggan. Dasar pajak adalah penjualan bersih setelah potongan, termasuk penyesuaian retur pada bulan retur.
- Kepemilikan, kategori, TAX, harga, dan potongan disimpan saat transaksi. Mengubah produk tidak mengubah transaksi lama. Data lama tanpa TAX ditampilkan sebagai **Belum ditandai**, tidak diasumsikan TAX = 1. Periksa kelengkapan penandaan sebelum memakai laporan; tidak ada perubahan massal data historis.
- Checkout mendukung Tunai, Tempo, EDC, Transfer BCA/BRI/BNI, dan QRIS. Metode non-tunai juga tersedia saat mencatat cicilan. Ini pencatatan metode pembayaran; konfirmasi penerimaan dilakukan kasir.
- **Potongan total nota** diisi dalam rupiah. Sistem membaginya secara proporsional ke item agar laporan per pemilik/kategori/TAX tetap cocok dengan total nota. Contoh: barang Rp10.000 + Rp30.000 dengan potongan Rp4.000 menjadi Rp9.000 + Rp27.000.
- Tempo: pilih pelanggan dan jatuh tempo, lalu isi tambahan harga **per unit** jika diperlukan. Piutang mengikuti total setelah tambahan dan potongan. Nota tempo mencantumkan tagihan awal dan jatuh tempo; cicilan dicetak lewat kwitansi pembayaran.
- Kas harian memisahkan penjualan non-tunai dari uang kas fisik. Ringkasan Excel lama masih mengikuti rumus workbook; tab Transaksi Bulanan merupakan rincian transaksi POS.

## Verifikasi revisi

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_financial_safety.py tests/test_sales_revision.py -q
cd ..\frontend
npm run build
node tests/sales-note.browser.mjs
```

Tes backend tersebut memakai database acak terpisah yang dihapus setelah tes. Tes browser menggunakan data tiruan. Panduan nota: `frontend/README.nota.md`; panduan server: `backend/README.local.md`.

---

## Catatan historis modul awal

Bagian berikut merupakan dokumentasi awal sebelum integrasi POS/Vite; untuk pemakaian saat ini ikuti panduan di atas.

# BengKasir — modul persiapan pembukuan

Kode BengKasir lama dan file Excel belum tersedia di workspace. Modul ini terpisah dan belum terhubung ke POS, stok, atau otorisasi admin/kasir lama.

## Tersedia
- Piutang/hutang dengan pembayaran parsial, riwayat, validasi sisa dan kontrol pembayaran bersamaan.
- Aging berdasarkan APP_TZ dan status retur Void dengan pencatatan pengembalian kas.
- Laporan kas aktual dan laba margin terpisah; transaksi tunai dan ekspor CSV/JSON.

## Konfigurasi
Pertahankan `backend/.env`: MONGO_URL, DB_NAME, APP_TZ, CORS_ORIGINS. Frontend membaca REACT_APP_BACKEND_URL. Tidak ada fallback database/origin.

Runner preview yang sudah disediakan masih CRA/CRACO; modul baru menggunakan TypeScript. Integrasikan `frontend/src/accounting` ke project Vite asli setelah kode tersedia. Tidak ada penggantian project lama karena kode lama belum ada.

Pemeriksaan: `cd frontend && yarn tsc --project tsconfig.accounting.json --noEmit && yarn build`.

Regresi backend: atur REACT_APP_BACKEND_URL dari frontend/.env, lalu jalankan `cd backend && pytest -n 0 tests/test_accounting_flows.py`. Gunakan mode serial untuk rekonsiliasi baseline laporan; tes race pembayaran tetap menjalankan thread konkuren. Fixture hanya menghapus ID data uji yang dibuatnya sendiri.

## API utama
| Method | Path | Fungsi |
| --- | --- | --- |
| GET | /api/health | Tanggal server, zona waktu dan kesehatan DB |
| POST | /api/debts | Buat tagihan kredit |
| GET | /api/debts?kind=receivable atau payable | Semua tagihan per jenis |
| GET | /api/debts/{id} | Detail & riwayat |
| POST | /api/debts/{id}/pay | amount, method, payment_date, note, request_id |
| POST | /api/debts/{id}/return | reason, refund_confirmed; piutang saja |
| POST/GET | /api/entries | Transaksi tunai langsung |
| GET | /api/reports?month=YYYY-MM | Laporan kas dan margin |
| GET | /api/overview?month=YYYY-MM | Ringkasan tagihan terkini dan laporan periode |
| GET | /api/backup | JSON data tersimpan; belum mendukung restore |

Retur penuh mempertahankan riwayat cicilan, menutup sisa sebagai Void, membalik penjualan/HPP pada tanggal retur. Jika sudah ada pembayaran, operator harus mengonfirmasi pengembalian penuh yang benar-benar dilakukan. Piutang retur tidak termasuk `receivables_paid`, namun penerimaan dan pengembalian kas tetap masuk arus kas sesuai tanggal sebenarnya.

Nominal berupa integer Rupiah. Pembelian supplier tunai bukan HPP: HPP dicatat bersama penjualan. Laba margin belum mencakup akrual beban yang belum dibayar.

## Windows XP dan offline
**Belum didukung. Tidak ada installer XP atau mode offline mandiri.** MongoDB, Python/FastAPI dan runtime web modern tidak mendukung kebutuhan satu komputer XP dengan stack ini. Referensi kompatibilitas: https://docs.python.org/release/3.4.10/using/windows.html dan https://www.mongodb.com/docs/languages/python/pymongo-driver/v4.9/reference/compatibility/ . Diperlukan keputusan arsitektur terpisah dan uji pada perangkat XP; tidak menggunakan runtime lama atau mengganti MongoDB tanpa persetujuan.

Lihat `memory/PRD.md` untuk cakupan, batasan, dan rencana integrasi.