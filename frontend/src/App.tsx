import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import AppShell from "@/components/AppShell";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import PosPage from "@/pages/PosPage";
import TransactionsPage from "@/pages/TransactionsPage";
import ProductsPage from "@/pages/ProductsPage";
import CustomersPage from "@/pages/CustomersPage";
import SuppliersPage from "@/pages/SuppliersPage";
import DebtPage from "@/pages/DebtPage";
import ExpensesPage from "@/pages/ExpensesPage";
import StockInPage from "@/pages/StockInPage";
import VehiclesPage from "@/pages/VehiclesPage";
import ExcelReportsPage from '@/pages/ExcelReportsPage';
import ImportPage from '@/pages/ImportPage';
import StockSnapshotPage from '@/pages/StockSnapshotPage';
import ReportsPage from "@/pages/ReportsPage";
import LaravelBundlePage from "@/pages/LaravelBundlePage";

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  return (
    <>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/pos" element={<PosPage />} />
          <Route path="/transaksi" element={<TransactionsPage />} />
          <Route path="/produk" element={<ProductsPage />} />
          <Route path="/pelanggan" element={<CustomersPage />} />
          <Route path="/distributor" element={<SuppliersPage />} />
          <Route path="/piutang-hutang" element={<DebtPage />} />
          <Route path="/stok-masuk" element={<StockInPage />} />
          <Route path="/kendaraan" element={<VehiclesPage />} />
          <Route path="/laporan" element={<ReportsPage />} />
        <Route path="/laporan-excel" element={<ExcelReportsPage />} />
        <Route path="/impor" element={<ImportPage />} />
        <Route path="/snapshot-stok" element={<StockSnapshotPage />} />
          <Route path="/pengeluaran" element={<ExpensesPage />} />
          <Route path="/laravel" element={<LaravelBundlePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster />
    </>
  );
}
