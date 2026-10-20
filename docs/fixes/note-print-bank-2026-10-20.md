# Ketajaman cetak dan rekening nota

Nota pembayaran langsung kini mencantumkan Bank BCA, 3761155405, A.N Wati Wulandari di kiri bawah. Posisi header, tabel, lebar setiap kolom, serta posisi total dibandingkan dengan dokumen sebelum perubahan dan tetap sama pada enam varian tunai/transfer/tempo serta setengah/satu lembar. Form tempo tetap memakai tata letak tersendiri.

Teks tetap berupa teks asli dengan font Arial reguler 10 sampai 11 pt. Aturan bersama menonaktifkan text shadow, text stroke, dan sintesis font. Rekening ditulis 10 pt hitam di atas putih, dengan jarak yang cukup agar nota pendek tetap satu halaman.

## Printer

Epson LX-310 ESC/P sebelumnya memakai 120 x 72 dpi. Driver menyatakan dukungan untuk 240 x 144 dpi, yang telah diterapkan sebagai preferensi pengguna Windows. Verifikasi DEVMODE 1.124 byte menunjukkan hanya `dmPrintQuality` dan `dmYResolution` berubah. Form Letter, orientasi portrait, skala 100%, satu salinan, sumber kertas, serta data privat driver tetap sama. Default sistem tidak berubah.

Cadangan dan bukti berada di `.cache/note-print-20261020/printer-original.json` dan `printer-applied.json`. Pemulihan preferensi semula:

```powershell
& '.cache/note-print-20261020/printer-quality.ps1' -Action Restore
```

Tidak ada pekerjaan cetak fisik yang dikirim. Kualitas kertas hasil printer masih perlu diperiksa melalui cetakan pengguna.

## Verifikasi

- PASS: `npm run build`.
- PASS: `node tests/note-print-quality.browser.mjs`. Dua belas PDF pendek tetap satu halaman, termasuk simulasi area cetak lebih kecil. PDF berisi font asli tanpa gambar raster. Rekening tampil tepat sekali di kiri bawah pada nota pembayaran langsung; seluruh 50 barang dan total tetap tercetak pada nota panjang.
- PASS: `node tests/sales-note.browser.mjs`. Cetak/PDF, pengaturan, cetak ulang, seluruh pembayaran langsung, tema terang/gelap, ukuran layar, keyboard, serta transaksi tempo/retur dan data lama lolos.
- PASS: perbandingan geometri header, tabel, kolom, dan posisi total sebelum/sesudah pada enam varian; bukti `.cache/note-print-20261020/geometry-verification.json`.
- PASS: PDF tunai dan transfer dirender dengan Poppler dan diperiksa langsung. Rekening terbaca, tidak bertumpuk dengan catatan/total, dan tidak terpotong.
- PASS: aplikasi aktif di port 3001 menyajikan modul rekening terbaru.

Artefak PDF dan HTML pengujian berada di `test_reports/nota/print-quality-1792476106018`. Semua transaksi pengujian adalah fixture, bukan transaksi operasional.

## Delivery Gate

- Hard Gate PASS: nomor rekening sesuai instruksi pengguna, teks hitam-putih berkontras 21:1, PDF tidak terpotong; tes kontrol, keyboard, loading, serta pembatalan cetak lolos.
- Purpose Gate PASS: teks asli tanpa stroke/shadow mencegah penebalan tambahan; rekening menggunakan area kiri bawah yang diminta; resolusi printer ditingkatkan tanpa mengubah form.
- Liveliness PASS: acuan tetap nota Perkasa Jaya, ENERGY 1 / RHYTHM 1 / MOTION 1; total menjadi fokus, struktur tabel dan penekanan tebal dipertahankan.
- Craftsmanship/Quality Locks PASS: build, pengujian browser/PDF, pemeriksaan visual, serta perbandingan geometri lolos; isi rekening berasal langsung dari pengguna dan nilai transaksi tidak diubah.
