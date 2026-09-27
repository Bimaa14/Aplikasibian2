import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Minus, PackagePlus, Plus, Search, Trash2 } from "lucide-react";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  const [dueDate, setDueDate] = useState("");
  const [note, setNote] = useState("");
  const [search, setSearch] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [detail, setDetail] = useState<StockIn | null>(null);

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
  const formValid = supplierId !== "" && invoiceNumber.trim() !== "" && dueDate !== "" && lines.length > 0;

  const createMutation = useMutation({
    mutationFn: () =>
      apiPost<StockIn>("/stock-in", {
        supplier_id: supplierId,
        invoice_number: invoiceNumber.trim(),
        due_date: dueDate,
        note: note.trim(),
        items: lines.map((l) => ({ product_id: l.product.id, qty: l.qty, cost_price: l.cost_price })),
      }),
    onSuccess: (rec) => {
      toast.success(`Stok masuk ${rec.reference} tersimpan — stok naik & hutang dibuat`);
      setDialogOpen(false);
      setSupplierId("");
      setInvoiceNumber("");
      setDueDate("");
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

  const records = stockInQuery.data ?? [];

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Stok Masuk</h1>
          <p className="text-sm text-muted-foreground">
            Catat barang masuk dari distributor: stok naik, modal diperbarui, dan hutang dibuat otomatis.
          </p>
        </div>
        <Button data-testid="stock-in-add-button" onClick={() => setDialogOpen(true)}>
          <PackagePlus className="size-4" /> Catat Barang Masuk
        </Button>
      </div>

      {stockInQuery.isPending ? (
        <LoadingBlock />
      ) : stockInQuery.isError ? (
        <ErrorBlock error={stockInQuery.error} onRetry={() => void stockInQuery.refetch()} />
      ) : records.length === 0 ? (
        <EmptyBlock
          title="Belum ada barang masuk"
          description="Klik 'Catat Barang Masuk' untuk menambah stok dari distributor."
        />
      ) : (
        <div className="rounded-xl border border-border bg-card" data-testid="stock-in-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Referensi</TableHead>
                <TableHead>Waktu</TableHead>
                <TableHead>Distributor</TableHead>
                <TableHead>Invoice</TableHead>
                <TableHead className="text-right">Item</TableHead>
                <TableHead>Jatuh Tempo</TableHead>
                <TableHead className="text-right">Nilai</TableHead>
                <TableHead className="text-right">Aksi</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((r) => (
                <TableRow key={r.id} data-testid={`stock-in-row-${r.reference.toLowerCase()}`}>
                  <TableCell className="font-mono text-xs">{r.reference}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDateTime(r.date)}</TableCell>
                  <TableCell className="max-w-48 truncate text-sm">{r.supplier_name}</TableCell>
                  <TableCell className="font-mono text-xs">{r.invoice_number}</TableCell>
                  <TableCell className="text-right text-sm">{r.items.length}</TableCell>
                  <TableCell className="text-sm">{formatDate(r.due_date)}</TableCell>
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

      {/* Dialog form barang masuk */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl" data-testid="stock-in-form-dialog">
          <DialogHeader>
            <DialogTitle>Catat Barang Masuk</DialogTitle>
            <DialogDescription>
              Pilih distributor, tambahkan beberapa barang beserta harga modal. Stok akan naik, modal produk
              diperbarui, dan hutang distributor dibuat otomatis.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Distributor</Label>
              <Select value={supplierId || "none"} onValueChange={(v) => setSupplierId(v === "none" ? "" : v)}>
                <SelectTrigger data-testid="stock-in-supplier-select">
                  <SelectValue>
                    {(v) => {
                      const val = v as string;
                      if (val === "none") return "— Pilih —";
                      return (suppliersQuery.data ?? []).find((s) => s.id === val)?.name ?? "— Pilih —";
                    }}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— Pilih —</SelectItem>
                  {(suppliersQuery.data ?? []).map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="stock-in-invoice">No. Invoice</Label>
              <Input
                id="stock-in-invoice"
                data-testid="stock-in-invoice-input"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                placeholder="mis. GT/PO/2699"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="stock-in-due">Jatuh Tempo Hutang</Label>
              <Input
                id="stock-in-due"
                data-testid="stock-in-due-input"
                type="date"
                min={todayLocalISO()}
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>
          </div>

          {/* Pilih barang */}
          <div className="mt-2 space-y-2">
            <Label>Tambah Barang</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                data-testid="stock-in-product-search"
                className="pl-9"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Cari nama atau SKU barang…"
              />
            </div>
            {search.trim() !== "" ? (
              <div className="max-h-40 overflow-y-auto rounded-lg border border-border">
                {candidates.length === 0 ? (
                  <p className="p-3 text-xs text-muted-foreground">Tidak ada barang cocok.</p>
                ) : (
                  candidates.slice(0, 8).map((p) => (
                    <button
                      key={p.id}
                      data-testid={`stock-in-pick-${p.sku.toLowerCase()}`}
                      className="flex w-full items-center justify-between gap-2 border-b border-border/60 px-3 py-2 text-left text-sm last:border-0 hover:bg-accent/50"
                      onClick={() => {
                        setLines((prev) => [...prev, { product: p, qty: 1, cost_price: p.cost_price }]);
                        setSearch("");
                      }}
                    >
                      <span className="min-w-0 truncate">
                        <span className="font-mono text-xs text-muted-foreground">{p.sku}</span> {p.name}
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">stok {p.stock}</span>
                    </button>
                  ))
                )}
              </div>
            ) : null}
          </div>

          {/* Baris barang masuk */}
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
                            className="h-7 w-14 text-center"
                          />
                          <Button
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
                          data-testid={`stock-in-cost-${l.product.sku.toLowerCase()}`}
                          type="number"
                          min={0}
                          value={l.cost_price}
                          onChange={(e) =>
                            setLines((prev) =>
                              prev.map((x, i) => (i === idx ? { ...x, cost_price: Number(e.target.value || 0) } : x))
                            )
                          }
                          className="h-7"
                        />
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {formatIDR(l.qty * l.cost_price)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          data-testid={`stock-in-remove-${l.product.sku.toLowerCase()}`}
                          onClick={() => setLines((prev) => prev.filter((_, i) => i !== idx))}
                        >
                          <Trash2 className="text-red-400" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex items-center justify-between border-t border-border px-4 py-3">
                <span className="text-sm font-semibold">Total Hutang yang Dibuat</span>
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
              placeholder="mis. Kiriman ban bulanan"
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" data-testid="stock-in-cancel-button" onClick={() => setDialogOpen(false)}>
              Batal
            </Button>
            <Button
              data-testid="stock-in-submit-button"
              disabled={!formValid || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? "Menyimpan…" : `Simpan & Buat Hutang ${formatIDR(total)}`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog detail */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="sm:max-w-lg" data-testid="stock-in-detail-dialog">
          <DialogHeader>
            <DialogTitle className="font-mono">{detail?.reference}</DialogTitle>
            <DialogDescription>
              {detail ? `${detail.supplier_name} · invoice ${detail.invoice_number}` : ""}
            </DialogDescription>
          </DialogHeader>
          {detail ? (
            <div className="space-y-3">
              <div className="divide-y divide-border rounded-lg border border-border">
                {detail.items.map((it) => (
                  <div key={it.product_id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{it.product_name}</p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {it.sku} · {it.qty} × {formatIDR(it.cost_price)} · stok {it.stock_before} → {it.stock_after}
                      </p>
                    </div>
                    <span className="font-mono text-sm">{formatIDR(it.subtotal)}</span>
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Total / Hutang dibuat</span>
                <span className="font-mono font-bold">{formatIDR(detail.total_amount)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Jatuh Tempo</span>
                <span>{formatDate(detail.due_date)}</span>
              </div>
              {detail.note ? (
                <p className="rounded-md bg-secondary/50 p-2 text-xs text-muted-foreground">{detail.note}</p>
              ) : null}
              <Badge variant="outline" className="rounded-md">
                Hutang otomatis tercatat di halaman Piutang &amp; Hutang
              </Badge>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
