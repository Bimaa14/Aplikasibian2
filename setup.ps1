# Script untuk setup lokal Aplikasi Bian

Write-Host "1. Menyiapkan Backend..."
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

Write-Host "`n2. Seed Akun Admin & Kasir..."
python seed.py

Write-Host "`n3. Setup selesai. Untuk menjalankan backend:"
Write-Host "   cd backend"
Write-Host "   .\venv\Scripts\activate"
Write-Host "   uvicorn server:app --host 0.0.0.0 --port 8001 --reload"

Write-Host "`n4. Menyiapkan Frontend..."
cd ..\frontend
npm install -g yarn
yarn install

Write-Host "`n5. Setup selesai. Untuk menjalankan frontend:"
Write-Host "   cd frontend"
Write-Host "   yarn dev"
