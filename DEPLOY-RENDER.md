# Demo client gratis di Render + MongoDB Atlas

Frontend dan API berjalan di satu alamat HTTPS Render. Login menggunakan cookie
`Secure; SameSite=Lax`, dan frontend memanggil `/api` pada alamat yang sama. Laptop
bisa dimatikan setelah layanan cloud aktif. Format nota tetap menggunakan kode
aplikasi yang sama.

Paket ini menyiapkan deployment, belum menerbitkan layanan atau menyalin database.
Gunakan database demo baru `bian_client_demo`, bukan database operasional.

## 1. Siapkan repository dan Atlas

1. Gunakan repository **private** dan berikan Render akses ke repository tersebut.
   Pastikan source yang berubah dan file baru sudah ikut commit/push; Render
   membangun isi repository, bukan perubahan yang hanya ada di laptop.
   Workbook yang sudah ada di repository memuat data usaha. Docker hanya membawa
   tiga workbook acuan yang diperlukan; `.env`, backup, hasil tes, dan arsip tidak
   masuk image. Workbook disimpan di backend, bukan di folder frontend publik.
2. Di [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register), buat cluster
   **Free** untuk demo. Atlas Free menyediakan kapasitas 512 MB; periksa pilihan
   paket sebelum membuatnya. [Batas Atlas Free](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/).
3. Buat database user khusus demo, dengan akses baca/tulis hanya pada database
   `bian_client_demo`. Gunakan password baru. [Pengaturan database user Atlas](https://www.mongodb.com/docs/atlas/security-add-mongodb-users/).
4. Salin connection string Atlas untuk driver Python. Masukkan kredensial user
   demo; jika password mengandung karakter khusus, gunakan nilai yang sudah
   URL-encoded. Simpan URI ini sebagai `MONGO_URL` di Render, bukan di source atau
   variabel `VITE_*`.

## 2. Buat layanan Render

1. Di [Render Dashboard](https://dashboard.render.com/), pilih **New > Blueprint**
   dan hubungkan repository private berisi perubahan ini.
2. Gunakan `render.yaml` di root. Blueprint membuat satu **Web Service**, runtime
   **Docker**, paket **Free**, region **Singapore**. Jangan tambahkan Postgres,
   disk berbayar, instance kedua, atau service preview.
3. Saat diminta, isi `MONGO_URL` dengan URI demo Atlas dan `DEMO_SETUP_KEY` dengan
   secret acak minimal 32 karakter. Secret hanya untuk setup awal. Nilai lain
   sudah ada pada Blueprint. [Konfigurasi Blueprint](https://render.com/docs/blueprint-spec).
4. Di service Render, buka **Connect > Outbound** dan tambahkan semua rentang IP
   outbound yang ditampilkan ke **Network Access** Atlas. Build pertama boleh
   selesai sebelum akses database siap; backend akan sehat setelah koneksinya
   diizinkan. [IP outbound Render](https://render.com/docs/outbound-ip-addresses).
5. Tunggu deployment selesai dan `/healthz` mengembalikan status HTTP 200. Buka
   alamat `https://<nama-layanan>.onrender.com/`. Nama alamat yang sebenarnya
   ditampilkan oleh Render dan mungkin memiliki suffix.

Docker membangun frontend memakai Node 22, base path `/`, backend URL kosong, dan
overlay development dinonaktifkan. Runtime Python 3.12 memakai
`backend/requirements-local.txt`, termasuk dependensi laporan PDF dan Atlas.
Uvicorn menggunakan port Render dan **satu worker**. [Docker di Render](https://render.com/docs/docker).

## 3. Buat akun dan lakukan tes

1. Buka `https://<alamat-demo>/api/setup-demo`. Isi `DEMO_SETUP_KEY` dan password
   baru minimal 12 karakter, maksimal 72 byte UTF-8. Akun yang dibuat bernama
   `demo-admin` dan mempunyai akses admin penuh.
2. Login dari halaman aplikasi sebagai `demo-admin`. Database baru belum berisi
   produk/transaksi. Tambahkan beberapa produk dan transaksi contoh; jangan
   menjalankan migrasi atau impor database operasional untuk demo ini.
3. Setelah akun berhasil dibuat, halaman dan request setup otomatis ditutup
   dengan HTTP 404 meskipun `DEMO_SETUP_KEY` masih terpasang. Akun tetap tersimpan
   di Atlas. Hapus key pada pembaruan terencana berikutnya menggunakan prosedur
   di bawah; tidak perlu mengganti alamat layanan hanya untuk menutup setup awal.
4. Tes login, refresh, logout, tambah produk, checkout, retur, laporan, unduhan
   PDF/CSV, dan cetak nota dari perangkat client. Cocokkan ukuran kertas pada
   browser dan printer client dengan ukuran nota yang dipilih.

Data transaksi demo disimpan di Atlas. File lokal container bersifat sementara;
workbook acuan berasal dari image Docker sehingga tersedia lagi saat layanan
dihidupkan. Jangan menyimpan backup database di disk layanan Free.

## 4. Pembaruan dengan jeda layanan

Backend harus mempunyai satu penulis aktif per database. `CLOUD_SINGLE_WRITER=true`
mengambil pengunci pemilik di MongoDB sebelum pemulihan transaksi dimulai. Proses
kedua gagal start selama pengunci masih dimiliki proses pertama. Jangan matikan
pengaturan ini di cloud. `numInstances: 1` tidak menjamin hanya satu proses saat deploy:
Render biasanya menjalankan instance baru sebelum mematikan yang lama, termasuk
pada **Restart service**. Karena itu automatic deploy dan preview dinonaktifkan.
[Urutan deploy Render](https://render.com/docs/deploys#zero-downtime-deploys).

Untuk memperbarui demo:

1. Selesaikan semua request/transaksi client, lalu **Suspend** layanan lama.
   Tunggu status suspended dan log shutdown selesai; status HTTP tidak tersedia
   saja belum membuktikan proses backend sudah berhenti. Shutdown normal melepas
   pengunci MongoDB. Jangan menjalankan backend lokal pada database demo yang sama.
2. Setelah proses lama berhenti, buat layanan pengganti dari commit terbaru dengan
   konfigurasi Docker/env yang sama dan database demo yang sama. Pakai nama
   layanan baru, **Free**, satu instance, automatic deploy **Off**, dan health
   check `/healthz`. Lakukan initial deploy layanan pengganti.
3. Pastikan `/healthz`, login, laporan, dan data demo bekerja. Bagikan alamat
   pengganti ke client. Biarkan layanan lama suspended agar tidak ada penulis kedua.
   Untuk pembaruan berikutnya, ulangi proses ini. Setelah setup akun, layanan
   pengganti tidak perlu `DEMO_SETUP_KEY`.

Prosedur ini menerima downtime dan perubahan alamat demo. Dokumentasi resmi
menyediakan aksi [suspend](https://api-docs.render.com/reference/suspend-service-1)
dan [resume](https://api-docs.render.com/reference/resume-service-1), tetapi tidak
menjamin deploy terbaru dapat dibangun saat suspended lalu dipilih saat resume;
karena itu panduan ini menggunakan initial deploy layanan pengganti.

Render dapat mengganti instance juga saat maintenance platform, termasuk pada
layanan Free tanpa pemberitahuan sebelumnya. Pengunci MongoDB menolak proses
pengganti selama proses sebelumnya masih memiliki pengunci, sehingga maintenance
atau restart dapat menimbulkan downtime dan kegagalan start yang perlu ditangani.
[Maintenance Render](https://render.com/docs/platform-maintenance).

Pengunci tidak mempunyai expiry/TTL. Jika container dipaksa berhenti, pengunci
bisa tertinggal dan start berikutnya gagal dengan pesan database masih dikunci.
Pastikan **semua** proses yang memakai database demo sudah berhenti, termasuk
service lama/pengganti dan backend lokal. Kemudian di Atlas **Browse Collections**,
pilih database `bian_client_demo`, koleksi `runtime_locks`, filter
`{"_id":"financial-writer"}`, dan hapus hanya satu dokumen pengunci tersebut.
Lakukan initial deploy layanan pengganti sesudahnya. Jangan menghapus pengunci
ketika pemiliknya masih aktif; jangan menghapus `financial_operations` atau
koleksi transaksi untuk mengatasi kegagalan start.

## Batas gratis yang perlu diketahui

Render Free tidur setelah 15 menit tanpa traffic, lalu biasanya memerlukan sekitar
satu menit untuk bangun. Ada kuota 750 jam instance per workspace per bulan,
serta batas bandwidth dan build. Jika tanpa metode pembayaran kuota terlampaui,
layanan/build dapat ditangguhkan. Untuk kebutuhan gratis, pilih Free dan jangan
mengaktifkan upgrade atau pembelian tambahan. [Batas Render Free](https://render.com/docs/free).

Demo ini cocok untuk meminta client mencoba alur aplikasi dengan data yang bisa
dibuat ulang. Kesiapan produksi memerlukan proses pembaruan/pemulihan yang sudah
diuji di hosting serta backup database tersendiri.

## Verifikasi persiapan, 3 Oktober 2026

- Build frontend dan uji build statis pada `/` serta `/Aplikasibian2/` lolos;
  gambar login dan logout desktop/HP mengikuti alamat aplikasi.
- 55 tes backend untuk hosting, health, pengunci cloud, PDF, keamanan transaksi,
  dan setup akun lolos dengan fixture palsu atau database sementara terpisah.
- Uji satu origin dengan backend dan MongoDB asli lokal lolos: setup akun lalu
  penutupan setup, login cookie, checkout, nota/cetak ulang, PDF laporan,
  refresh, logout, dan login ulang. Database uji dihapus setelah server berhenti.
  Bukti: `test_reports/deployment/cloud-demo-1791033875951/results.json`.
- Blueprint lolos schema resmi Render; dependensi Linux Python 3.12 berhasil
  di-resolve/download. Kode format nota tidak diubah.

Docker tidak tersedia pada komputer pengujian, jadi image belum dijalankan.
Render, Atlas, HTTPS publik, dan printer fisik belum diuji. Uji langsung pada
hosting tetap diperlukan sebelum membagikan alamat kepada client.

Perintah regresi dari root project (MongoDB lokal harus aktif):

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_web_hosting.py tests/test_cloud_writer.py tests/test_report_pdf_export.py tests/test_financial_safety.py tests/test_setup_demo.py -n 0 -q
cd ../frontend
node tests/deployment.browser.mjs
node tests/cloud-demo.browser.mjs
```
