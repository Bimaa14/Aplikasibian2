import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, CalendarClock, Package, ReceiptText } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "@/lib/recharts";
import { DebtStatusBadge, TxStatusBadge } from "@/components/StatusBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { formatDate, formatDateTime, formatIDR, formatIDRCompact } from "@/lib/format";
import type { DashboardStats } from "@/lib/types";
import { cn } from "@/lib/utils";

function KpiCard({
  testid,
  label,
  value,
  sub,
  tone = "plain",
  onClick,
}: {
  testid: string;
  label: string;
  value: string;
  sub: ReactNode;
  tone?: "primary" | "success" | "danger" | "plain";
  onClick?: () => void;
}) {
  return (
    <Card
      size="sm"
      data-testid={testid}
      className={cn("bg-card", onClick && "cursor-pointer transition-shadow hover:shadow-md hover:ring-1 hover:ring-primary/30")}
      onClick={onClick}
    >
      <CardContent className="space-y-1.5">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
        <p
          className={cn(
            "font-heading text-xl font-bold tracking-tight tabular-nums",
            tone === "primary" && "text-primary",
            tone === "success" && "text-emerald-700 dark:text-emerald-400",
            tone === "danger" && "text-red-700 dark:text-red-400"
          )}
        >
          {value}
        </p>
        <div className="text-xs text-muted-foreground">{sub}</div>
      </CardContent>
    </Card>
  );
}

const AGING_BUCKETS = [
  ["upcoming", "Belum JT", "border-border bg-secondary/40"],
  ["0-30", "0–30 hari", "border-amber-500/25 bg-amber-500/5"],
  ["31-60", "31–60 hari", "border-orange-500/30 bg-orange-500/10"],
  ["61-90", "61–90 hari", "border-red-500/25 bg-red-500/5"],
  ["90+", ">90 hari", "border-red-500/40 bg-red-500/10"],
] as const;

export default function DashboardPage() {
  const navigate = useNavigate();
  const statsQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiGet<DashboardStats>("/dashboard"),
  });
  const stats = statsQuery.data;

  return (
    <div className="p-4 md:p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Dashboard Keuangan</h1>
          <p className="text-sm text-muted-foreground">Ringkasan pendapatan, laba, dan arus tagihan bengkel.</p>
        </div>
        {stats ? (
          <Badge variant="outline" className="rounded-md" data-testid="dashboard-today-badge">
            Hari ini · {formatDate(stats.today)}
          </Badge>
        ) : null}
      </div>

      {statsQuery.isPending ? (
        <LoadingBlock className="h-64" />
      ) : statsQuery.isError ? (
        <ErrorBlock error={statsQuery.error} onRetry={() => void statsQuery.refetch()} />
      ) : stats ? (
        <div className="space-y-5">
          {/* KPI row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <KpiCard
              testid="kpi-revenue"
              label="Total Pendapatan"
              value={formatIDR(stats.total_revenue)}
              tone="primary"
              onClick={() => navigate("/transaksi")}
              sub={
                <span className="flex items-center gap-1">
                  <ArrowUpRight className="size-3 text-emerald-700 dark:text-emerald-400" />
                  Hari ini {formatIDR(stats.today_revenue)} · {stats.transaction_count} transaksi
                </span>
              }
            />
            <KpiCard
              testid="kpi-gross-profit"
              label="Laba Kotor (Barang)"
              value={formatIDR(stats.gross_profit)}
              tone="success"
              onClick={() => navigate("/laporan")}
              sub={
                <span className="flex items-center gap-1">
                  <ArrowUpRight className="size-3 text-emerald-700 dark:text-emerald-400" />
                  Jasa {formatIDR(stats.jasa_amount)} · komisi montir {formatIDR(stats.service_fee_total)}
                </span>
              }
            />
            <KpiCard
              testid="kpi-net-profit"
              label="Laba Bersih"
              value={formatIDR(stats.net_profit)}
              tone={stats.net_profit >= 0 ? "success" : "danger"}
              onClick={() => navigate("/laporan-kas")}
              sub={
                <span className="flex items-center gap-1">
                  <ArrowDownRight className="size-3 text-red-700 dark:text-red-400" />
                  Setelah komisi montir + pengeluaran {formatIDR(stats.expenses_total)}
                </span>
              }
            />
            <KpiCard
              testid="kpi-receivables"
              label="Piutang Belum Lunas"
              value={formatIDR(stats.receivables_outstanding)}
              tone={stats.receivables_overdue > 0 ? "danger" : "plain"}
              onClick={() => navigate("/piutang-hutang")}
              sub={
                stats.receivables_overdue > 0 ? (
                  <span className="font-semibold text-red-700 dark:text-red-400">{stats.receivables_overdue} lewat jatuh tempo</span>
                ) : (
                  "Semua masih dalam tempo"
                )
              }
            />
            <KpiCard
              testid="kpi-payables"
              label="Hutang Distributor"
              value={formatIDR(stats.payables_outstanding)}
              tone={stats.payables_overdue > 0 ? "danger" : "plain"}
              onClick={() => navigate("/piutang-hutang")}
              sub={
                stats.payables_overdue > 0 ? (
                  <span className="font-semibold text-red-700 dark:text-red-400">{stats.payables_overdue} lewat jatuh tempo</span>
                ) : (
                  "Semua masih dalam tempo"
                )
              }
            />
          </div>

          {/* Ringkasan umur tunggakan (aging) */}
          <Card data-testid="aging-summary-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 font-heading text-base">
                <CalendarClock className="size-4 text-primary" />
                Umur Tunggakan (Aging)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {([
                ["Piutang pelanggan", stats.receivables_aging, "receivables"],
                ["Hutang distributor", stats.payables_aging, "payables"],
              ] as const).map(([title, data, key]) => (
                <div key={key} data-testid={`aging-${key}`}>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                    {AGING_BUCKETS.map(([bk, label, tone]) => (
                      <div key={bk} data-testid={`aging-${key}-${bk}`} className={cn("rounded-lg border p-2.5", tone)}>
                        <p className="text-[11px] text-muted-foreground">{label}</p>
                        <p className="mt-1 font-mono text-sm font-semibold tabular-nums">{formatIDR(data?.[bk] ?? 0)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
            {/* Grafik 7 hari */}
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle className="font-heading text-base">Pendapatan &amp; Laba 7 Hari Terakhir</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64" data-testid="revenue-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={stats.revenue_by_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="grad-revenue" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.35} />
                          <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.02} />
                        </linearGradient>
                        <linearGradient id="grad-profit" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--chart-2)" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="var(--chart-2)" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="label" stroke="var(--muted-foreground)" fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis
                        stroke="var(--muted-foreground)"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        width={70}
                        tickFormatter={(value: number) => formatIDRCompact(value)}
                      />
                      <Tooltip
                        formatter={(value: number, name: string) => [formatIDR(value), name]}
                        labelFormatter={(label: string) => `Hari: ${label}`}
                        contentStyle={{
                          backgroundColor: "var(--popover)",
                          border: "1px solid var(--border)",
                          borderRadius: "8px",
                          color: "var(--popover-foreground)",
                        }}
                      />
                      <Area type="monotone" dataKey="revenue" name="Pendapatan" stroke="var(--chart-1)" fill="url(#grad-revenue)" strokeWidth={2} />
                      <Area type="monotone" dataKey="profit" name="Laba" stroke="var(--chart-2)" fill="url(#grad-profit)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Peringatan jatuh tempo */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-heading text-base">
                  <AlertTriangle className="size-4 text-red-700 dark:text-red-400" />
                  Peringatan Jatuh Tempo
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {stats.overdue_receivables.length === 0 && stats.overdue_payables.length === 0 ? (
                  <EmptyBlock
                    title="Aman!"
                    description="Tidak ada tagihan yang lewat jatuh tempo."
                    className="border-0 bg-transparent p-4"
                  />
                ) : (
                  <>
                    {stats.overdue_receivables.map((r) => (
                      <div
                        key={r.id}
                        className="rounded-lg border border-red-500/25 bg-red-500/5 p-3 text-sm"
                        data-testid="overdue-receivable-row"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate font-semibold">{r.customer_name}</span>
                          <span className="font-mono text-red-700 dark:text-red-400">{formatIDR(r.amount)}</span>
                        </div>
                        <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                          <span className="font-mono">{r.invoice_number}</span>
                          <DebtStatusBadge status={r.status} dueDate={r.due_date} />
                        </div>
                      </div>
                    ))}
                    {stats.overdue_payables.map((p) => (
                      <div
                        key={p.id}
                        className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-3 text-sm"
                        data-testid="overdue-payable-row"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate font-semibold">{p.supplier_name}</span>
                          <span className="font-mono text-amber-700 dark:text-amber-300">{formatIDR(p.amount)}</span>
                        </div>
                        <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                          <span className="font-mono">{p.invoice_number}</span>
                          <DebtStatusBadge status={p.status} dueDate={p.due_date} />
                        </div>
                      </div>
                    ))}
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {/* Stok menipis */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-heading text-base">
                  <Package className="size-4 text-amber-700 dark:text-amber-400" />
                  Stok Menipis (≤ 4)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {stats.low_stock.length === 0 ? (
                  <EmptyBlock title="Stok aman" description="Tidak ada barang dengan stok ≤ 4." className="border-0 bg-transparent p-4" />
                ) : (
                  <ul className="space-y-2" data-testid="low-stock-list">
                    {stats.low_stock.map((p) => (
                      <li key={p.id} className="flex items-center justify-between rounded-lg bg-secondary/50 px-3 py-2 text-sm">
                        <span className="truncate">
                          {p.name} <span className="text-muted-foreground">· {p.sku}</span>
                        </span>
                        <Badge variant={p.stock <= 2 ? "destructive" : "secondary"} className="rounded-md">
                          Sisa {p.stock}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            {/* Transaksi terakhir */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 font-heading text-base">
                  <ReceiptText className="size-4 text-primary" />
                  Transaksi Terakhir
                </CardTitle>
              </CardHeader>
              <CardContent>
                {stats.recent_transactions.length === 0 ? (
                  <EmptyBlock title="Belum ada transaksi" description="Kunjungi halaman Kasir POS untuk mulai menjual." className="border-0 bg-transparent p-4" />
                ) : (
                  <ul className="space-y-2" data-testid="recent-transactions-list">
                    {stats.recent_transactions.map((t) => (
                      <li key={t.id} className="flex items-center justify-between gap-2 rounded-lg bg-secondary/50 px-3 py-2 text-sm">
                        <div className="min-w-0">
                          <p className="truncate font-mono text-xs text-muted-foreground">{t.invoice_number}</p>
                          <p className="truncate font-semibold">{t.customer_name ?? "Umum"}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className="font-mono text-sm">{formatIDR(t.total_amount)}</span>
                          <TxStatusBadge status={t.status} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}
