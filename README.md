# Aplikasi Bian / Perkasa Jaya

Aplikasi kasir, stok, piutang/hutang, dan laporan bengkel berbasis React + FastAPI + MongoDB.

- [Demo client gratis di Render + MongoDB Atlas](DEPLOY-RENDER.md): frontend dan API dalam satu alamat, database demo terpisah.
- [Menjalankan backend dan frontend lokal](backend/README.local.md).
- [Acuan perhitungan dan verifikasi laporan](README.accounting.md).
- [Pemakaian dan cetak nota penjualan](frontend/README.nota.md).

Konfigurasi Render tersedia di `render.yaml` dan `Dockerfile`. Secret koneksi database diisi di hosting; tidak disimpan di source. Penyiapan ini tidak menerbitkan layanan atau menyalin database operasional.
