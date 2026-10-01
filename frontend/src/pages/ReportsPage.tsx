import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileSpreadsheet, FileText } from "lucide-react";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet } from "@/lib/api";
import { formatIDR, todayLocalISO } from "@/lib/format";
import type { MonthlyReport } from "@/lib/types";
import { cn } from "@/lib/utils";

const BULAN_ID = [
  "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember",
];

function monthLabel(month: string): string {
  const [y, m] = month.split("-");
  const idx = Number(m) - 1;
  return idx >= 0 && idx < 12 ? `${BULAN_ID[idx]} ${y}` : month;
}

function Row({
  label,
  value,
  tone = "plain",
  testid,
  indent,
}: {
  label: string;
  value: string;
  tone?: "plain" | "total" | "positive" | "negative";
  testid?: string;
  indent?: boolean;
}) {
  return (
    <div
      data-testid={testid}
      className={cn(
        "flex items-center justify-between gap-3 border-b border-border/60 px-4 py-2.5 last:border-0",
        tone === "total" && "bg-secondary/40",
        indent && "pl-8"
      )}
    >
      <span className={cn("text-sm", tone === "total" ? "font-semibold" : "text-muted-foreground")}>{label}</span>
      <span
        className={cn(
          "font-mono text-sm tabular-nums",
          tone === "total" && "text-base font-bold",
          tone === "positive" && "font-bold text-emerald-700 dark:text-emerald-400",
          tone === "negative" && "text-red-700 dark:text-red-400"
        )}
      >
        {value}
      </span>
    </div>
  );
}

export default function ReportsPage() {
  const [month, setMonth] = useState(todayLocalISO().slice(0, 7));

  const reportQuery = useQuery({
    queryKey: ["monthly-report", month],
    queryFn: () => apiGet<MonthlyReport>(`/reports/monthly?month=${month}`),
  });
  const r = reportQuery.data;

  function download(kind: "csv" | "pdf") {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/reports/monthly/${kind}?month=${month}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = `laporan-bengkel-${month}.${kind}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast.success(`Laporan ${kind.toUpperCase()} ${monthLabel(month)} sedang diunduh`);
  }

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 data-testid="margin-report-title" className="font-heading text-2xl font-bold tracking-tight">Laba Margin POS</h1>
          <p className="text-sm text-muted-foreground">
            Margin penjualan − HPP − komisi − pengeluaran. Definisi Excel tersedia terpisah di menu Laporan Excel.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={month} onValueChange={setMonth}>
            <SelectTrigger data-testid="report-month-select" className="w-48">
              <SelectValue>{(v) => monthLabel(v as string)}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {(r?.available_months ?? [month]).map((m) => (
                <SelectItem key={m} value={m}>
                  {monthLabel(m)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" data-testid="report-download-csv" onClick={() => download("csv")}>
            <FileSpreadsheet className="size-4" /> Unduh CSV
          </Button>
          <Button data-testid="report-download-pdf" onClick={() => download("pdf")}>
            <FileText className="size-4" /> Unduh PDF
          </Button>
        </div>
      </div>

      {reportQuery.isPending ? (
        <LoadingBlock />
      ) : reportQuery.isError ? (
        <ErrorBlock error={reportQuery.error} onRetry={() => void reportQuery.refetch()} />
      ) : r ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          {/* Laba-rugi */}
          <div className="space-y-5 xl:col-span-7">
            <Card className="overflow-hidden p-0">
              <CardHeader className="border-b border-border bg-secondary/30 px-4 py-3">
                <CardTitle className="font-heading text-base">
                  Laba-Rugi — {r.month_label}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Row label="Pendapatan Barang (ban, oli, sparepart)" value={formatIDR(r.barang_revenue)} />
                <Row label="Pendapatan Jasa Servis" value={formatIDR(r.jasa_revenue)} />
                <Row label="Total Pendapatan" value={formatIDR(r.revenue_total)} tone="total" testid="report-revenue" />
                <Row label="Modal Barang Terjual (HPP)" value={`-${formatIDR(r.cost_of_goods)}`} tone="negative" />
                <Row
                  label="Laba Kotor (Barang)"
                  value={formatIDR(r.gross_profit_barang)}
                  tone="total"
                  testid="report-gross-profit"
                />
                <Row label="Service Fee Mekanik" value={`-${formatIDR(r.service_fee_total)}`} tone="negative" />
                <Row label="Total Pengeluaran Operasional" value={`-${formatIDR(r.expenses_total)}`} tone="negative" />
                <Row
                  label="LABA BERSIH"
                  value={formatIDR(r.net_profit)}
                  tone={r.net_profit >= 0 ? "positive" : "negative"}
                  testid="report-net-profit"
                />
              </CardContent>
            </Card>

            <Card className="overflow-hidden p-0">
              <CardHeader className="border-b border-border bg-secondary/30 px-4 py-3">
                <CardTitle className="font-heading text-base">Pengeluaran per Kategori</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {r.expenses_by_category.length === 0 ? (
                  <p className="p-4 text-sm text-muted-foreground">Tidak ada pengeluaran bulan ini.</p>
                ) : (
                  <div data-testid="report-expense-categories">
                    {r.expenses_by_category.map((e) => (
                      <Row key={e.category} label={e.category} value={formatIDR(e.amount)} />
                    ))}
                    <Row label="Total" value={formatIDR(r.expenses_total)} tone="total" />
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Ringkasan + terlaris */}
          <div className="space-y-5 xl:col-span-5">
            <Card className="overflow-hidden p-0">
              <CardHeader className="border-b border-border bg-secondary/30 px-4 py-3">
                <CardTitle className="font-heading text-base">Ringkasan Aktivitas</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Row label="Transaksi Selesai" value={String(r.transaction_count)} testid="report-tx-count" />
                <Row label="Transaksi Retur" value={`${r.returned_count} · ${formatIDR(r.returned_amount)}`} />
                <Row label="Piutang Baru (tempo)" value={formatIDR(r.new_receivables)} />
                <Row label="Pembayaran piutang (non-Void)" value={formatIDR(r.receivables_paid)} testid="margin-paid-receivables" />
                <Row label="Nilai Barang Masuk" value={formatIDR(r.stock_in_total)} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-heading text-base">Produk &amp; Jasa Terlaris</CardTitle>
              </CardHeader>
              <CardContent>
                {r.top_products.length === 0 ? (
                  <EmptyBlock
                    title="Belum ada penjualan"
                    description={`Tidak ada transaksi pada ${r.month_label}.`}
                    className="border-0 bg-transparent p-2"
                  />
                ) : (
                  <Table data-testid="report-top-products">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Produk / Jasa</TableHead>
                        <TableHead className="text-right">Qty</TableHead>
                        <TableHead className="text-right">Pendapatan</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {r.top_products.map((p) => (
                        <TableRow key={`${p.sku}-${p.name}`}>
                          <TableCell className="max-w-48 truncate text-sm">
                            {p.name}
                            {p.sku ? (
                              <Badge variant="outline" className="ml-2 rounded-sm font-mono text-[10px]">
                                {p.sku}
                              </Badge>
                            ) : null}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">{p.qty}</TableCell>
                          <TableCell className="text-right font-mono text-sm">{formatIDR(p.revenue)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}
