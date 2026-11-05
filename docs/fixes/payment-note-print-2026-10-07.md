# Pembayaran diterima dan cetak nota

Pembayaran cash, EDC, BCA, Mandiri, BRI, dan transfer dapat menyimpan nominal sebenarnya yang diterima. Total penjualan tetap mengikuti barang dan potongan; selisih disimpan terpisah. Nota tunai menampilkan kembalian, sedangkan nota non-tunai menampilkan kelebihan pembayaran. Pembayaran tempo tetap mengikuti alur piutang.

Cetak nota menggunakan teks Arial asli dengan ukuran minimal 10 pt, tanpa text stroke. Huruf tebal dipakai untuk judul dan total. Print menunggu dokumen siap, dan dokumen yang sudah ditutup tidak dapat memicu cetak berikutnya. Ukuran setengah/penuh serta pengaturan area cetak tetap tersedia.

## Verifikasi pada Demo-Bian

- PASS: build produksi dan lint.
- PASS: 49 regresi backend memakai database Mongo lokal terisolasi; pembayaran berlebih, validasi nominal, cetak ulang, idempotensi, stok, dan retur.
- PASS: browser kasir untuk semua metode langsung, nominal pas/berlebih/invalid, cetak ulang, tempo, potongan per unit, keyboard, serta viewport 390/768/1280 dalam tema terang/gelap. API uji memakai fixture.
- PASS: 12 PDF pendek pada ukuran setengah/penuh dan area cetak 0/0,25 inci masing-masing satu halaman; dua PDF 50 barang mempertahankan seluruh teks dan total. Font berupa teks asli, tanpa gambar raster.
- PASS: printer browser untuk tutup/buka ulang serta frame terlambat.
- PASS antislop: arah kasir Perkasa Jaya yang sudah ada dipertahankan; label selisih mengikuti metode, feedback terhubung ke input, keyboard dan reflow diuji.

Artefak lokal: `test_reports/nota/payment-print-1791376526097` dan `test_reports/nota/print-quality-1791376385147`. Printer fisik belum diuji; lakukan satu cetak nyata menggunakan form dan orientasi yang cocok di driver.

## Target deployment

Repo produksi: `Bimaa14/Demo-Bian`, branch `main`. Railway: project `sublime-reflection`, service `bian-client-demo`, environment `production`.

Docker mengaktifkan `CLOUD_SINGLE_WRITER=true`. Hentikan deployment aktif secara graceful dan tunggu Offline sebelum menjalankan penggantinya agar lock database dilepas. Jangan menghapus lock saat proses lama masih berjalan. Perubahan ini tidak membutuhkan migrasi workbook atau data laporan.
