> **Panduan perhitungan aktif, 3 Oktober 2026:** nota mengikuti [acuan Excel terbaru](../README.accounting.md) dan [hasil verifikasi](../refrensi-spreadsheet/PENYAMAAN-PERHITUNGAN-2026-10-03.md).

# Nota penjualan

Nota menggantikan struk thermal pada checkout POS dan cetak ulang di Riwayat
Transaksi. Kwitansi cicilan piutang/hutang tetap merupakan dokumen tersendiri.

## Pemakaian

1. Pada checkout tunai, transfer BCA/BRI/BNI, EDC, atau QRIS, isi **Uang diterima**
   sesuai nominal yang benar-benar diterima, termasuk jika melebihi tagihan.
   Default mengikuti total; **Uang pas** mengembalikan input ke total terbaru.
   Tunai menampilkan kembalian, metode lain menampilkan kelebihan pembayaran.
   Backend menolak nominal di bawah total. Tempo tetap mencatat tagihan awal;
   pembayaran piutang memakai kwitansi tersendiri.
2. Di pratinjau nota, pilih ukuran: **9,5 × 5,5 inci** (setengah lembar,
   mengikuti proporsi contoh) atau **9,5 × 11 inci** (ukuran kemasan kertas).
3. Buka **Identitas toko** untuk mengubah nama, alamat, nomor telepon, dan
   catatan bawah. Nomor telepon awal sengaja kosong karena foto kurang jelas.
   Pengaturan disimpan di browser komputer ini; menghapus data browser akan
   mengembalikannya ke nilai awal.
4. Klik **Cetak Nota** untuk printer fisik. Pilih **Portrait**, samakan ukuran form pada driver printer, gunakan
   skala 100%, matikan header/footer browser, dan cetak satu salinan untuk
   kertas NCR 3 ply. Pengaturan panjang form pada printer harus sesuai pilihan
   panjang nota, khususnya saat memakai setengah lembar.

Klik **Simpan PDF**, lalu pilih **Save as PDF**. Ukuran halaman mengikuti pilihan di pratinjau:
241,3 x 139,7 mm untuk setengah lembar atau 241,3 x 279,4 mm untuk satu lembar.
Ukuran ini ditetapkan melalui CSS `@page`, sehingga PDF tidak memakai ukuran
default A4/Letter. **Cetak Nota** memakai `@page size: auto` agar form dan
orientasi Portrait dari driver printer fisik dipakai tanpa rotasi otomatis
akibat halaman PDF yang lebarnya lebih besar daripada tingginya.

Dokumen dicetak hitam di atas kertas putih tanpa latar berwarna atau gambar
lubang perforasi. Warna rangkap berasal dari kertas. Lebar dokumen 241,3 mm;
Margin nota tunai: kiri/kanan 12 mm dan atas/bawah 6 mm; nota tempo memakai kiri/kanan 18 mm. Teks nota memakai Arial reguler, 10 pt untuk transaksi langsung dan 11 pt untuk tempo, tanpa garis tambahan pada huruf. Judul, header kolom, dan total memakai huruf tebal untuk membedakan informasi utama. Kolom nama barang tetap lebih lebar; ruang kosong tabel menyesuaikan rincian dan catatan agar nota pendek muat pada setengah lembar. Pratinjau memakai dokumen yang
sama dengan cetak, dalam iframe terpisah agar menu aplikasi tidak ikut tercetak.
Tabel panjang dilanjutkan ke halaman berikutnya dengan header kolom berulang; jumlah akhir tampil sekali. Nota tunai juga mengulang nomor transaksi pada header tabel.

Nota pembayaran langsung (tunai, transfer, EDC, dan QRIS) mencantumkan rekening
di kiri bawah: Bank BCA, 3761155405, A.N Wati Wulandari. Header, ukuran tabel,
lebar kolom, dan posisi total tetap mengikuti format sebelumnya.

Untuk Epson LX-310 ESC/P, gunakan resolusi 240 x 144 dpi pada preferensi printer.
Resolusi ini sudah diterapkan pada preferensi pengguna Windows di komputer ini;
ukuran kertas dan orientasi tetap mengikuti pilihan pengguna. Cetak ulang dari
aplikasi terbaru agar tambahan rekening ikut tercetak.

## Format tempo (buku nota)

Transaksi tempo otomatis memakai form tersendiri sesuai foto: BANYAKNYA, UKURAN, MERK, SATUAN, TOTAL; penerima, tanggal, jatuh tempo, dan ruang tanda tangan Tanda Terima/Hormat Kami. Harga satuan termasuk tambahan tempo dan total baris setelah potongan per unit. Ukuran, merek, dan alamat pelanggan disimpan saat checkout untuk cetak ulang. Data lama yang tidak lengkap ditampilkan dengan nama barang/tanda kosong, bukan diisi dari master terbaru.

Catatan khusus tempo dapat diedit melalui Identitas toko. Ukuran kertas masih memakai pilihan 9,5 x 5,5 atau 9,5 x 11 inci yang sudah tersedia; ukuran fisik buku pada foto belum diberikan. PDF setengah lembar sudah diuji, hasil pada printer fisik belum diuji.

## Data nota

- SKU, uang diterima, dan kembalian/kelebihan disimpan bersama transaksi baru
  untuk semua metode pembayaran langsung, sehingga
  perubahan master produk tidak mengubah kode dan harga pada cetak ulang.
- Nota dan cetak ulang menampilkan nominal diterima yang tersimpan. Kelebihan
  pembayaran tidak menambah total penjualan, pajak, atau nominal retur tagihan.
- Transaksi lama yang belum memiliki SKU menampilkan tanda `-`; uang diterima
  atau selisih yang belum tersimpan ditulis **Tidak tercatat**, tanpa mengarang
  nominal atau memakai SKU produk terbaru.
- Potongan checkout diisi **per unit**, mengikuti SELLING CASH H. Qty 2 dengan potongan Rp10.000 menghasilkan total potongan Rp20.000. Nota menampilkan total potongan dari rincian tersimpan; checkout tidak lagi menampilkan potongan tambahan total nota.
- Komisi item **bernama SERVICE** untuk tunai adalah 50% subtotal setelah potongan. Untuk tempo, komisi adalah 50% total **harga tunai** sebelum tambahan/potongan tempo (SELLING CREDIT O); tambahan harga tempo tidak meningkatkan komisi tersebut. Item lain memakai service fee DATABASE per unit dikali qty.
- Harga satuan tempo termasuk tambahan per unit. Potongan per unit mengurangi total tagihan tempo, sedangkan harga tunai dasar tetap tersimpan untuk komisi dan Get Data. Harga, modal asal, komisi, kategori, dan potongan transaksi baru disimpan saat checkout; baris impor mempertahankan angka ekspor/manual sumber.
- Modal laporan dibulatkan naik ke kelipatan Rp5.000 mengikuti sumber. Komisi dan cabang laba mengikuti kategori, termasuk modal sekali pada kategori SERVICE. Total nota tetap nominal yang ditagihkan kepada pelanggan.
- Pembayaran pertama piutang menggunakan default laba Q+K bagi kelompok pelanggan/tanggal invoice; pembayaran berikutnya default nol. Nilai ini milik pembukuan pembayaran, bukan tambahan tagihan atau perubahan total nota. Riwayat pembayaran lama tidak dihitung ulang.
- Nota tempo menampilkan jatuh tempo dan total tagihan awal (pembayaran cicilan memiliki kwitansi terpisah); nota transaksi retur diberi tanda dibatalkan.

## Verifikasi

`npm run build` memeriksa TypeScript dan build aplikasi.

Pada revisi 7 Oktober 2026, 49 regresi nominal pembayaran backend,
`sales-note.browser.mjs`, dan `note-print-quality.browser.mjs` lolos.
PDF nota pendek tunai/transfer/tempo muat satu halaman pada kedua ukuran,
termasuk simulasi area cetak lebih kecil; semua 50 barang pada nota panjang
tetap lengkap. Teks PDF memakai font asli tanpa gambar raster. Rincian dan
contoh hasil tersedia di [laporan verifikasi pembayaran/cetak](../test_reports/nota/VERIFIKASI-PEMBAYARAN-CETAK-2026-10-07.md).

Pada revisi 3 Oktober 2026, build, `sales-note.browser.mjs`, dan lima skenario `excel-alignment.browser.mjs` lolos tanpa page error. Tes pagination di bawah tersedia sebagai verifikasi tambahan dan belum dijalankan ulang pada revisi ini.

Uji browser dengan data tiruan, tanpa memanggil API operasional:

```powershell
npm install --no-save --package-lock=false playwright
node tests/sales-note.browser.mjs
node tests/note-print-quality.browser.mjs
node tests/excel-alignment.browser.mjs
# Opsional: pagination, belum dijalankan ulang pada revisi ini
node tests/note-pagination.browser.mjs
```

Uji pagination memeriksa jumlah halaman PDF nota tunai/tempo pada kedua ukuran
kertas, termasuk simulasi area cetak 0,25 inci lebih kecil dari form. Nota pendek
harus satu halaman; nota 50 item harus tetap memuat seluruh item dan total.
Pengujian ini memakai `pypdf` dari virtual environment backend.
Tinggi cetak mengikuti isi, bukan tinggi tetap kertas, untuk mencegah halaman
kedua kosong akibat batas area cetak printer. Pilih form printer 9,5 x 5,5 inci
untuk setengah lembar, skala 100%, serta matikan header/footer browser.

Chrome lokal dipakai secara default; `CHROME_PATH` dapat menunjuk executable
browser lain yang kompatibel. Port 3101 harus kosong. Artefak PDF dan screenshot
ditulis ke `test_reports/nota`. Pengujian backend terkait nominal dan cetak ulang
terdapat di `backend/tests/test_financial_safety.py`, memakai database uji terpisah.

PDF sudah diperiksa untuk ukuran halaman dan kelengkapan tabel panjang.
Cetak fisik serta ketepatan tarikan kertas pada printer klien belum diuji.
