# Nota penjualan

Nota menggantikan struk thermal pada checkout POS dan cetak ulang di Riwayat
Transaksi. Kwitansi cicilan piutang/hutang tetap merupakan dokumen tersendiri.

## Pemakaian

1. Pada checkout tunai, isi **Uang diterima**. Default adalah uang pas; kembalian
   dihitung otomatis. Backend menolak nominal di bawah total.
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
Margin nota tunai: kiri/kanan 12 mm dan atas/bawah 6 mm; nota tempo memakai kiri/kanan 18 mm. Nota tunai mengikuti contoh kertas: font 10 pt, kolom nama barang lebih lebar, dan area tabel minimal 16 baris pada setengah lembar. Pratinjau memakai dokumen yang
sama dengan cetak, dalam iframe terpisah agar menu aplikasi tidak ikut tercetak.
Tabel panjang dilanjutkan ke halaman berikutnya dengan header kolom berulang; jumlah akhir tampil sekali. Nota tunai juga mengulang nomor transaksi pada header tabel.

## Format tempo (buku nota)

Transaksi tempo otomatis memakai form tersendiri sesuai foto: BANYAKNYA, UKURAN, MERK, SATUAN, TOTAL; penerima, tanggal, jatuh tempo, dan ruang tanda tangan Tanda Terima/Hormat Kami. Harga satuan termasuk tambahan tempo dan total baris setelah alokasi potongan. Ukuran, merek, dan alamat pelanggan disimpan saat checkout untuk cetak ulang. Data lama yang tidak lengkap ditampilkan dengan nama barang/tanda kosong, bukan diisi dari master terbaru.

Catatan khusus tempo dapat diedit melalui Identitas toko. Ukuran kertas masih memakai pilihan 9,5 x 5,5 atau 9,5 x 11 inci yang sudah tersedia; ukuran fisik buku pada foto belum diberikan. PDF setengah lembar sudah diuji, hasil pada printer fisik belum diuji.

## Data nota

- SKU, uang diterima, dan kembalian disimpan bersama transaksi baru, sehingga
  perubahan master produk tidak mengubah kode dan harga pada cetak ulang.
- Transaksi lama yang belum memiliki SKU/uang diterima/kembalian menampilkan
  tanda `—`; tidak mengarang nominal atau memakai SKU produk terbaru.
- Potongan adalah selisih positif `harga × jumlah − subtotal` dari rincian
  tersimpan, dalam total per baris. Potongan item diisi per baris (total seluruh unit
  pada baris itu). Potongan total nota tambahan dialokasikan proporsional terhadap
  sisa nilai setelah potongan item, dengan ketelitian sen.
- Komisi item bernama SERVICE adalah 50% dari subtotal setelah seluruh potongan,
  termasuk tambahan tempo. Item lainnya memakai service fee master DATABASE
  per unit dikali jumlah. Fee tersimpan saat checkout untuk laporan dan cetak ulang.
- Tambahan harga tempo dapat diisi per unit saat checkout. Harga, tambahan, dan potongan tersimpan untuk cetak ulang.
- Nota tempo menampilkan jatuh tempo dan total tagihan awal (pembayaran cicilan memiliki kwitansi terpisah); nota transaksi retur diberi tanda dibatalkan.

## Verifikasi

`npm run build` memeriksa TypeScript dan build aplikasi.

Uji browser dengan data tiruan, tanpa memanggil API operasional:

```powershell
npm install --no-save --package-lock=false playwright
node tests/sales-note.browser.mjs
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
