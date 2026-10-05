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
import { apiGet, fileUrl } from "@/lib/api";
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
        "ledger-line flex flex-col items-start justify-between gap-2 border-b border-border/60 px-4 py-3 last:border-0 sm:flex-row sm:items-center sm:gap-4",
        tone === "total" && "bg-secondary/40",
        indent && "pl-8",
        testid === "report-net-profit" && "ledger-total"
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
    const url = fileUrl(`/reports/monthly/${kind}?month=${month}`);
    const a = document.createElement("a");
    a.href = url;
    a.download = `laporan-bengkel-${month}.${kind}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast.success(`Laporan ${kind.toUpperCase()} ${monthLabel(month)} sedang diunduh`);
  }

  return (
    <div className="page-workspace space-y-5">
      <div className="page-heading">
        <div className="min-w-0">
          <h1 data-testid="margin-report-title" className="font-heading text-2xl font-bold tracking-tight">Laporan bulanan</h1>
          <p className="text-sm text-muted-foreground">
            Pendapatan, modal, laba, dan spooring mengikuti rumus REPORT. Laba tempo diakui saat pembayaran pertama.
          </p>
        </div>
        <div className="report-actions flex flex-wrap items-center gap-2">
          <Select value={month} onValueChange={setMonth}>
            <SelectTrigger data-testid="report-month-select" aria-label="Bulan laporan" className="w-full sm:w-48">
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
          <Button variant="outline" data-testid="report-download-csv" disabled={!r || reportQuery.isFetching || reportQuery.isError} onClick={() => download("csv")}>
            <FileSpreadsheet className="size-4" /> Unduh CSV
          </Button>
          <Button data-testid="report-download-pdf" disabled={!r || reportQuery.isFetching || reportQuery.isError} onClick={() => download("pdf")}>
            <FileText className="size-4" /> Unduh PDF
          </Button>
        </div>
      </div>

      {reportQuery.isPending ? (
        <LoadingBlock />
      ) : reportQuery.isError ? (
        <ErrorBlock error={reportQuery.error} onRetry={() => void reportQuery.refetch()} />
      ) : r ? (
        <div className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-12">
          {/* Laba-rugi */}
          <div className="min-w-0 space-y-5 xl:col-span-7">
            <Card className="ledger-statement p-0">
              <CardHeader className="border-b border-border bg-secondary/30 px-4 py-3">
                <CardTitle className="font-heading text-base">
                  Laba rugi · {r.month_label}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Row label="Pendapatan selain spooring" value={formatIDR(r.barang_revenue)} />
                <Row label="Laba Spooring" value={formatIDR(r.jasa_revenue)} />
                <Row label="Total Pendapatan" value={formatIDR(r.revenue_total)} tone="total" testid="report-revenue" />
                <Row label="Modal REPORT" value={formatIDR(r.cost_of_goods)} />
                <Row
                  label="Laba REPORT (tanpa oli/spooring)"
                  value={formatIDR(r.gross_profit_barang)}
                  tone="total"
                  testid="report-gross-profit"
                />
                <Row label="Komisi montir (sudah dihitung)" value={formatIDR(r.service_fee_total)} />
                <Row label="Pembayaran distributor" value={formatIDR(r.supplier_payments)} />
                <Row label="Saldo modal setelah distributor" value={formatIDR(r.capital_balance)} />
                <Row label="Spooring bersih" value={formatIDR(r.spooring_net)} />
                <Row label="Penjualan oli tunai (terpisah)" value={formatIDR(r.oil_revenue)} />
                <Row label="Total Pengeluaran Operasional" value={`-${formatIDR(r.expenses_total)}`} tone="negative" />
                <Row
                  label="Laba bersih REPORT"
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
          <div className="min-w-0 space-y-5 xl:col-span-5">
            <Card className="overflow-hidden p-0">
              <CardHeader className="border-b border-border bg-secondary/30 px-4 py-3">
                <CardTitle className="font-heading text-base">Ringkasan Aktivitas</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Row label="Nota penjualan" value={String(r.transaction_count)} testid="report-tx-count" />
                <Row label="Transaksi Retur" value={`${r.returned_count} · ${formatIDR(r.returned_amount)}`} />
                <Row label="Piutang Baru (tempo)" value={formatIDR(r.new_receivables)} />
                <Row label="Pembayaran piutang bersih" value={formatIDR(r.receivables_paid)} testid="margin-paid-receivables" />
                <Row label="Nilai Barang Masuk" value={formatIDR(r.stock_in_total)} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-heading text-base">Produk dan jasa terlaris</CardTitle>
              </CardHeader>
              <CardContent>
                {r.top_products.length === 0 ? (
                  <EmptyBlock
                    title="Belum ada penjualan"
                    description={`Tidak ada transaksi pada ${r.month_label}.`}
                    className="border-0 bg-transparent p-2"
                  />
                ) : (
                  <Table data-testid="report-top-products" className="report-product-table">
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
                          <TableCell className="whitespace-normal break-words text-sm">
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
