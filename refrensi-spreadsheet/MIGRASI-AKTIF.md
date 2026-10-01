# Pembaruan master aktif ? 30 September 2026

Master aktif sekarang berasal dari `imports/workbooks/Laporan_Data_Barang_30-09-2026.xlsx`: 445 barang, stok/harga sesuai file, tidak ada stok negatif. Sebanyak 319 produk lama diarsipkan (tidak muncul di POS/master aktif), bukan dihapus dari referensi riwayat.

Referensi kepemilikan dan TAX tetap `Perkasa Jaya - Store information system (1).xlsx`, sheet DATABASE. Pencocokan memakai kode atau nama persis setelah normalisasi spasi/huruf: 157 barang cocok, 288 belum dipetakan (owner/TAX null, bukan TAX=0). Hanya TAX=1 masuk dasar PPh sesuai aturan aplikasi sebelumnya. Barang belum dipetakan perlu dilengkapi sebelum laporan pajak transaksi baru dianggap lengkap. Kategori yang belum cocok memakai default aplikasi TIRE dan perlu diperiksa juga.

Nama barang kode S_005 kosong di sumber dan dipertahankan demikian. Barang berkode berbeda tetap menjadi produk terpisah meskipun namanya sama.

Riwayat transaksi dan koleksi bisnis selain produk diperiksa dengan fingerprint sebelum/sesudah dan tidak berubah. Backup lengkap sebelum penggantian tersedia lokal di `test_reports/spreadsheet/inventory-replacement-20260930_052423/backup.bson.json`; hasil verifikasi di `result.json`. Backup mengandung data privat dan dikecualikan dari Git.

Tool: `backend/tools/replace_inventory.py`. Harus dijalankan saat backend berhenti; lock OS mencegah penulisan bersamaan. Perubahan memakai jurnal pemulihan. Jangan jalankan ulang setelah transaksi baru tanpa meninjau dampak penggantian saldo stok.

Verifikasi: 55 tes regresi terkait lolos, ditambah tes integrasi penggantian/backup lolos. API aktif mengembalikan 445 produk, nol stok negatif, 288 TAX belum dipetakan. Percobaan seluruh suite terhalang dua modul tes lama yang membutuhkan paket requests dan 16 tes dilewati; bukan klaim seluruh suite lolos.

---

## Riwayat migrasi sebelumnya (master berikut sudah digantikan)

# Migrasi Store aktif — 29 September 2026

Sumber tunggal aktif: `Perkasa Jaya - Store information system (1).xlsx` di folder ini. File lama tetap arsip dan tidak perlu dihapus. Apps Script tetap referensi, tidak dijalankan oleh aplikasi.

## Data yang sudah masuk

| Data | Hasil |
| --- | ---: |
| Master produk, stok FINAL, kepemilikan dan TAX | 475 baris |
| Invoice historis | 7.533 |
| Rincian penjualan historis | 11.423 |
| Transaksi aplikasi yang dipertahankan | 10 |
| Riwayat pembelian | 1.503 baris |
| Riwayat transfer | 1.266 baris |
| Master pelanggan dari workbook | 111 baris sumber |
| Master distributor dari workbook | 22 baris sumber |
| Arsip nilai seluruh 14 sheet | 19.964 baris |

Impor lama Store diganti dalam database salinan, bukan ditumpuk. Produk dengan nama sama tetap dipisahkan menurut baris sumber. Satu baris penjualan dengan qty dan nominal nol (`SELLING CASH!10277`) hanya masuk arsip, tidak dibuatkan invoice kosong.

Stok memakai DATABASE kolom Q (FINAL), bukan G (stok awal). Semua 110 saldo negatif dipertahankan sesuai instruksi pengguna; penjualan barang dengan stok tidak cukup tetap ditolak. Label kolom J dipertahankan (BIAN/Bian dinormalisasi menjadi bian; IBU menjadi ibu; NON/POLOSAN/NON VPT/NON VAT tetap ada). Nilai sumber mentah juga disimpan. Total stok termasuk baris jasa/saldo referensi sumber; bukan penghitungan stok fisik baru.

Sepuluh transaksi aplikasi tetap ada. Stok mengikuti snapshot sheet persis, tanpa memutar ulang pengurangan stok dari transaksi aplikasi tersebut. Bila transaksi itu belum tercakup dalam stok sheet, penyesuaian fisik harus dilakukan terpisah.

Saldo piutang/hutang September yang sebelumnya sudah ada dipertahankan. Saldo agregat DATABASE dan pembayaran sumber tersimpan di arsip/ledger; tidak dibuat menjadi invoice baru dengan tanggal atau alokasi cicilan hasil tebakan. Retur otomatis riwayat impor tetap ditolak karena memakai snapshot stok akhir.

## Get Data dan PPh

Buka **Laporan Kas & Pajak → Get Data**. Pilih bulan, **Penjualan/Pembelian**, pemilik, kategori dan TAX, lalu klik **Get Data**. Default TAX = 1. Sumber Database aplikasi memakai data aktif; Pratinjau spreadsheet membaca file referensi tanpa menyimpan apa pun. CSV mengikuti filter yang sudah diterapkan.

Kolom mengikuti keluaran script REPORT: tanggal transaksi, jenis barang, nomor faktur, tanggal faktur, harga termasuk PPN, harga tanpa PPN, nilai PPN, nama pembeli/penjual. Kolom tanpa PPN dan PPN kosong seperti keluaran script; tidak dibuat tarif PPN baru. Pembelian disaring berdasarkan tanggal faktur, bukan tanggal masuk barang. Form Stok Masuk baru menyediakan tanggal faktur.

PPh = 0,5% dari penjualan bersih item yang TAX DATABASE K = 1. TAX lain tidak masuk. Tempo memakai harga tempo setelah potongan sesuai keputusan pengguna, tidak mengikuti filter Tire/harga tunai dari script lama. Nilai TAX historis dipetakan dari master saat ekspor; tidak mengklaim atribut itu sama pada tanggal transaksi dahulu.

## Nota tempo

Form terpisah sesuai foto: Banyaknya, Ukuran, Merk, Satuan, Total; penerima dan jatuh tempo; Tanda Terima dan Hormat Kami. Ukuran/merek/alamat pelanggan tersimpan saat checkout. Catatan tempo dapat diubah pada Identitas toko. Ukuran kertas memakai pengaturan nota yang ada; belum diuji pada printer fisik klien.

## Verifikasi dan pemulihan

- 475 baris stok/pemilik/TAX cocok dengan sumber.
- 42 pasangan bulan/jenis laporan cocok untuk total dan dasar TAX.
- 12 periode REPORT lama cocok.
- 53 tes backend, build frontend, tes browser, dan PDF nota tempo lulus saat migrasi.
- Endpoint produk, Get Data penjualan/pembelian, pajak, dan pratinjau impor diperiksa setelah restart.

Database aktif: `bian_store_candidate_20260929_222923_cada18` (nama kandidat dipertahankan setelah aktivasi). Database sebelum migrasi: `aplikasi_bian`, masih utuh. Backend `.env` menunjuk database aktif baru.

Backup sumber dan rencana migrasi berada di `test_reports/spreadsheet/bian_store_candidate_20260929_222923_cada18/`. Backup konfigurasi: `backend/.env.pre-store-migration`. File backup berisi data usaha dan autentikasi; tidak untuk dibagikan sebagai contoh publik.

Untuk kembali ke database lama: hentikan backend, ubah hanya `DB_NAME` di `backend/.env` menjadi `aplikasi_bian`, lalu jalankan kembali backend. Jangan lakukan setelah ada transaksi baru di database aktif tanpa rekonsiliasi transaksi tersebut. Aktivasi migrasi tidak menghapus database lama.

Tool persiapan `backend/tools/prepare_store_candidate.py` hanya menulis database salinan baru. Tool aktivasi menolak bila sumber bisnis atau file spreadsheet berubah setelah pratinjau, dan memerlukan backend berhenti agar kunci satu penulis dapat diperoleh.
