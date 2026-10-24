import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Minus, PackagePlus, Plus, Search, Trash2 } from "lucide-react";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { apiGet, apiPost } from "@/lib/api";
import { formatDate, formatDateTime, formatIDR, getApiErrorMessage, todayLocalISO } from "@/lib/format";
import type { Product, StockIn, Supplier } from "@/lib/types";

type Line = { product: Product; qty: number; cost_price: number };

export default function StockInPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(todayLocalISO());
  const [dueDate, setDueDate] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'credit'>('credit');
  const [note, setNote] = useState("");
  const [search, setSearch] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [detail, setDetail] = useState<StockIn | null>(null);
  const [recordSearch, setRecordSearch] = useState("");

  const stockInQuery = useQuery({ queryKey: ["stock-in"], queryFn: () => apiGet<StockIn[]>("/stock-in") });
  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<Supplier[]>("/suppliers") });
  const productsQuery = useQuery({ queryKey: ["products"], queryFn: () => apiGet<Product[]>("/products") });

  const barang = useMemo(() => (productsQuery.data ?? []).filter((p) => p.type === "barang"), [productsQuery.data]);
  const candidates = useMemo(() => {
    const term = search.trim().toLowerCase();
    return barang.filter(
      (p) =>
        !lines.some((l) => l.product.id === p.id) &&
        (!term || p.name.toLowerCase().includes(term) || p.sku.toLowerCase().includes(term))
    );
  }, [barang, lines, search]);

  const total = lines.reduce((sum, l) => sum + l.qty * l.cost_price, 0);
  const formValid = supplierId !== "" && invoiceNumber.trim() !== "" && invoiceDate !== "" && (paymentMethod === 'cash' || dueDate !== "") && lines.length > 0;

  const createMutation = useMutation({
    mutationFn: () =>
      apiPost<StockIn>("/stock-in", {
        supplier_id: supplierId,
        invoice_number: invoiceNumber.trim(),
        invoice_date: invoiceDate,
        payment_method: paymentMethod,
        due_date: paymentMethod === 'credit' ? dueDate : null,
        note: note.trim(),
        items: lines.map((l) => ({ product_id: l.product.id, qty: l.qty, cost_price: l.cost_price })),
      }),
    onSuccess: (rec) => {
      toast.success(`Stok masuk ${rec.reference} tersimpan. ${rec.payment_method === 'cash' ? 'Pembelian tunai lunas.' : 'Hutang dibuat.'}`);
      setDialogOpen(false);
      setSupplierId("");
      setInvoiceNumber("");
      setInvoiceDate(todayLocalISO());
      setDueDate("");
      setPaymentMethod('credit');
      setNote("");
      setLines([]);
      setSearch("");
      void queryClient.invalidateQueries({ queryKey: ["stock-in"] });
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["payables"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const allRecords = stockInQuery.data ?? [];
  const records = allRecords.filter(r => [r.reference, r.invoice_number, r.supplier_name].join(" ").toLowerCase().includes(recordSearch.trim().toLowerCase()));

  return (
    <div className="page-workspace">
      <div className="page-heading">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Stok Masuk</h1>
          <p className="text-sm text-muted-foreground">
            Catat pembelian dari distributor, perbarui stok, dan simpan harga modal.
          </p>
        </div>
        <Button data-testid="stock-in-add-button" onClick={() => setDialogOpen(true)}>
          <PackagePlus className="size-4" /> Catat barang masuk
        </Button>
      </div>

      <div className="page-toolbar">
        <div className="relative min-w-0 w-full sm:max-w-md">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input aria-label="Cari pembelian barang" data-testid="stock-in-record-search" className="pl-10" value={recordSearch} onChange={e => setRecordSearch(e.target.value)} placeholder="Cari referensi, faktur, atau distributor" />
        </div>
        {!stockInQuery.isPending && !stockInQuery.isError && <span className="text-sm text-muted-foreground" data-testid="stock-in-visible-count">{records.length} pembelian ditampilkan</span>}
      </div>

      {stockInQuery.isPending ? (
        <LoadingBlock />
      ) : stockInQuery.isError ? (
        <ErrorBlock error={stockInQuery.error} onRetry={() => void stockInQuery.refetch()} />
      ) : records.length === 0 ? (
        <EmptyBlock
          title={allRecords.length ? "Pembelian tidak ditemukan" : "Belum ada barang masuk"}
          description={allRecords.length ? "Ubah kata pencarian untuk melihat pembelian lainnya." : "Pilih Catat barang masuk untuk menambah stok dari distributor."}
        />
      ) : (
        <div className="data-panel" data-testid="stock-in-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Referensi</TableHead>
                <TableHead>Waktu</TableHead>
                <TableHead>Distributor</TableHead>
                <TableHead>Invoice</TableHead>
                <TableHead className="text-right">Item</TableHead>
                <TableHead>Pembayaran / Jatuh Tempo</TableHead>
                <TableHead className="text-right">Nilai</TableHead>
                <TableHead className="text-right">Aksi</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((r) => (
                <TableRow key={r.id} data-testid={`stock-in-row-${r.reference.toLowerCase()}`}>
                  <TableCell className="font-mono text-xs">{r.reference}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDateTime(r.date)}</TableCell>
                  <TableCell className="min-w-40 max-w-64 whitespace-normal text-sm font-semibold">{r.supplier_name}</TableCell>
                  <TableCell className="font-mono text-xs">{r.invoice_number}</TableCell>
                  <TableCell className="text-right text-sm">{r.items.length}</TableCell>
                  <TableCell className="text-sm">{r.payment_method === 'cash' ? 'Tunai (lunas)' : formatDate(r.due_date)}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{formatIDR(r.total_amount)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="outline"
                      size="xs"
                      data-testid={`stock-in-detail-btn-${r.reference.toLowerCase()}`}
                      onClick={() => setDetail(r)}
                    >
                      Detail
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-3xl" data-testid="stock-in-form-dialog">
          <DialogHeader>
            <DialogTitle>Catat Barang Masuk</DialogTitle>
            <DialogDescription>
              Pembelian tunai dicatat lunas. Pembelian tempo membuat hutang distributor.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <h3 className="col-span-full border-b border-border pb-2 text-sm font-semibold">Faktur pembelian</h3>
            <div className="space-y-2">
              <Label htmlFor="stock-in-supplier">Distributor</Label>
              <Select value={supplierId || "none"} onValueChange={(v) => setSupplierId(v === "none" ? "" : v)}>
                <SelectTrigger id="stock-in-supplier" className="w-full" data-testid="stock-in-supplier-select">
                  <SelectValue>
                    {(v) => {
                      const val = v as string;
                      if (val === "none") return "Pilih distributor";
                      return (suppliersQuery.data ?? []).find((s) => s.id === val)?.name ?? "Pilih distributor";
                    }}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Pilih distributor</SelectItem>
                  {(suppliersQuery.data ?? []).map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="stock-in-invoice">Nomor faktur</Label>
              <Input
                id="stock-in-invoice"
                data-testid="stock-in-invoice-input"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                placeholder="Nomor pada faktur distributor"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="stock-in-invoice-date">Tanggal faktur</Label>
              <Input id="stock-in-invoice-date" data-testid="stock-in-invoice-date-input" type="date" value={invoiceDate} onChange={e => setInvoiceDate(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="stock-in-payment">Pembayaran pembelian</Label>
              <select id="stock-in-payment" className="bk-control" data-testid="stock-in-payment-select" value={paymentMethod} onChange={e => setPaymentMethod(e.target.value as 'cash' | 'credit')}>
                <option value="credit">Tempo</option>
                <option value="cash">Tunai (lunas)</option>
              </select>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="stock-in-due">Jatuh tempo hutang</Label>
              <Input
                id="stock-in-due"
                data-testid="stock-in-due-input"
                type="date"
                min={todayLocalISO()}
                value={dueDate}
                disabled={paymentMethod === 'cash'}
                onChange={(e) => setDueDate(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">Wajib untuk pembelian tempo. Pembelian tunai tidak memiliki jatuh tempo.</p>
            </div>
          </div>
          {suppliersQuery.isError && <ErrorBlock error={suppliersQuery.error} onRetry={() => void suppliersQuery.refetch()} />}

          <div className="mt-2 space-y-3">
            <h3 className="border-b border-border pb-2 text-sm font-semibold">Barang yang diterima</h3>
            <Label htmlFor="stock-in-product-search">Cari dan tambahkan barang</Label>
            <div className="relative">
              <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="stock-in-product-search"
                data-testid="stock-in-product-search"
                className="pl-10"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Cari nama atau SKU barang…"
              />
            </div>
            {productsQuery.isPending ? <LoadingBlock /> : productsQuery.isError ? <ErrorBlock error={productsQuery.error} onRetry={() => void productsQuery.refetch()} /> : search.trim() !== "" ? (
              <div className="max-h-40 overflow-y-auto rounded-lg border border-border">
                {candidates.length === 0 ? (
                  <p className="p-3 text-xs text-muted-foreground">Tidak ada barang cocok.</p>
                ) : (
                  candidates.slice(0, 8).map((p) => (
                    <button
                      key={p.id}
                      data-testid={`stock-in-pick-${p.sku.toLowerCase()}`}
                      className="flex min-h-11 w-full items-center justify-between gap-2 border-b border-border/60 px-3 py-3 text-left text-sm last:border-0 hover:bg-accent/50"
                      onClick={() => {
                        setLines((prev) => [...prev, { product: p, qty: 1, cost_price: p.cost_price }]);
                        setSearch("");
                      }}
                    >
                      <span className="min-w-0 whitespace-normal">
                        <span className="font-mono text-xs text-muted-foreground">{p.sku}</span> {p.name}
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">stok {p.stock}</span>
                    </button>
                  ))
                )}
              </div>
            ) : null}
          </div>

          {lines.length > 0 ? (
            <div className="rounded-lg border border-border" data-testid="stock-in-lines">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Barang</TableHead>
                    <TableHead className="w-32 text-center">Qty</TableHead>
                    <TableHead className="w-40">Modal / unit</TableHead>
                    <TableHead className="text-right">Subtotal</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {lines.map((l, idx) => (
                    <TableRow key={l.product.id} data-testid={`stock-in-line-${l.product.sku.toLowerCase()}`}>
                      <TableCell className="text-sm">
                        <p className="font-medium">{l.product.name}</p>
                        <p className="font-mono text-xs text-muted-foreground">
                          {l.product.sku} · stok {l.product.stock} → {l.product.stock + l.qty}
                        </p>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-center gap-1">
                          <Button
                            aria-label={`Kurangi jumlah ${l.product.name}`}
                            variant="outline"
                            size="icon-xs"
                            data-testid={`stock-in-dec-${l.product.sku.toLowerCase()}`}
                            onClick={() =>
                              setLines((prev) =>
                                prev.map((x, i) => (i === idx ? { ...x, qty: Math.max(1, x.qty - 1) } : x))
                              )
                            }
                          >
                            <Minus />
                          </Button>
                          <Input
                            aria-label={`Jumlah ${l.product.name}`}
                            data-testid={`stock-in-qty-${l.product.sku.toLowerCase()}`}
                            type="number"
                            min={1}
                            value={l.qty}
                            onChange={(e) =>
                              setLines((prev) =>
                                prev.map((x, i) =>
                                  i === idx ? { ...x, qty: Math.max(1, Number(e.target.value || 1)) } : x
                                )
                              )
                            }
                            className="w-16 text-center"
                          />
                          <Button
                            aria-label={`Tambah jumlah ${l.product.name}`}
                            variant="outline"
                            size="icon-xs"
                            data-testid={`stock-in-inc-${l.product.sku.toLowerCase()}`}
                            onClick={() =>
                              setLines((prev) => prev.map((x, i) => (i === idx ? { ...x, qty: x.qty + 1 } : x)))
                            }
                          >
                            <Plus />
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Input
                          aria-label={`Modal per unit ${l.product.name}`}
                          data-testid={`stock-in-cost-${l.product.sku.toLowerCase()}`}
                          type="number"
                          min={0}
                          value={l.cost_price}
                          onChange={(e) =>
                            setLines((prev) =>
                              prev.map((x, i) => (i === idx ? { ...x, cost_price: Number(e.target.value || 0) } : x))
                            )
                          }
                          className="min-w-32"
                        />
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {formatIDR(l.qty * l.cost_price)}
                      </TableCell>
                      <TableCell>
                        <Button
                          aria-label={`Hapus ${l.product.name} dari pembelian`}
                          variant="ghost"
                          size="icon-xs"
                          data-testid={`stock-in-remove-${l.product.sku.toLowerCase()}`}
                          onClick={() => setLines((prev) => prev.filter((_, i) => i !== idx))}
                        >
                          <Trash2 className="text-red-700 dark:text-red-400" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border bg-secondary/40 px-4 py-4">
                <span className="text-sm font-semibold">{paymentMethod === 'cash' ? 'Total Pembelian Tunai' : 'Total Hutang yang Dibuat'}</span>
                <span className="font-mono font-bold text-primary" data-testid="stock-in-total">
                  {formatIDR(total)}
                </span>
              </div>
            </div>
          ) : (
            <EmptyBlock title="Belum ada barang" description="Cari dan pilih barang di kolom pencarian di atas." />
          )}

          <div className="space-y-2">
            <Label htmlFor="stock-in-note">Catatan</Label>
            <Textarea
              id="stock-in-note"
              data-testid="stock-in-note-input"
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Catatan pembelian (opsional)"
            />
          </div>

          <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
            <Button variant="outline" data-testid="stock-in-cancel-button" onClick={() => setDialogOpen(false)}>
              Batal
            </Button>
            <Button
              data-testid="stock-in-submit-button"
              disabled={!formValid || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? "Menyimpan…" : paymentMethod === 'cash' ? 'Simpan pembelian tunai' : 'Simpan dan buat hutang'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" data-testid="stock-in-detail-dialog">
          <DialogHeader>
            <DialogTitle className="font-mono">{detail?.reference}</DialogTitle>
            <DialogDescription>
              {detail ? `${detail.supplier_name} · invoice ${detail.invoice_number}` : ""}
            </DialogDescription>
          </DialogHeader>
          {detail ? (
            <div className="space-y-3">
              <div className="divide-y divide-border rounded-lg border border-border">
                {detail.items.map((it, index) => (
                  <div key={`${it.product_id}-${index}`} className="flex flex-wrap items-start justify-between gap-3 px-3 py-3 text-sm">
                    <div className="min-w-0">
                      <p className="whitespace-normal font-semibold">{it.product_name}</p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {it.sku} · {it.qty} × {formatIDR(it.cost_price)} · stok {it.stock_before} → {it.stock_after}
                      </p>
                    </div>
                    <span className="font-mono text-sm">{formatIDR(it.subtotal)}</span>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap justify-between gap-2 text-sm">
                <span className="text-muted-foreground">Total pembelian</span>
                <span className="font-mono font-bold">{formatIDR(detail.total_amount)}</span>
              </div>
              <div className="flex flex-wrap justify-between gap-2 text-sm">
                <span className="text-muted-foreground">Tanggal faktur</span>
                <span>{formatDate(detail.invoice_date ?? detail.date_key)}</span>
              </div>
              <div className="flex flex-wrap justify-between gap-2 text-sm">
                <span className="text-muted-foreground">Jatuh Tempo</span>
                <span>{formatDate(detail.due_date)}</span>
              </div>
              {detail.note ? (
                <p className="rounded-md bg-secondary/50 p-2 text-xs text-muted-foreground">{detail.note}</p>
              ) : null}
              <Badge variant="outline" className="rounded-md">
                {detail.payment_method === 'cash' ? 'Tunai (lunas)' : 'Hutang otomatis tercatat di halaman Piutang & Hutang'}
              </Badge>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
