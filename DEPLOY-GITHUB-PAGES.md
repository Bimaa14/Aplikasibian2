# Frontend GitHub Pages + backend Railway

## Deployment

1. Repository `Bimaa14/Aplikasibian2`: buka Settings > Pages, pilih Source **GitHub Actions**. GitHub Free mendukung Pages untuk repository publik; jangan mempublikasikan secret agar dapat memakai Pages.
2. Atur Variables pada service backend Railway:
   - `CORS_ORIGINS=https://bimaa14.github.io`
   - `COOKIE_SECURE=true`
   - `COOKIE_SAMESITE=none`
3. Commit dan push perubahan frontend, backend, serta `.github/workflows/deploy-frontend.yml` ke branch `main`.
4. Pastikan Railway melakukan deployment kode backend terbaru dan menerapkan perubahan Variables.
5. Tunggu workflow **Deploy frontend to GitHub Pages** sukses di tab Actions.
6. Buka https://bimaa14.github.io/Aplikasibian2/#/login dan uji login, refresh, logout, serta unduhan laporan.

## Setup demo admin satu lần

1. Railway backend: tambahkan variable **`DEMO_SETUP_KEY`** dengan secret acak minimal 32 byte. Jangan gunakan default atau simpan secret di repository.
2. Tunggu deployment selesai, lalu buka `https://aplikasibian2-production.up.railway.app/api/setup-demo`.
3. Isi secret dan password baru minimal 12 karakter, maksimal 72 byte UTF-8. Form memakai POST body, bukan URL.
4. Klik **Buat akun demo admin**, lalu tutup halaman dan login secara terpisah sebagai `demo-admin`. Tidak ada login otomatis.
5. Endpoint dinonaktifkan jika variable tidak ada atau kurang dari 32 byte. Endpoint hanya membuat akun; akun yang sudah ada tidak diubah.
6. Setelah setup, hapus `DEMO_SETUP_KEY` dari Railway untuk menonaktifkan endpoint. Akun admin tetap ada; hapus atau ubah secara manual bila tidak diperlukan.

## Konfigurasi build

Workflow memasukkan URL publik backend melalui `VITE_BACKEND_URL` dan base path `/Aplikasibian2/` melalui `VITE_BASE_PATH`. Jika nama repository atau backend berubah, perbarui nilai tersebut dalam workflow. Jangan menaruh password, MONGO_URL, atau secret pada variabel `VITE_*`: nilainya masuk ke bundle publik.

Development lokal tanpa variabel tersebut tetap memakai proxy `/api` milik Vite. HashRouter menjaga refresh route seperti `#/produk` tetap bekerja tanpa rewrite server.

## Cookie lintas situs

GitHub Pages dan Railway berbeda situs. `SameSite=None; Secure` diperlukan untuk cookie login lintas situs, tetapi browser yang memblokir third-party cookies masih dapat menggagalkan login. Solusi lebih andal adalah domain frontend/API dalam satu situs atau hosting satu origin. GitHub Pages tidak menyediakan proxy API.

Backend memeriksa Origin pada request yang mengubah data saat `COOKIE_SAMESITE=none`. Client non-browser dalam mode ini juga harus mengirim Origin yang diizinkan. Jangan gunakan wildcard pada CORS_ORIGINS.

GitHub Pages hanya menyediakan hosting frontend; biaya dan batas Railway tetap berlaku. Rotasi password MongoDB yang pernah terlihat pada screenshot sebelum penggunaan produksi.
