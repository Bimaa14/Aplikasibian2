"""Serves the parallel Laravel 11 + Filament v3 + Livewire v3 reference bundle (raw files on disk)."""

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from lib.auth import require_user

router = APIRouter(prefix="/laravel-bundle", tags=["laravel-bundle"], dependencies=[Depends(require_user)])

LARAVEL_DIR = Path(__file__).resolve().parents[2] / "archive" / "laravel_reference"

DESCRIPTIONS = {
    "README.md": "Panduan instalasi + perintah terminal langkah demi langkah (Laravel 11 + Filament v3 + Livewire v3 + MySQL)",
    "routes/web.php": "Rute web: POS Livewire full-page component dan panel Filament",
    "database/migrations/2025_01_01_000001_create_products_table.php": "Migration products: type, sku, stock, modal, harga jual, komisi montir",
    "database/migrations/2025_01_01_000002_create_customers_table.php": "Migration customers (pelanggan)",
    "database/migrations/2025_01_01_000003_create_suppliers_table.php": "Migration suppliers (distributor)",
    "database/migrations/2025_01_01_000004_create_transactions_table.php": "Migration transactions (penjualan POS): invoice, metode bayar, laba, status retur",
    "database/migrations/2025_01_01_000005_create_transaction_details_table.php": "Migration transaction_details: snapshot modal & komisi per baris",
    "database/migrations/2025_01_01_000006_create_accounts_receivable_table.php": "Migration accounts_receivable (piutang customer)",
    "database/migrations/2025_01_01_000007_create_accounts_payable_table.php": "Migration accounts_payable (hutang distributor)",
    "database/migrations/2025_01_01_000008_create_expenses_table.php": "Migration expenses (pengeluaran)",
    "app/Models/Product.php": "Model Product + unitProfit() (barang: jual-modal, jasa: jual-komisi)",
    "app/Models/Customer.php": "Model Customer + sisa piutang per pelanggan",
    "app/Models/Supplier.php": "Model Supplier + sisa hutang per distributor",
    "app/Models/Transaction.php": "Model Transaction + markReturned() (retur: kembalikan stok, hanguskan piutang)",
    "app/Models/TransactionDetail.php": "Model TransactionDetail + profit() per baris",
    "app/Models/AccountsReceivable.php": "Model AccountsReceivable + scope overdue",
    "app/Models/AccountsPayable.php": "Model AccountsPayable + scope overdue",
    "app/Models/Expense.php": "Model Expense (pengeluaran)",
    "app/Livewire/Pos/PosPage.php": "Komponen Livewire v3 halaman POS: pencarian, keranjang, checkout, aturan kredit, cetak struk",
    "resources/views/livewire/pos/pos-page.blade.php": "Blade view halaman POS (Tailwind + modal struk thermal 80mm)",
    "app/Filament/Widgets/FinancialStatsWidget.php": "Widget dashboard keuangan: pendapatan, laba kotor barang, laba bersih, piutang/hutang",
    "app/Filament/Resources/ReceivableResource.php": "Resource piutang dengan indikator lewat jatuh tempo + aksi tandai lunas",
    "app/Filament/Resources/ProductResource.php": "Resource produk (CRUD data master) dengan form kondisional barang/jasa",
}


class LaravelBundleFile(BaseModel):
    path: str
    description: str
    code: str


@router.get("", response_model=List[LaravelBundleFile])
async def get_laravel_bundle():
    files: List[LaravelBundleFile] = []
    if not LARAVEL_DIR.exists():
        return files
    for path in sorted(LARAVEL_DIR.rglob("*")):
        if path.is_file() and path.suffix in {".php", ".md"}:
            rel = path.relative_to(LARAVEL_DIR).as_posix()
            try:
                code = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            files.append(LaravelBundleFile(path=rel, description=DESCRIPTIONS.get(rel, ""), code=code))
    return files
