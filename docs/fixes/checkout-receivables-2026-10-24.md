# Checkout, piutang, dan laporan harian

Revisi lokal 24 Oktober 2026 mengikuti empat gambar dan klarifikasi pemilik: Print menyimpan transaksi lalu membuka cetak; Tempo dapat memakai uang muka.

## Arah tampilan

Reading this as: a workshop checkout and receivables ledger for Perkasa Jaya cashiers, following the existing navy and amber bookkeeping language. ENERGY 1 / RHYTHM 1 / MOTION 1 for the revised working sections.

- Pilihan Cash/Tempo berada di panel keranjang yang sama agar kasir dapat menyelesaikan transaksi tanpa berpindah formulir pembayaran.
- Navy, amber, font, dan bentuk kontrol mengikuti arah yang sudah ada di `docs/UI-REDESIGN.md`; amber tetap menandai aksi Print.
- Angka Rupiah memakai tipografi keuangan yang sudah ada; nama pelanggan dan label dapat membungkus pada layar sempit.
- Tabel rekap menampilkan kredit, pembayaran, dan sisa piutang karena angka tersebut menentukan pelanggan yang perlu ditagih.
- Formulir mengikuti aliran halaman agar seluruh input bisa dijangkau pada ponsel, tablet, dan desktop.
- Laporan cetak memakai dua kolom ringkas dengan teks hitam dan tabel tanpa dekorasi agar mudah dibaca di kertas.
- Ikon pencarian, riwayat, tambah/kurang barang, dan printer menunjukkan tindakan yang memang tersedia. Tidak ada aset visual baru.
- Gerak dibatasi pada umpan balik kontrol yang sudah ada; hierarki berasal dari label, jarak antarkelompok, dan total.

## Aturan transaksi dan laporan

- Tenor merupakan bilangan hari 1 sampai 3.650. Backend menghitung jatuh tempo berdasarkan tanggal server; client lama yang mengirim `due_date` tetap didukung.
- Tempo wajib pelanggan. Uang muka harus positif dan lebih kecil dari total bila dipilih, serta memiliki metode pembayaran.
- Piutang menyimpan total nota asli, pembayaran uang muka, serta sisa tagihan. Stok, transaksi, dan pembayaran pertama disimpan dalam satu operasi keuangan.
- Print menyimpan terlebih dahulu. Percobaan ulang payload yang sama memakai request ID yang sama. Cetak ulang memakai transaksi yang sudah tersimpan.
- Laba otomatis diambil dari pembayaran aktual sampai laba nota terpenuhi, termasuk uang muka. Setiap pembayaran dibatasi nominal penerimaan dan sisa laba.
- Pembayaran historis yang sudah tercatat dipertahankan. Saldo lama tanpa rincian laba tidak diberi laba otomatis yang tidak dapat dibuktikan.
- Rekap pelanggan mengabaikan nota Void. Customer ID menjadi identitas utama; nama yang dinormalisasi digunakan untuk data lama tanpa ID.
- Cetak harian memakai dokumen tersendiri, berisi kas, modal/laba, oli, dan rincian nontunai. Laba piutang ditampilkan sebagai bagian dari laba toko, bukan ditambahkan dua kali.

## Verifikasi

Pengujian memakai fixture, database acak yang dibuang setelah tes, dan browser dengan seluruh permintaan API diintercept. Server operasional, transaksi pengguna, dan printer fisik tidak digunakan.

- PASS: 184 tes backend pada checkout/DP/tenor, laba piutang, kesesuaian spreadsheet, payload harian, pembagian pemilik, retur, konkurensi, idempotensi, rollback, dan pengecualian laporan.
- PASS: `npm run build`, termasuk pemeriksaan TypeScript. Peringatan ukuran bundle Vite yang sudah ada tetap muncul; tidak ada kegagalan build.
- PASS: Oxlint untuk tujuh file source frontend yang berubah dan `git diff --check` untuk file tracked yang disentuh.
- PASS: `sales-note.browser.mjs` mempertahankan nota tunai/transfer, PDF, rekening BCA, dan riwayat cetak.
- PASS: `note-print-quality.browser.mjs` menguji nota lama, 50 barang, serta nota DP pada setengah/satu lembar dengan simulasi area cetak lebih kecil. Font tetap teks asli tanpa rasterisasi, stroke, atau scaling.
- PASS: sembilan skenario dalam `frontend/tests/revision-20261024.browser.mjs`; bukti ada di `test_reports/revision-20261024/clickthrough.json`.
- PASS: PDF laporan harian A4, Letter, dan continuous 241,3 × 139,7 mm masing-masing satu halaman. MediaBox diperiksa agar ukuran setengah lembar benar-benar landscape. Cabang tambahan Transfer lainnya juga satu halaman, termasuk angka dan totalnya.
- PASS: PDF dirender menjadi PNG dan diperiksa langsung. Tabel, nominal, QRIS, total nontunai, serta nota uang muka tidak terpotong.
- PASS: 14 sampel kontras teks pada dua tema memenuhi 4,5:1; kontras batas input 3,56:1 (terang) / 4,81:1 (gelap), fokus 6,70:1 / 9,36:1, memenuhi batas nonteks 3:1.

## Catatan interaksi yang diuji

- Katalog: pencarian dan tab barang/jasa, tambah barang, tambah/kurangi jumlah, potongan, serta total berubah sesuai input.
- Checkout: Cash/Tempo, metode tunai/BCA/BRI/BNI/EDC/QRIS, pelanggan opsional/wajib, nomor mobil, tenor angka, dan pilihan tanpa/dengan uang muka.
- Validasi: pelanggan wajib, tenor tidak sah, uang diterima kurang, uang muka di luar batas, dan laba manual negatif/melebihi cicilan.
- Print: dua klik cepat tidak menggandakan transaksi; simpan yang kehilangan acknowledgment memakai request ID yang sama saat dicoba lagi; batal cetak, cetak ulang, dan kegagalan printer tetap memakai transaksi tersimpan.
- Nota: cetak otomatis setelah frame siap, pengaturan cetak, cetak ulang, penutupan dengan Escape, dan pemulihan fokus setelah mencetak.
- Rekap pelanggan: seluruh pilihan urutan, pencarian, halaman berikut/sebelumnya, Lihat nota, dan hapus filter pelanggan.
- Cicilan: nominal, batas laba manual, otomatis laba lebih dulu, simpan pembayaran, dan pembaruan rekap.
- Laporan: pilih tanggal, simpan pengambilan Bian, dan cetak dokumen harian yang terpisah dari layar aplikasi.
- Akses: F2, F4, Enter, Space, Escape, fokus yang terlihat; tema terang/gelap dan lebar 375, 768, 1280 px tanpa overflow halaman.
- Keadaan data: memuat, kosong, gagal, coba lagi, dan tombol cetak yang dinonaktifkan saat data belum tersedia. Error HTTP 503 dalam log sengaja dibuat untuk pengujian; tidak ada error halaman atau API tak dikenal.

## Antislop Delivery Gate

Pemeriksaan berikut berlaku pada bagian yang direvisi. Bukti interaksi dan angka pengujian tercantum di atas dan di `clickthrough.json`.

| Item | Hasil dan bukti |
| --- | --- |
| R-01 | PASS: navy dan amber mengikuti identitas aplikasi; warna membedakan konteks dan aksi Print. |
| R-02 | PASS: teks baru diperiksa tanpa em dash dan tanpa kalimat promosi. |
| R-03 | PASS: tiga lebar layar diuji, tanpa overflow halaman; tabel mempunyai area scroll sendiri. |
| R-04 | PASS: ikon pencarian, jumlah, riwayat, dan cetak menunjukkan tindakan sebenarnya. |
| R-05 | PASS: satu panel checkout dan tabel rekap dibangun dari alur kasir yang diminta. |
| R-06 | PASS: font aplikasi dipertahankan untuk label dan angka; laporan cetak memakai Arial 9,5 pt yang diuji. |
| R-07 | PASS: tidak menambahkan pola latar. |
| R-08 | PASS: tidak menambahkan panah dekoratif pada tombol. |
| R-09 | PASS: label status menjelaskan status transaksi, tanpa badge promosi baru. |
| R-10 | PASS: tidak menambahkan blur atau glassmorphism. |
| R-11 | PASS: panel dan kontrol mengikuti radius desain yang sudah ada. |
| R-12 | PASS: bayangan mengikuti dialog yang memang berada di atas halaman. |
| R-13 | PASS: tidak menambahkan glow; fokus memakai ring yang terukur. |
| R-14 | PASS: kelompok formulir dan total mempunyai hierarki sesuai keputusan pembayaran. |
| R-15 | PASS: Print, Lihat nota, Simpan pembayaran, dan Cetak menjalankan tindakan yang disebut. |
| R-16 | PASS: teks baru menyebut transaksi, tenor, uang muka, piutang, dan laba tanpa buzzword. |
| R-17 | PASS: tampilan memakai API dan input transaksi; data contoh hanya di fixture pengujian. |
| R-18 | PASS: tidak menambahkan testimoni atau identitas orang pada produk. |
| R-19 | PASS: perubahan mengikuti MOTION 1, tanpa animasi berulang baru. |
| R-20 | PASS: identitas bengkel dan bentuk buku kas yang sudah ada dipertahankan. |
| R-21 | PASS: kontrol dan tampilan diuji pada dua tema. |
| R-22 | PASS: tidak membuat ilustrasi baru. |
| R-23 | PASS: arah berasal dari gambar pemilik dan identitas aplikasi; tidak ada aset baru. |
| R-24 | PASS: navigasi checkout, piutang, laporan, dan perpindahan ke nota diuji pada tujuan nyata. |
| R-25 | PASS: 14 sampel teks dan empat pasangan batas/fokus dihitung dengan rumus WCAG. |
| R-26 | PASS: catatan klik mencakup kontrol yang diubah dan membuktikan hasil tindakannya. |
| R-27 | PASS: memuat, kosong, gagal, dan coba lagi diuji pada katalog, rekap, dan laporan. |
| R-28 | PASS: tidak menambahkan FAQ. |
| R-29 | PASS: warna inti navy, amber, dan netral mengikuti aplikasi. |
| R-30 | PASS: struktur mengikuti kasir Perkasa Jaya dan referensi pemilik. |
| R-31 | PASS: alasan setiap keputusan utama dicatat pada bagian arah tampilan. |
| R-32 | PASS: keyboard, Escape, F2/F4, dan fokus setelah cetak tercatat dalam tes browser. |
| R-33 | PASS: perubahan ditulis langsung pada source; tidak ada skrip pengganti string untuk menerapkan UI. |
| R-34 | PASS: checkout, rekap, dan laporan diperiksa pada tema terang/gelap. |
| R-35 | PASS: build, tes backend, klik browser, dan inspeksi render PDF selesai. |
| R-36 | PASS: tidak menambahkan klaim keamanan, kinerja, atau klaim pelanggan. |
| R-37 | PASS: arah pemilik, identitas aplikasi, dan dials dinyatakan untuk revisi. |
| R-38 | PASS: data produk dan transaksi berasal dari API; fixture terpisah dari produk operasional. |
| Focal point | PASS: Print menjadi aksi akhir checkout; sisa piutang ditegaskan untuk penagihan. |
| Whitespace | PASS: jarak memisahkan pilihan transaksi, identitas pelanggan, pembayaran, dan total. |
| Accent | PASS: amber menandai Print dan tujuan aktif yang sudah ada. |
| Identity | PASS: logo bengkel, tipografi angka, dan tabel buku kas tetap konsisten. |
| Dials | PASS: ENERGY 1 / RHYTHM 1 / MOTION 1 sesuai formulir dan tabel kerja yang tenang. |
| Design Read | PASS: arah mengikuti referensi pemilik dan dokumen identitas aplikasi. |
| C-1 | PASS: alasan visual tertulis dan terkait pekerjaan kasir. |
| C-2 | PASS: kontrol yang direvisi mempunyai hasil interaksi yang diuji. |
| C-3 | PASS: penambahan hanya melayani checkout, piutang, laba, dan laporan cetak. |
| C-4 | PASS: tema, breakpoint, keyboard, dan keadaan data tercakup pada tes browser. |
| C-5 | PASS: angka produksi tidak direkayasa; contoh uji memakai fixture terpisah. |

Riwayat pembayaran lama tidak dihitung ulang atau ditulis ulang. Aturan baru dipakai pada pembayaran yang dicatat setelah revisi, dengan pengurangan laba yang sudah pernah diakui. Cetakan printer fisik tetap perlu dilihat pada perangkat pengguna; tidak ada pekerjaan cetak fisik yang dikirim selama pengujian.
