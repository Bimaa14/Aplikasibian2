# Menyamakan laporan demo dengan sheet terbaru

Kode Docker menggunakan `Perkasa Jaya - Store information system (3).xlsx` melalui
`STORE_WORKBOOK_PATH`. File (1) tetap tersedia; aplikasi lokal yang belum memasang
variabel tersebut tetap menggunakan sumber sebelumnya.

Pembaruan data dan kode harus dipasang bersama. Mengganti workbook saja belum
mengganti riwayat impor di Atlas. Menjalankan kode lama setelah pembaruan data
dapat membaca metadata sumber yang lama.

Laporan baseline mengikuti sumber (3), termasuk nilai cache dan koreksi manual.
Transaksi aplikasi yang sudah ada tetap disimpan tetapi memiliki
`report_excluded=true`; pembayaran lama ditandai per pembayaran, bukan per
tagihan. Transaksi dan pembayaran baru tanpa penanda tetap masuk laporan.
Stok, akun, pelanggan, supplier, dan saldo tagihan tetap dipertahankan.

September 2026: pendapatan Rp399.283.000; modal Rp343.145.000; laba Rp45.278.000;
spooring Rp10.860.000; pembayaran supplier Rp397.114.574; pengeluaran Rp41.735.000;
laba bersih Rp3.543.000. Angka ini diverifikasi terhadap `REPORT!E15:M15`.

Oktober 2026 pada sumber (3): pendapatan Rp48.675.000; modal Rp40.895.000;
laba Rp5.765.000; spooring Rp2.015.000; pembayaran supplier Rp59.030.000;
pengeluaran Rp3.975.000; laba bersih Rp1.790.000.

Salinan uji cocok pada seluruh 12 bulan tahun 2026, termasuk urutan dan isi baris
Get Data penjualan serta pembelian. Pemeriksaan hash memastikan database sumber,
salinan kandidat, dan workbook tetap sama setelah pengujian. Suite pengujian
fokus pada repository demo lulus 148 kasus. Frontend dan format nota tidak diubah.

## Urutan pembaruan online

1. Siapkan kode ini di repository `Bimaa14/Demo-Bian`. Tunda push sampai
   deployment lama berhenti, agar auto deploy tidak beradu dengan kunci penulis.
2. Dari checkout lokal yang memiliki Python dan dependensi aplikasi, jalankan
   `backend/tools/update_atlas_report_baseline.py --folder <folder-baru>`.
   Folder baru harus di `.cache/report-baseline/`. Isi password Atlas langsung
   pada jendela helper, lalu klik **Cek data online**.
3. Di Railway, buka service **bian-client-demo**, tab **Deployments**, lalu
   menu titik tiga deployment **Active** → **Remove**. Tunggu service **Offline**.
   Jangan menghapus service atau project.
4. Klik **Perbarui laporan** di helper. Helper mengambil backup sebelum menulis,
   menolak perubahan sejak pengecekan, dan memeriksa hash seluruh koleksi.
5. Setelah helper menyatakan selesai, push commit kode terbaru. Deploy commit
   terbaru itu di Railway; jangan redeploy commit lama. Pastikan 1 replica dan
   1 worker, serta tidak ada variabel Railway yang menimpa `STORE_WORKBOOK_PATH`
   dengan file (1) atau (2).
6. Periksa `/healthz` dan laporan September/Oktober setelah server hidup.

Password tidak disimpan dalam source, backup, status, atau log. Backup privat
berada di `.cache/` dan tidak masuk Git maupun Docker. Jika pembaruan gagal
setelah mulai menulis, kunci operasi ditahan untuk pemeriksaan. Jangan menghapus
kunci milik proses lain atau menyalakan server terhadap pembaruan yang belum
terverifikasi.
