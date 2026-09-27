// Hand-written mirrors of the backend Pydantic models — nothing infers across the HTTP
// boundary, so this file must change in the same edit as backend/models/*.

export type ProductType = "barang" | "jasa";
export type ProductOwner = "bian" | "ibu";
export type PaymentMethod = "cash" | "credit";
export type TxStatus = "completed" | "returned";
export type DebtStatus = "unpaid" | "partial" | "paid" | "void";
export type UserRole = "admin" | "kasir";

export interface Product {
  category: 'TIRE' | 'OIL' | 'SERVICE' | 'COMPLEMENTARY';
  id: string;
  type: ProductType;
  sku: string;
  name: string;
  brand: string;
  size: string;
  owner: ProductOwner | null;
  stock: number;
  cost_price: number;
  selling_price: number;
  service_fee: number;
}

export interface Customer {
  id: string;
  name: string;
  phone: string;
  address: string;
}

export interface Supplier {
  id: string;
  name: string;
  phone: string;
  address: string;
}

export interface TransactionDetail {
  id: string;
  transaction_id: string;
  product_id: string;
  product_name: string;
  product_type: ProductType;
  owner: ProductOwner | null;
  qty: number;
  price: number;
  cost_price: number;
  service_fee: number;
  subtotal: number;
}

export interface Transaction {
  id: string;
  invoice_number: string;
  date: string;
  date_key: string;
  customer_id: string | null;
  customer_name: string | null;
  payment_method: PaymentMethod;
  total_amount: number;
  barang_amount: number;
  jasa_amount: number;
  total_cost: number;
  service_fee: number;
  total_profit: number;
  status: TxStatus;
  due_date: string | null;
  vehicle_plate: string | null;
  details: TransactionDetail[];
}

// --- Stok masuk (barang masuk dari distributor) ---
export interface StockInItem {
  product_id: string;
  product_name: string;
  sku: string;
  qty: number;
  cost_price: number;
  subtotal: number;
  stock_before: number;
  stock_after: number;
}

export interface StockIn {
  id: string;
  reference: string;
  date: string;
  date_key: string;
  supplier_id: string;
  supplier_name: string;
  invoice_number: string;
  due_date: string;
  total_amount: number;
  note: string;
  payable_id: string | null;
  items: StockInItem[];
}

// --- Riwayat kendaraan ---
export interface VehicleServiceSummary {
  plate: string;
  visit_count: number;
  total_spent: number;
  last_visit: string | null;
  last_customer: string | null;
  last_tire: string | null;
  last_tire_date: string | null;
  last_oil: string | null;
  last_oil_date: string | null;
}

export interface VehicleDetail extends VehicleServiceSummary {
  services: Transaction[];
}

// --- Laporan bulanan ---
export interface ExpenseByCategory {
  category: string;
  amount: number;
}

export interface TopProduct {
  name: string;
  sku: string;
  qty: number;
  revenue: number;
}

export interface MonthlyReport {
  month: string;
  month_label: string;
  revenue_total: number;
  barang_revenue: number;
  jasa_revenue: number;
  cost_of_goods: number;
  gross_profit_barang: number;
  service_fee_total: number;
  expenses_total: number;
  expenses_by_category: ExpenseByCategory[];
  net_profit: number;
  transaction_count: number;
  returned_count: number;
  returned_amount: number;
  new_receivables: number;
  receivables_paid: number;
  stock_in_total: number;
  top_products: TopProduct[];
  available_months: string[];
}

export interface AccountsReceivable {
  paid_amount: number; remaining: number; payments: DebtPayment[];
  issued_date: string; days_overdue: number; days_remaining: number; due_label: string; aging_bucket: string | null;
  legacy_payment_history_missing: boolean;
  id: string;
  transaction_id: string;
  invoice_number: string;
  customer_id: string;
  customer_name: string;
  amount: number;
  due_date: string;
  status: DebtStatus;
}

export interface AccountsPayable {
  paid_amount: number; remaining: number; payments: DebtPayment[];
  issued_date: string; days_overdue: number; days_remaining: number; due_label: string; aging_bucket: string | null;
  legacy_payment_history_missing: boolean;
  id: string;
  supplier_id: string;
  supplier_name: string;
  invoice_number: string;
  amount: number;
  due_date: string;
  status: DebtStatus;
}

export interface Expense {
  id: string;
  date: string;
  amount: number;
  category: string;
  description: string;
}

export interface DebtPayment {
  id: string; amount: number; payment_date: string; method: string; note: string; profit_amount: number;
}

export interface User {
  id: string;
  name: string;
  username: string;
  role: UserRole;
}

export interface DayRevenue {
  date_key: string;
  label: string;
  revenue: number;
  profit: number;
}

export interface DashboardStats {
  today: string;
  total_revenue: number;
  total_cost: number;
  gross_profit: number;
  jasa_amount: number;
  service_fee_total: number;
  expenses_total: number;
  net_profit: number;
  transaction_count: number;
  today_revenue: number;
  receivables_outstanding: number;
  receivables_overdue: number;
  payables_outstanding: number;
  payables_overdue: number;
  receivables_aging: Record<string, number>;
  payables_aging: Record<string, number>;
  low_stock: Product[];
  revenue_by_day: DayRevenue[];
  overdue_receivables: AccountsReceivable[];
  overdue_payables: AccountsPayable[];
  recent_transactions: Transaction[];
}

export interface LaravelBundleFile {
  path: string;
  description: string;
  code: string;
}
