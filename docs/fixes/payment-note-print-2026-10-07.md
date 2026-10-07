# Pembayaran diterima dan teks nota

Perbaikan ini disiapkan dari commit `4280cd0` untuk pembayaran berlebih dan hasil cetak yang sulit dibaca. Perubahan lokal lain pada laporan, perhitungan harga, dan tampilan aplikasi tidak disertakan.

## Perubahan

- Tunai, EDC, transfer BCA/BRI/BNI, dan QRIS menerima nominal pembayaran sebenarnya, termasuk jika melebihi tagihan. Nominal serta selisih disimpan untuk cetak ulang.
- Data lama yang tidak memiliki nominal pembayaran tetap ditandai Tidak tercatat. Penjualan dan retur tetap mengikuti tagihan.
- Nota langsung/tempo memakai Arial reguler 10 sampai 11 pt tanpa stroke tambahan pada huruf. Judul/header/total mempertahankan huruf tebal untuk hierarki.
- Ruang kosong tabel disesuaikan agar nota pendek tetap satu halaman dengan huruf yang terbaca.
- Cetak menunggu font/layout, membatalkan operasi ketika nota ditutup/diganti, dan memulihkan tombol setelah dibuka ulang.

## Verifikasi pada versi yang dikirim

- PASS: `npm run build`, TypeScript dan build produksi selesai.
- PASS: 49 regresi backend untuk nominal diterima, seluruh metode langsung, input tidak valid, request berulang, data lama, cetak ulang, penjualan, dan retur. Database pengujian acak dibuang setelah tes.
- PASS: `node tests/sales-note.browser.mjs`, memakai API tiruan. Enam metode langsung, nominal lebih, validasi, reset Uang pas, cetak ulang, tempo tanpa nominal diterima, kontrol cetak/PDF, Escape, Tab, serta dialog pada 390/768/1280 px dalam dua tema lulus tanpa page error.
- PASS: `node tests/note-print-quality.browser.mjs`, memakai data tiruan. Dua belas PDF pendek tunai/transfer/tempo pada kedua ukuran kertas, termasuk simulasi area cetak lebih kecil, tetap satu halaman. Dua PDF 50 barang mempertahankan semua barang dan total.
- PASS: harga minimal 10 pt reguler, stroke nol, tanpa filter/transform/shadow. PDF berisi font asli dan nol gambar raster.
- PASS: menutup nota saat menunggu font/frame membatalkan cetak lama; membuka ulang dapat mencetak sekali. Frame terlambat pulih melalui batas waktu.
- PASS: gambar nota transfer akhir diperiksa langsung; jumlah diterima Rp500.000 dan kelebihan Rp90.000 tampil jelas pada fixture tagihan Rp410.000.
- PASS: pemeriksaan whitespace dan lint file printer selesai tanpa error. Build masih memberi peringatan ukuran bundle yang sudah tersedia.

## Delivery Gate untuk perubahan ini

- Hard Gate PASS: input berlabel dan memiliki validasi yang diumumkan; loading/error cetak tersedia; Tab/Escape dan ukuran dialog diuji; teks nota hitam/putih memiliki kontras 21:1; data transaksi tidak dikarang; tidak ada aset atau navigasi baru.
- Purpose Gate PASS: Arial reguler dan ukuran 10 sampai 11 pt meningkatkan keterbacaan; tebal terbatas pada hierarki; spasi footer menjaga ukuran form; ikon cetak/PDF tetap menandai tindakan yang nyata.
- Liveliness PASS: format kasir/nota Perkasa Jaya dipertahankan dengan ENERGY 1 / RHYTHM 1 / MOTION 1. Total menjadi fokus, tabel mengikuti rincian, dan ruang kosong dipakai untuk struktur dokumen.
- Craftsmanship/Quality Locks PASS: perilaku keenam metode dan kontrol cetak diuji; nilai tagihan/retur tidak berubah karena nominal lebih; tema dan lebar dialog diperiksa; tidak menambahkan bagian dekoratif atau klaim tanpa bukti.

Printer fisik pengguna belum diuji. Verifikasi di atas menguji source, browser, font PDF, isi nota, dan ukuran halaman.
