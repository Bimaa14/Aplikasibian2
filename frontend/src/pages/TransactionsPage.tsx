import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Eye, Printer, Undo2 } from "lucide-react";
import ThermalReceiptModal from "@/components/pos/ThermalReceiptModal";
import { DebtStatusBadge, PaymentMethodBadge, TxStatusBadge } from "@/components/StatusBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, apiPost } from "@/lib/api";
import { formatDate, formatDateTime, formatIDR, getApiErrorMessage } from "@/lib/format";
import type { Transaction, TxStatus } from "@/lib/types";

export default function TransactionsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<TxStatus | "semua">("semua");
  const [detailTx, setDetailTx] = useState<Transaction | null>(null);
  const [printTx, setPrintTx] = useState<Transaction | null>(null);
  const [returnTx, setReturnTx] = useState<Transaction | null>(null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [refundConfirmed, setRefundConfirmed] = useState(false);

  const txQuery = useQuery({ queryKey: ["transactions"], queryFn: () => apiGet<Transaction[]>("/transactions") });

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (txQuery.data ?? []).filter((t) => {
      if (statusFilter !== "semua" && t.status !== statusFilter) return false;
      if (!term) return true;
      return (
        t.invoice_number.toLowerCase().includes(term) ||
        (t.customer_name ?? "").toLowerCase().includes(term) ||
        (t.vehicle_plate ?? "").toLowerCase().includes(term)
      );
    });
  }, [txQuery.data, search, statusFilter]);

  const returnMutation = useMutation({
    mutationFn: (tx: Transaction) => apiPost<Transaction>(`/transactions/${tx.id}/return`, { refund_confirmed: refundConfirmed, reason: 'Retur penuh melalui kasir' }),
    onSuccess: (tx) => {
      toast.success(`Transaksi ${tx.invoice_number} ditandai retur — stok barang dikembalikan`);
      setReturnTx(null);
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["receivables"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Riwayat Transaksi</h1>
          <p className="text-sm text-muted-foreground">Cetak ulang struk thermal 80mm atau tandai transaksi retur.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            data-testid="transactions-search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari invoice / pelanggan / nopol…"
            className="w-56"
          />
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as TxStatus | "semua")}>
            <SelectTrigger data-testid="transactions-status-filter" className="w-40">
              <SelectValue>{(v) => (v === "returned" ? "Retur" : v === "completed" ? "Selesai" : "Semua Status")}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="semua">Semua Status</SelectItem>
              <SelectItem value="completed">Selesai</SelectItem>
              <SelectItem value="returned">Retur</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {txQuery.isPending ? (
        <LoadingBlock />
      ) : txQuery.isError ? (
        <ErrorBlock error={txQuery.error} onRetry={() => void txQuery.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyBlock title="Belum ada transaksi" description="Transaksi dari halaman Kasir POS akan muncul di sini." />
      ) : (
        <div className="rounded-xl border border-border bg-card" data-testid="transactions-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Invoice</TableHead>
                <TableHead>Waktu</TableHead>
                <TableHead>Pelanggan</TableHead>
                <TableHead>Nopol</TableHead>
                <TableHead>Metode</TableHead>
                <TableHead>Jatuh Tempo</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Aksi</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((t) => (
                <TableRow key={t.id} data-testid={`transaction-row-${t.invoice_number.toLowerCase()}`}>
                  <TableCell className="font-mono text-xs">{t.invoice_number}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDateTime(t.date)}</TableCell>
                  <TableCell className="max-w-40 truncate text-sm">{t.customer_name ?? "Umum"}</TableCell>
                  <TableCell className="font-mono text-xs tracking-wider">{t.vehicle_plate ?? "-"}</TableCell>
                  <TableCell><PaymentMethodBadge method={t.payment_method} /></TableCell>
                  <TableCell className="text-xs">
                    {t.payment_method === "credit" && t.due_date ? (
                      <span className="flex items-center gap-2">
                        {formatDate(t.due_date)}
                        {t.status === "completed" ? <DebtStatusBadge status="unpaid" dueDate={t.due_date} /> : null}
                      </span>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">{formatIDR(t.total_amount)}</TableCell>
                  <TableCell><TxStatusBadge status={t.status} /></TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon-xs" data-testid={`detail-tx-btn-${t.invoice_number.toLowerCase()}`} title="Detail" onClick={() => setDetailTx(t)}>
                        <Eye />
                      </Button>
                      <Button variant="ghost" size="icon-xs" data-testid={`print-tx-btn-${t.invoice_number.toLowerCase()}`} title="Cetak Ulang Struk" onClick={() => { setPrintTx(t); setReceiptOpen(true); }}>
                        <Printer />
                      </Button>
                      {t.status === "completed" ? (
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          data-testid={`return-tx-btn-${t.invoice_number.toLowerCase()}`}
                          title="Retur"
                          onClick={() => { setRefundConfirmed(false); setReturnTx(t); }}
                        >
                          <Undo2 className="text-amber-400" />
                        </Button>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog detail */}
      <Dialog open={!!detailTx} onOpenChange={(o) => !o && setDetailTx(null)}>
        <DialogContent className="sm:max-w-lg" data-testid="transaction-detail-dialog">
          <DialogHeader>
            <DialogTitle className="font-mono">{detailTx?.invoice_number}</DialogTitle>
            <DialogDescription>
              {detailTx ? `${formatDateTime(detailTx.date)} · ${detailTx.customer_name ?? "Umum"}` : ""}
            </DialogDescription>
          </DialogHeader>
          {detailTx ? (
            <div className="space-y-3">
              <div className="divide-y divide-border rounded-lg border border-border">
                {detailTx.details.map((d) => (
                  <div key={d.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{d.product_name}</p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {d.qty} × {formatIDR(d.price)} · {d.product_type === "jasa" ? "Jasa" : "Barang"}
                      </p>
                    </div>
                    <span className="font-mono text-sm">{formatIDR(d.subtotal)}</span>
                  </div>
                ))}
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total</span>
                  <span className="font-mono font-bold" data-testid="detail-total">{formatIDR(detailTx.total_amount)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Komisi Montir (jasa)</span>
                  <span className="font-mono" data-testid="detail-service-fee">{formatIDR(detailTx.service_fee)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Metode Bayar</span>
                  <PaymentMethodBadge method={detailTx.payment_method} />
                </div>
                {detailTx.due_date ? (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Jatuh Tempo</span>
                    <span>{formatDate(detailTx.due_date)}</span>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Dialog konfirmasi retur */}
      <Dialog open={!!returnTx} onOpenChange={(o) => !o && setReturnTx(null)}>
        <DialogContent className="sm:max-w-md" data-testid="return-dialog">
          <DialogHeader>
            <DialogTitle>Retur Transaksi {returnTx?.invoice_number}?</DialogTitle>
            <DialogDescription>
              Stok dikembalikan, piutang menjadi Void (bukan Lunas), dan pengembalian kas dicatat pada tanggal retur. Laporan margin dan laporan Excel tetap terpisah.
              Tindakan ini tidak dapat dibatalkan.
            </DialogDescription>
          </DialogHeader>
          <label className="flex items-start gap-3 text-sm" data-testid="refund-confirmation-label"><input type="checkbox" className="mt-1" data-testid="refund-confirmation-checkbox" checked={refundConfirmed} onChange={e => setRefundConfirmed(e.target.checked)} />Saya sudah mengembalikan seluruh uang yang pernah diterima untuk transaksi ini (jika ada pembayaran).</label>
          <div className="flex justify-end gap-2">
            <Button variant="outline" data-testid="cancel-return-btn" onClick={() => setReturnTx(null)}>
              Batal
            </Button>
            <Button
              variant="destructive"
              data-testid="confirm-return-btn"
              disabled={returnMutation.isPending || !refundConfirmed}
              onClick={() => returnTx && returnMutation.mutate(returnTx)}
            >
              {returnMutation.isPending ? "Memproses…" : "Ya, Retur"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ThermalReceiptModal transaction={printTx} open={receiptOpen} onOpenChange={setReceiptOpen} />
    </div>
  );
}
