# Menjalankan dan menguji backend lokal

Jalankan satu proses backend, satu worker, untuk satu database lokal. Dari folder `backend`:

```powershell
.\venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8001 --reload
```

Di terminal lain, dari folder `frontend`, jalankan `npm run dev`. Vite membaca
`HOST` dan `PORT` dari `.env`, dengan default `127.0.0.1:3000`.

## Konsistensi transaksi

Checkout, retur, dan stok masuk menyimpan jurnal pemulihan di koleksi
`financial_operations` sebelum mengubah dokumen. Penulisan MongoDB memakai
`w=1, j=true` agar jurnal database diakui sebelum langkah berikutnya.

- Bila langkah gagal sebelum commit, perubahan stok, invoice, detail, dan
  piutang/hutang milik operasi itu dibatalkan.
- Bila proses berhenti, backend memulihkan operasi sebelum menerima request.
  Operasi yang sudah commit dipertahankan; yang belum commit dibatalkan.
- Pemulihan yang terputus dapat dilanjutkan tanpa mengembalikan stok dua kali.
- Pembacaan API menunggu operasi finansial selesai, termasuk rollback.
- Checkout dari halaman POS menyertakan `request_id`. Mengulang request dengan
  ID dan isi yang sama mengembalikan transaksi sebelumnya. ID dipertahankan
  selama halaman masih terbuka; setelah reload browser, periksa riwayat sebelum
  mengulangi checkout yang hasilnya belum diketahui.
- Kasir tetap boleh melakukan retur dan menghapus pengeluaran.

Ini mekanisme untuk deployment lokal satu proses, bukan transaksi MongoDB
lintas server. Penguncian proses mencegah backend kedua di komputer dan akun OS
yang sama memakai database bernama sama. Jangan menjalankan backend melalui
akun OS/komputer lain pada database yang sama atau mengubah database langsung
saat aplikasi aktif. Jangan menghapus jurnal atau field `_financial_operation`.
Untuk multi-server/multi-worker, gunakan desain transaksi MongoDB replica set.

Backup tetap diperlukan: mekanisme ini tidak mengatasi kerusakan disk. Jangan
menyalin sebagian koleksi sebagai backup; jurnal dan data bisnis harus ikut dalam
snapshot yang konsisten. Data tidak konsisten dari versi sebelumnya tidak
direkonsiliasi otomatis oleh perubahan ini. Impor Excel belum memakai jurnal ini.

## Tes regresi terisolasi

MongoDB lokal harus berjalan. Pasang alat tes sekali:

```powershell
.\venv\Scripts\python.exe -m pip install pytest pytest-asyncio pytest-xdist
.\venv\Scripts\python.exe -m pytest tests/test_financial_safety.py -q
```

Tes membuat database `bian_safety_test_<UUID>` baru untuk setiap kasus, lalu
menghapus hanya database tersebut. Default koneksi adalah
`mongodb://127.0.0.1:27017`; dapat diganti lewat `TEST_MONGO_URL`.
Tes tidak menulis ke database aplikasi dari `backend/.env`.

Cakupan: checkout bersamaan, request ulang, kegagalan sesudah penulisan,
rollback stok masuk/retur, proses berhenti paksa, pemulihan berulang, cicilan lalu
retur, akses kasir, dan autentikasi sesi. Ini bukan audit keamanan lengkap atau
pengujian pemadaman listrik fisik.

Tes lama yang mengakses server HTTP membutuhkan `TEST_ADMIN_USERNAME`,
`TEST_ADMIN_PASSWORD`, `TEST_CASHIER_USERNAME`, `TEST_CASHIER_PASSWORD`, dan
`BACKEND_URL` yang mengarah ke server uji. Beberapa tes laporan memakai
`REACT_APP_BACKEND_URL`. Jangan arahkan tes lama ke data operasional.

`autoimport.py` sekarang membaca `IMPORT_ADMIN_USERNAME` dan
`IMPORT_ADMIN_PASSWORD` dari environment. Password akun database tidak diubah.
Menghapus password dari kode tidak menghapus salinannya dari riwayat atau arsip;
ganti password akun operasional bila pernah memakai kredensial yang tersebar.
