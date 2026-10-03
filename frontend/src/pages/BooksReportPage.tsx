import GetDataReportView from './GetDataReportView';
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from 'sonner';
import { FileSpreadsheet, CalendarDays, Calculator, Download, Landmark, Printer, TrendingUp } from "lucide-react";
import { ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { apiGet, apiPut, fileUrl } from "@/lib/api";
import { formatIDR, getApiErrorMessage, todayLocalISO } from "@/lib/format";
import { cn } from "@/lib/utils";
import MonthlySalesView from './MonthlySalesView';
import SalesFilters, { initialSalesFilters, salesFilterQuery } from '@/components/SalesFilters';

type DailyReport = {
  non_cash_sales: number;
  date: string;
  cash_sales: number;
  receivable_payments: number;
  transfer_payments: number;
  montir_fee: number;
  expenses: number;
  net_cash: number;
  modal_bian: number;
  laba_bian: number;
  final_cash: number;
  parameters_saved: boolean;
  modal: number;
  laba: number;
  spooring: number;
  oil_revenue: number;
  oil_benefit: number;
};

type FundingGroup = { label: string; total: number; items: { name: string; amount: number }[] };
type MonthlyReport = {
  month: string; month_label: string;
  omzet: number; omzet_bruto: number; oli: number;
  distributor_payment: number; expenses: number; expenses_total: number; gaji: number;
  pajak_recorded: number;
  store: { pendapatan: number; modal: number; laba: number; spooring: number; supplier: number; pengeluaran: number; total_modal: number; nett_laba: number; nett_spooring: number };
  pph_final: number; pph_rate: number;
  sisa_aset: number; stok_value: number; stok_basis: string; piutang_outstanding: number; hutang_outstanding: number;
  funding: { modal: FundingGroup; laba: FundingGroup };
  owner_summary: { owner: string; label: string; omzet: number; laba: number }[];
};

type TaxReport = {
  unassigned_tax_net: number;
  full_tax_base: number; tax_summary_row_limit: number; tax_eligible_line_count: number;
  month: string; month_label: string; basis: string;
  omzet_base: number; omzet_bruto: number; rate: number; pph_final: number;
};

const TABS = [
  { key: "get-data", label: "Get Data", icon: FileSpreadsheet },
  { key: "transaksi", label: "Transaksi Bulanan", icon: CalendarDays },
  { key: "harian", label: "Laporan Harian", icon: CalendarDays },
  { key: "bulanan", label: "Laporan Bulanan", icon: TrendingUp },
  { key: "pajak", label: "Estimasi PPh Final", icon: Calculator },
] as const;

function Row({ label, value, tone = "plain", strong = false, sub }: { label: string; value: string; tone?: "plain" | "minus" | "plus" | "total"; strong?: boolean; sub?: string }) {
  return (
    <div className={cn("flex items-center justify-between gap-3 py-2.5 px-3 rounded-lg", tone === "total" && "bg-primary/10 border border-primary/20", strong && tone !== "total" && "bg-secondary/40")}>
      <div>
        <p className={cn("text-sm", strong ? "font-semibold" : "text-muted-foreground")}>{label}</p>
        {sub ? <p className="text-[11px] text-muted-foreground/70">{sub}</p> : null}
      </div>
      <span className={cn("font-mono tabular-nums text-sm",
        tone === "minus" && "text-red-700 dark:text-red-400", tone === "plus" && "text-emerald-700 dark:text-emerald-400",
        (tone === "total" || strong) && "font-bold")}>{value}</span>
    </div>
  );
}

function ReportActions({ csvHref, testid }: { csvHref: string; testid: string }) {
  return (
    <div className="flex items-center gap-2 print:hidden">
      <a data-testid={`${testid}-csv-button`} href={csvHref} className="inline-flex items-center gap-1.5 rounded-md bg-secondary/60 px-3 py-2 text-sm font-medium transition-colors hover:text-foreground">
        <Download className="size-4" /> Unduh CSV
      </a>
      <button data-testid={`${testid}-print-button`} onClick={() => window.print()} className="inline-flex items-center gap-1.5 rounded-md bg-secondary/60 px-3 py-2 text-sm font-medium transition-colors hover:text-foreground">
        <Printer className="size-4" /> Cetak
      </button>
    </div>
  );
}

function DailyView() {
  const today = todayLocalISO();
  const [date, setDate] = useState(today);
  const q = useQuery({ queryKey: ["books-daily", date], queryFn: () => apiGet<DailyReport>(`/books/daily?date=${date}`) });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Tanggal</label>
          <input type="date" data-testid="daily-date-input" className="bk-control h-9 w-auto" value={date} max={today} onChange={(e) => setDate(e.target.value)} />
        </div>
        <ReportActions csvHref={fileUrl(`/books/daily/csv?date=${date}`)} testid="daily" />
      </div>
      {q.isPending ? <LoadingBlock /> : q.isError ? <ErrorBlock error={q.error} onRetry={() => void q.refetch()} /> : q.data && (
        <div className="grid gap-4 lg:grid-cols-2" data-testid="daily-report">
        <div className="bk-panel p-3">
          <Row label="Penjualan tunai tanpa oli" value={formatIDR(q.data.cash_sales)} tone="plus" strong sub="SELLING CASH termasuk transfer / EDC / QRIS" />
          <Row label="Pembayaran piutang masuk" value={`+ ${formatIDR(q.data.receivable_payments)}`} tone="plus" />
          <Row label="Dikurangi: transfer / EDC / QRIS" value={`− ${formatIDR(q.data.transfer_payments)}`} tone="minus" sub="Riwayat TRANSFER dan penerimaan non-tunai baru" />
          <Row label="Dikurangi: komisi montir" value={`− ${formatIDR(q.data.montir_fee)}`} tone="minus" />
          <Row label="Dikurangi: pengeluaran dari kasir" value={`− ${formatIDR(q.data.expenses)}`} tone="minus" sub="Sumber pembayaran Cashier" />
          <div className="my-2 border-t border-border" />
          <Row label="Kas bersih sebelum Bian" value={formatIDR(q.data.net_cash)} strong />
          <Row label="Dikurangi: modal Bian" value={`− ${formatIDR(q.data.modal_bian)}`} tone="minus" />
          <Row label="Dikurangi: laba Bian" value={`− ${formatIDR(q.data.laba_bian)}`} tone="minus" />
          <Row label="Kas bersih akhir" value={formatIDR(q.data.final_cash)} tone="total" strong />
          <DailyParameters key={date} report={q.data} />
        </div>
        <div className="space-y-4">
          <div className="bk-panel p-3" data-testid="daily-capital-profit">
            <p className="mb-2 px-1 text-sm font-semibold">Modal dan Laba</p>
            <Row label="Modal toko" value={formatIDR(q.data.modal)} strong />
            <Row label="Laba toko" value={formatIDR(q.data.laba)} strong sub="Setelah pengeluaran kasir dan laba Bian" />
            <Row label="Spooring / Service" value={formatIDR(q.data.spooring)} />
            <p className="mt-2 px-1 text-xs text-muted-foreground">Mengikuti rincian DAILY REPORT: modal toko, laba setelah pengeluaran kasir, dan spooring termasuk komisi tempo.</p>
          </div>
          <div className="bk-panel p-3" data-testid="daily-oil-report">
            <p className="mb-2 px-1 text-sm font-semibold">Laporan Oli</p>
            <Row label="Pendapatan oli" value={formatIDR(q.data.oil_revenue)} strong sub="SELLING CASH, termasuk transfer / EDC / QRIS" />
            <Row label="Benefit oli" value={formatIDR(q.data.oil_benefit)} tone="total" strong sub="Laba oli yang tercatat pada transaksi" />
          </div>
        </div>
        </div>
      )}
    </div>
  );
}

function DailyParameters({ report }: { report: DailyReport }) {
  const queryClient = useQueryClient();
  const [modal, setModal] = useState(String(report.modal_bian));
  const [laba, setLaba] = useState(String(report.laba_bian));
  const save = useMutation({
    mutationFn: () => apiPut(`/books/daily/parameters/${report.date}`, { modal_bian: Number(modal), laba_bian: Number(laba) }),
    onSuccess: () => {
      toast.success('Pengambilan Bian disimpan');
      void queryClient.invalidateQueries({ queryKey: ['books-daily', report.date] });
      void queryClient.invalidateQueries({ queryKey: ['excel-reports'] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  return (
    <div className="mt-4 space-y-2 border-t border-border pt-3 print:hidden">
      <p className="text-sm font-semibold">Pengambilan Bian</p>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-muted-foreground">Modal (Rp)<input aria-label="Modal Bian" type="number" min="0" className="bk-control mt-1 w-full" value={modal} onChange={(e) => setModal(e.target.value)} /></label>
        <label className="text-xs text-muted-foreground">Laba (Rp)<input aria-label="Laba Bian" type="number" min="0" className="bk-control mt-1 w-full" value={laba} onChange={(e) => setLaba(e.target.value)} /></label>
      </div>
      <button className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground" disabled={save.isPending || !Number.isFinite(Number(modal)) || !Number.isFinite(Number(laba)) || Number(modal) < 0 || Number(laba) < 0} onClick={() => save.mutate()}>{save.isPending ? 'Menyimpan…' : 'Simpan'}</button>
      <p className="text-xs text-muted-foreground">Nilai per tanggal mengikuti kolom modal dan laba Bian pada DAILY REPORT.</p>
    </div>
  );
}

function MonthPicker({ month, setMonth }: { month: string; setMonth: (m: string) => void }) {
  const thisMonth = todayLocalISO().slice(0, 7);
  return (
    <div className="flex items-center gap-2">
      <label className="text-sm text-muted-foreground">Bulan</label>
      <input type="month" data-testid="month-input" className="bk-control h-9 w-auto" value={month} max={thisMonth} onChange={(e) => setMonth(e.target.value)} />
    </div>
  );
}

function MonthlyView() {
  const [month, setMonth] = useState(todayLocalISO().slice(0, 7));
  const q = useQuery({ queryKey: ["books-monthly", month], queryFn: () => apiGet<MonthlyReport>(`/books/monthly?month=${month}`) });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <MonthPicker month={month} setMonth={setMonth} />
        <ReportActions csvHref={fileUrl(`/books/monthly/csv?month=${month}`)} testid="monthly" />
      </div>
      {q.isPending ? <LoadingBlock /> : q.isError ? <ErrorBlock error={q.error} onRetry={() => void q.refetch()} /> : q.data && (
        <div className="grid gap-4 lg:grid-cols-2" data-testid="monthly-report">
          <div className="bk-panel p-3">
            <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Ringkasan {q.data.month_label}</p>
            <Row label="1. Pendapatan REPORT" value={formatIDR(q.data.omzet)} strong sub="Penjualan tunai tanpa oli + pembayaran piutang − komisi tunai" />
            <Row label="Modal" value={formatIDR(q.data.store.modal)} />
            <Row label="Laba (tanpa oli / spooring)" value={formatIDR(q.data.store.laba)} />
            <Row label="Spooring" value={formatIDR(q.data.store.spooring)} />
            <Row label="2. Pembayaran ke distributor" value={formatIDR(q.data.distributor_payment)} />
            <Row label="3. Semua pengeluaran tercatat" value={formatIDR(q.data.expenses_total)} sub={`Gaji ${formatIDR(q.data.gaji)} · pajak tercatat ${formatIDR(q.data.pajak_recorded)}`} />
            <Row label="Saldo modal setelah distributor" value={formatIDR(q.data.store.total_modal)} strong />
            <Row label="Laba bersih REPORT" value={formatIDR(q.data.store.nett_laba)} strong />
            <Row label="Estimasi PPh final 0,5%" value={formatIDR(q.data.pph_final)} sub="Informasi pajak, tidak dipotong ulang dari laba" />
            <Row label="4. Sisa aset (terkini)" value={formatIDR(q.data.sisa_aset)} strong tone="total" sub={`Stok ${formatIDR(q.data.stok_value)} (${q.data.stok_basis}) + piutang ${formatIDR(q.data.piutang_outstanding)} − hutang ${formatIDR(q.data.hutang_outstanding)}`} />
          </div>
          <div className="bk-panel p-3" data-testid="funding-breakdown">
            <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Sumber Uang</p>
            <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-2 mb-3">
              <p className="px-1 text-sm font-semibold text-amber-700 dark:text-amber-300">{q.data.funding.modal.label} — untuk distributor</p>
              {q.data.funding.modal.items.map((it) => <Row key={it.name} label={it.name} value={formatIDR(it.amount)} />)}
              <Row label="Subtotal dari modal" value={formatIDR(q.data.funding.modal.total)} strong />
            </div>
            <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-2">
              <p className="px-1 text-sm font-semibold text-emerald-700 dark:text-emerald-300">{q.data.funding.laba.label} — untuk pengeluaran, pajak, gaji</p>
              {q.data.funding.laba.items.map((it) => <Row key={it.name} label={it.name} value={formatIDR(it.amount)} />)}
              <Row label="Subtotal dari laba" value={formatIDR(q.data.funding.laba.total)} strong />
            </div>
          </div>
          <div className="bk-panel p-3 lg:col-span-2" data-testid="owner-summary">
            <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Ringkasan Per Pemilik (bagi hasil)</p>
            <div className="overflow-x-auto">
              <table className="bk-table">
                <thead><tr><th>Pemilik</th><th className="text-right">Pendapatan REPORT</th><th className="text-right">Laba REPORT</th></tr></thead>
                <tbody>
                  {q.data.owner_summary.map((o) => (
                    <tr key={o.owner} data-testid={`owner-row-${o.owner}`}>
                      <td><b>{o.label}</b></td>
                      <td className="text-right font-mono">{formatIDR(o.omzet)}</td>
                      <td className="text-right font-mono">{formatIDR(o.laba)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 px-1 text-[11px] text-muted-foreground">Pemilik mengikuti riwayat transaksi. Pembayaran piutang tanpa pemilik yang dapat dipastikan masuk "Belum ditandai". Retur membalik nilai pada tanggal retur.</p>
          </div>
        </div>
      )}
    </div>
  );
}

function TaxView() {
  const [filters, setFilters] = useState(initialSalesFilters);
  const params = salesFilterQuery(filters);
  const q = useQuery({ queryKey: ["books-tax", params], queryFn: () => apiGet<TaxReport>(`/books/tax?${params}`) });
  return (
    <div className="space-y-4">
      <SalesFilters value={filters} onChange={setFilters} showTax={false} />
      {q.isPending ? <LoadingBlock /> : q.isError ? <ErrorBlock error={q.error} onRetry={() => void q.refetch()} /> : q.data && (
        <div className="bk-panel p-3 max-w-xl" data-testid="tax-report">
          <div className="flex items-center gap-2 mb-2 px-1">
            <Landmark className="size-4 text-primary" />
            <p className="text-sm font-semibold">Estimasi PPh Final UMKM 0,5% — {q.data.month_label}</p>
          </div>
          <Row label={`Dasar pengenaan: ${q.data.basis}`} value={formatIDR(q.data.omzet_base)} strong sub={`Total penjualan sesuai filter: ${formatIDR(q.data.omzet_bruto)}`} />
          {q.data.unassigned_tax_net !== 0 && <p className="bk-notice">Penjualan {formatIDR(q.data.unassigned_tax_net)} belum memiliki atribut TAX pada transaksi; tidak dimasukkan ke dasar pajak.</p>}
          {q.data.tax_eligible_line_count > q.data.tax_summary_row_limit && <p className="bk-notice">Ringkasan mengikuti batas {q.data.tax_summary_row_limit} baris pertama pada REPORT. Dasar seluruh baris: {formatIDR(q.data.full_tax_base)}.</p>}
          <Row label="Tarif PPh Final" value={`${(q.data.rate * 100).toFixed(1)}%`} />
          <div className="my-2 border-t border-border" />
          <Row label="Estimasi PPh Final" value={formatIDR(q.data.pph_final)} tone="total" strong />
          <p className="mt-3 px-1 text-[11px] text-muted-foreground">Estimasi dengan tarif aplikasi 0,5%. Dasar omzet mengikuti Get Data spreadsheet; catat pembayaran pajak melalui Pengeluaran.</p>
        </div>
      )}
    </div>
  );
}

export default function BooksReportPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("harian");
  return (
    <div className="p-4 md:p-6">
      <div className="mb-4">
        <h1 className="font-heading text-2xl font-bold tracking-tight">Laporan Kas &amp; Estimasi Pajak</h1>
        <p className="text-sm text-muted-foreground">Kas harian dan ringkasan bulanan mengikuti spreadsheet. Estimasi PPh memakai tarif aplikasi 0,5%.</p>
      </div>
      <div className="mb-5 flex flex-wrap gap-2">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            data-testid={`books-tab-${key}`}
            onClick={() => setTab(key)}
            className={cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              tab === key ? "bg-primary text-primary-foreground" : "bg-secondary/50 text-muted-foreground hover:text-foreground")}
          >
            <Icon className="size-4" /> {label}
          </button>
        ))}
      </div>
      {tab === "get-data" && <GetDataReportView />}
      {tab === "transaksi" && <MonthlySalesView />}
      {tab === "harian" && <DailyView />}
      {tab === "bulanan" && <MonthlyView />}
      {tab === "pajak" && <TaxView />}
    </div>
  );
}
