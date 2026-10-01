> **Tindak lanjut:** migrasi telah dilaksanakan setelah instruksi pengguna untuk mempertahankan data sumber. Status terbaru ada di [MIGRASI-AKTIF.md](MIGRASI-AKTIF.md). Temuan di bawah merekam keadaan sebelum migrasi.

# Pemeriksaan spreadsheet dan Apps Script

Tanggal pemeriksaan: 29 September 2026.

Sumber: `C:/Users/Bima/Downloads/Perkasa Jaya - Store information system (1).xlsx` dan `referensi-spreadsheet/Code.gs`.
SHA-256 workbook: `7faa480412138dde21e5b00028677725b9d3b5b74578c44751a76b8b4d7772bb`.

Pemeriksaan ini membaca file lokal dan kode aplikasi. Tidak menjalankan Apps Script, mengimpor data, atau mengubah database operasional. Nilai rumus dibaca dari hasil kalkulasi yang tersimpan dalam XLSX; openpyxl tidak menghitung ulang rumus Google Sheets. Kecocokan database aplikasi yang sedang berjalan belum diuji.

## Keputusan pengguna

- Pajak laporan tetap hanya TAX = 1, tarif aplikasi 0,5%.
- Dasar tempo mengikuti total setelah tambahan harga dan potongan, bukan aturan script lama yang mengambil kategori Tire dan harga tunai. Dikonfirmasi saat pemeriksaan ini.
- Potongan checkout baru tetap rupiah dari total nota. Data historis mempertahankan hasil hitungan sumber; diskon per unit dari spreadsheet harus dikonversi ke total baris, bukan ditafsirkan sebagai diskon total nota.

## Inventaris sumber

Workbook berisi 14 sheet. Jumlah berikut adalah baris dengan tanggal yang dikenali, bukan jumlah invoice unik.

| Sheet | Baris | Rentang tanggal |
| --- | ---: | --- |
| SELLING CASH | 10.522 | 2025-01-01 sampai 2026-09-28 |
| SELLING CREDIT | 902 | 2025-01-02 sampai 2026-09-27 |
| PURCHASE | 1.503 | 2025-01-02 sampai 2026-09-29 |
| PAYMENT CREDIT | 706 | 2025-01-22 sampai 2026-09-28 |
| PAYMENT SUPPLIER | 446 | 2025-01-21 sampai 2026-09-29 |
| EXPENSES | 1.206 | 2025-11-01 sampai 2026-09-29 |
| TRANSFER | 1.266 | 2025-09-02 sampai 2026-09-29 |

DATABASE berisi 475 baris produk: 391 TAX = 1 dan 84 TAX = 0, termasuk satu nilai TAX berbentuk teks "1". Pemilik: BIAN 292, Bian 1, IBU 147, NON 20, POLOSAN 1, NON VPT 12, NON VAT 2. Sebanyak 35 label di luar BIAN/IBU belum memiliki padanan pemilik di aplikasi; jangan otomatis dialihkan ke Bian/Ibu.

Terdapat 110 baris produk dengan saldo stok akhir negatif. Lima baris tambahan memiliki nama duplikat tanpa membedakan kapitalisasi; importer saat ini menggabungkannya menjadi 470 produk. Jumlah baris bukan hasil pemeriksaan stok fisik.

## Hasil rekonsiliasi

Parser `backend/lib/workbooks.py` dijalankan terhadap file baru secara lokal, dengan penggantian nama file hanya dalam proses pemeriksaan. Parser menghasilkan 13.782 event dan 12 pemeriksaan bulanan REPORT tahun 2026. Semua 9 angka per bulan cocok dengan nilai tersimpan dengan toleransi Rp0,01. Januari–September berisi aktivitas; Oktober–Desember masih nol. Ini memverifikasi profil REPORT lama, bukan membuktikan laporan pajak, stok, pembelian, atau database aktif identik.

Detail angka: `../test_reports/spreadsheet/reconciliation.json`.
Contoh rumus dan struktur sheet: `../test_reports/spreadsheet/workbook-structure.json`.

## Pemetaan dan perbedaan aplikasi

| Bagian | Sumber spreadsheet/script | Keadaan aplikasi / tindak lanjut |
| --- | --- | --- |
| Pemilik dan TAX produk | DATABASE J dan K; additem menulis D:M | Importer belum mengambil J/K. Checkout baru sudah menyimpan owner/TAX. Perlu memperbaiki pemetaan impor dan merencanakan pembaruan data yang sudah pernah diimpor. |
| Pemilik/TAX tunai | SELLING CASH O/P, VLOOKUP ke master | Import riwayat belum menyimpan atribut ini. Nilai ekspor merupakan nilai saat file diekspor, bukan bukti atribut pada tanggal transaksi dahulu. |
| Tempo | SELLING CREDIT H harga tunai, I harga tempo, O total tunai, P total tempo, T pemilik | Importer mengambil nominal tempo P, tetapi belum membawa harga dasar/selisih/owner. Sheet ini tidak punya kolom TAX tersendiri. Pemetaan ke master perlu mendeteksi nama tidak ditemukan/duplikat dan mencatat asal nilai. |
| Get Data penjualan | Code.gs getSellingData: tunai P = 1; tempo S === "Tire", nominal O | Berbeda dari keputusan terbaru. Pertahankan TAX = 1 dengan total tempo bersih di aplikasi; jangan menyalin filter tempo lama. |
| Potongan | SELLING CASH I2 = (G2-H2)*F2 | H adalah potongan per unit. Contoh qty 2, H Rp10.000 berarti total potongan Rp20.000. Checkout baru tetap potongan total nota sesuai permintaan pengguna. |
| Komisi SERVICE | Tunai J = 50% total I setelah diskon; tempo K = 50% total tunai O | lib/excel_rules.py saat ini menghitung SERVICE dari selling_price yang diteruskan checkout. Diskon/tambahan tempo dapat membuat komisi profil Excel berbeda. Perlu koreksi khusus profil Excel tanpa menyamakan otomatis dengan model margin POS. |
| Pembelian | PURCHASE C tanggal masuk, D tanggal faktur, F TAX, H pemilik, L harga fixed, M pembayaran, N total | Get Data pembelian memakai bulan tanggal faktur D dan TAX F = 1. Importer Store belum membawa riwayat PURCHASE; laporan bulanan penjualan tidak menggantikan laporan ini. |
| Transfer | TRANSFER C tanggal, D nominal, E via | Importer belum membawa ledger ini. Tidak boleh menganggap semua transaksi SELLING CASH dibayar uang tunai atau menebak pasangan invoice hanya dari tanggal. |
| Stok | DATABASE Q = G + N - O - P | Importer memakai saldo akhir Q, tetapi membulatkan/mengubah negatif menjadi nol. Ini sengaja tidak identik dengan file; perlu rekonsiliasi stok sebelum migrasi. |
| Tagihan | Saldo pelanggan/distributor di DATABASE dan pembayaran terpisah | Data agregat tidak selalu menyediakan tautan invoice/jatuh tempo. Jangan membuat alokasi cicilan atau saldo baru yang menggandakan sejarah. |
| Sumber impor | FILES['store'] masih nama file lama `(wecompress.com).xlsx` | Upload lokal ini belum otomatis menjadi sumber importer. Jangan mengganti file lalu mengimpor ulang tanpa rencana pembaruan: ID impor memakai hash file, sehingga versi baru bisa menggandakan data versi lama. |

## Catatan Apps Script

- Ada deklarasi ganda `getData`, `saveexpenses`, dan `clear12`. Audit harus melihat definisi yang berlaku, bukan menganggap semuanya proses terpisah.
- `adddistributor` membaca penghitung DATABASE AJ1, sedangkan rumus penghitung yang ditemukan berada di AI1. Perlu dicek sebelum memakai fungsi ini; alamat sel tidak cocok.
- `tosellingoil` mengarah ke SELLING OIL, tetapi sheet tersebut tidak ada di workbook yang diberikan.
- `onEdit` hanya memeriksa alamat M2, tanpa membatasi nama sheet. Generator tanggal menggunakan tahun saat script berjalan; hasil historis berpotensi berbeda dari tahun laporan yang dipilih.
- REPORT U4 menjumlah U7:U1002, sedangkan fungsi Get Data bisa menulis lebih dari 996 baris. Data di bawah rentang itu tidak masuk total U4.
- File ini memuat fungsi `onOpen` dan `onEdit`. Daftar trigger yang dipasang lewat pengaturan, manifest, dan script terpisah belum tersedia untuk diperiksa.

## Urutan penyamaan data

1. Tentukan pemetaan label pemilik selain BIAN/IBU serta penyelesaian duplikat dan stok negatif.
2. Perbaiki pembacaan atribut produk/riwayat, sumber harga tempo, serta profil komisi SERVICE dengan mempertahankan data asal.
3. Buat pratinjau perubahan terhadap data yang sudah diimpor, dengan identitas stabil dan deteksi konflik antarversi file.
4. Rekonsiliasi per bulan/pemilik/TAX serta saldo tagihan dan stok; sertakan PURCHASE/TRANSFER sebagai sumber terpisah bila laporan itu ingin disamakan.
5. Tinjau hasil konkret sebelum menerapkan migrasi ke database aktif.

Status: pemeriksaan dan pemetaan selesai; penyamaan/migrasi data belum dilakukan.
