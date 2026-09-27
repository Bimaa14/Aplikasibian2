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