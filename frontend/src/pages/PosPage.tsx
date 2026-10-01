import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { toast } from "sonner";
import { Minus, Plus, Search, Trash2 } from "lucide-react";
import SalesNoteModal from "@/components/pos/SalesNoteModal";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiGet, apiPost } from "@/lib/api";
import { formatIDR, getApiErrorMessage, todayLocalISO } from "@/lib/format";
import type { Customer, PaymentMethod, Product, Transaction } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PAYMENT_OPTIONS } from "@/lib/payments";
import { mechanicFeeTotal } from "@/lib/pos-pricing";

type CartLine = { product: Product; qty: number };
type TabKey = "semua" | "barang" | "jasa";
type CheckoutBody = {
  request_id: string;
  items: { product_id: string; qty: number; credit_surcharge: number; discount_amount: number }[];
  discount_total: number;
  payment_method: PaymentMethod;
  cash_received: number | null;
  customer_id: string | null;
  due_date: string | null;
  vehicle_plate: string | null;
};

const TABS: { key: TabKey; label: string }[] = [
  { key: "semua", label: "Semua" },
  { key: "barang", label: "Ban & Sparepart" },
  { key: "jasa", label: "Jasa Servis" },
];

export default function PosPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<TabKey>("semua");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [cashInput, setCashInput] = useState<string | null>(null);
  const [discountInput, setDiscountInput] = useState('0');
  const [itemDiscounts, setItemDiscounts] = useState<Record<string, string>>({});
  const [surcharges, setSurcharges] = useState<Record<string, string>>({});
  const [customerId, setCustomerId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [receipt, setReceipt] = useState<Transaction | null>(null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const checkoutRequest = useRef<{ payload: string; id: string } | null>(null);

  const productsQuery = useQuery({ queryKey: ["products"], queryFn: () => apiGet<Product[]>("/products") });
  const customersQuery = useQuery({ queryKey: ["customers"], queryFn: () => apiGet<Customer[]>("/customers") });

  const products = productsQuery.data ?? [];
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return products.filter((p) => {
      if (tab !== "semua" && p.type !== tab) return false;
      if (!term) return true;
      return (
        p.name.toLowerCase().includes(term) ||
        p.sku.toLowerCase().includes(term) ||
        p.brand.toLowerCase().includes(term)
      );
    });
  }, [products, search, tab]);

  const unitPrice = (product: Product) => product.selling_price + (paymentMethod === 'credit' ? Number(surcharges[product.id] || 0) : 0);
  const grossAmount = cart.reduce((sum, line) => sum + Math.round(unitPrice(line.product) * 100) * line.qty, 0) / 100;
  const discountAmount = Number(discountInput || 0);
  const itemDiscountTotal = cart.reduce((sum, l) => sum + Math.round(Number(itemDiscounts[l.product.id] || 0) * 100), 0) / 100;
  const totalAmount = Math.max(0, Math.round((grossAmount - itemDiscountTotal - discountAmount) * 100) / 100);
  const pricingInvalid = cart.some(l => {
    const discount = Number(itemDiscounts[l.product.id] || 0);
    return !Number.isFinite(discount) || discount < 0 || discount > unitPrice(l.product) * l.qty || discount > 1e12;
  }) || !Number.isFinite(discountAmount) || discountAmount < 0 || discountAmount > grossAmount - itemDiscountTotal || discountAmount > 1e12 ||
    (paymentMethod === 'credit' && (totalAmount <= 0 || cart.some(l => !Number.isFinite(Number(surcharges[l.product.id] || 0)) || Number(surcharges[l.product.id] || 0) < 0 || Number(surcharges[l.product.id] || 0) > 1e12)));
  const serviceFeeTotal = mechanicFeeTotal(cart.map(l => ({ ...l, price: unitPrice(l.product), discount: Number(itemDiscounts[l.product.id] || 0) })), discountAmount);

  // Pintasan keyboard: F2 fokus pencarian, F4 buka checkout
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "F2") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === "F4") {
        e.preventDefault();
        if (cart.length > 0) setCheckoutOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cart.length]);

  function addToCart(product: Product) {
    setCart((prev) => {
      const idx = prev.findIndex((l) => l.product.id === product.id);
      if (idx >= 0) {
        const line = prev[idx];
        if (product.type === "barang" && line.qty >= product.stock) {
          toast.warning(`Stok ${product.name} tidak cukup (sisa ${product.stock})`);
          return prev;
        }
        const next = [...prev];
        next[idx] = { ...line, qty: line.qty + 1 };
        return next;
      }
      if (product.type === "barang" && product.stock < 1) {
        toast.warning(`Stok ${product.name} habis`);
        return prev;
      }
      return [...prev, { product, qty: 1 }];
    });
  }

  function decrementQty(productId: string) {
    setCart((prev) =>
      prev.map((l) => (l.product.id === productId ? { ...l, qty: l.qty - 1 } : l)).filter((l) => l.qty > 0)
    );
  }

  const checkoutMutation = useMutation({
    mutationFn: (body: CheckoutBody) => apiPost<Transaction>("/transactions", body),
    onSuccess: (tx) => {
      checkoutRequest.current = null;
      toast.success(`Transaksi ${tx.invoice_number} berhasil disimpan`);
      setReceipt(tx);
      setReceiptOpen(true);
      setCart([]);
      setCheckoutOpen(false);
      setPaymentMethod("cash");
      setCashInput(null);
      setDiscountInput('0');
      setItemDiscounts({});
      setSurcharges({});
      setCustomerId("");
      setDueDate("");
      setVehiclePlate("");
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["receivables"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const creditMissing = paymentMethod === "credit" && (!customerId || !dueDate);
  const cashReceived = cashInput === null ? totalAmount : Number(cashInput);
  const cashInvalid = paymentMethod === "cash" && (cashInput === "" || !Number.isFinite(cashReceived) || cashReceived < totalAmount || cashReceived > 1e12);

  function submitCheckout() {
    if (cart.length === 0 || creditMissing || cashInvalid || pricingInvalid || checkoutMutation.isPending) return;
    const body = {
      items: cart.map((l) => ({ product_id: l.product.id, qty: l.qty, credit_surcharge: paymentMethod === 'credit' ? Number(surcharges[l.product.id] || 0) : 0, discount_amount: Number(itemDiscounts[l.product.id] || 0) })),
      discount_total: discountAmount,
      payment_method: paymentMethod,
      cash_received: paymentMethod === "cash" ? cashReceived : null,
      customer_id: customerId || null,
      due_date: paymentMethod === "credit" ? dueDate : null,
      vehicle_plate: vehiclePlate.trim().toUpperCase() || null,
    };
    const payload = JSON.stringify(body);
    if (checkoutRequest.current?.payload !== payload) {
      checkoutRequest.current = { payload, id: crypto.randomUUID() };
    }
    checkoutMutation.mutate({ ...body, request_id: checkoutRequest.current.id });
  }

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Kasir POS</h1>
          <p className="text-sm text-muted-foreground">Cari barang/jasa, masukkan ke keranjang, lalu bayar.</p>
        </div>
        <div className="hidden gap-2 md:flex">
          <Badge variant="outline" className="rounded-md font-mono">[F2: Cari]</Badge>
          <Badge variant="outline" className="rounded-md font-mono">[F4: Bayar]</Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:h-[calc(100vh-9rem)] lg:grid-cols-12 xl:gap-6">
        {/* Katalog */}
        <section className="flex min-h-0 flex-col gap-3 lg:col-span-7 xl:col-span-8">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={searchRef}
              data-testid="pos-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari nama, SKU, atau merek ban/oli/jasa…"
              className="pl-9"
            />
          </div>
          <div className="flex gap-2" data-testid="pos-tabs">
            {TABS.map((t) => (
              <Button
                key={t.key}
                data-testid={`pos-tab-${t.key}`}
                variant={tab === t.key ? "default" : "outline"}
                size="sm"
                onClick={() => setTab(t.key)}
              >
                {t.label}
              </Button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            {productsQuery.isPending ? (
              <LoadingBlock />
            ) : productsQuery.isError ? (
              <ErrorBlock error={productsQuery.error} onRetry={() => void productsQuery.refetch()} />
            ) : filtered.length === 0 ? (
              <EmptyBlock title="Produk tidak ditemukan" description="Coba kata kunci lain atau pilih tab jenis produk." />
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                {filtered.map((p) => {
                  const out = p.type === "barang" && p.stock < 1;
                  return (
                    <button
                      key={p.id}
                      data-testid={`pos-product-card-${p.sku.toLowerCase()}`}
                      disabled={out}
                      onClick={() => addToCart(p)}
                      className="rounded-lg border border-border bg-card p-3 text-left transition hover:border-primary/60 hover:shadow-[0_0_20px_-5px_rgba(245,158,11,0.3)] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{p.sku}</span>
                        <Badge
                          variant="outline"
                          className={cn(
                            "rounded-sm px-1.5 text-[10px]",
                            p.type === "jasa" ? "border-sky-500/30 text-sky-700 dark:text-sky-400" : "border-amber-500/30 text-amber-700 dark:text-amber-400"
                          )}
                        >
                          {p.type === "jasa" ? "Jasa" : "Barang"}
                        </Badge>
                      </span>
                      <span className="mt-2 block text-sm font-semibold leading-snug">{p.name}</span>
                      <span className="text-xs text-muted-foreground">{[p.brand, p.size].filter(Boolean).join(" · ")}</span>
                      <span className="mt-2 flex items-center justify-between">
                        <span className="font-mono text-sm font-bold text-primary">{formatIDR(p.selling_price)}</span>
                        {p.type === "barang" ? (
                          <span
                            data-testid={`pos-stock-${p.sku.toLowerCase()}`}
                            className={cn("text-xs", p.stock <= 4 ? "font-semibold text-red-700 dark:text-red-400" : "text-muted-foreground")}
                          >
                            Stok {p.stock}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* Keranjang */}
        <aside className="flex min-h-0 flex-col rounded-xl border border-border bg-card lg:col-span-5 xl:col-span-4">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <p className="font-heading font-bold">Keranjang ({cart.length} item)</p>
            {cart.length > 0 ? (
              <Button variant="ghost" size="xs" data-testid="cart-clear-button" onClick={() => setCart([])}>
                Kosongkan
              </Button>
            ) : null}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {cart.length === 0 ? (
              <EmptyBlock
                title="Keranjang kosong"
                description="Klik produk di katalog untuk menambah ke keranjang."
                className="m-4 border-0 bg-transparent"
              />
            ) : (
              <AnimatePresence initial={false}>
                {cart.map((l) => (
                  <motion.div
                    key={l.product.id}
                    layout
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex items-center gap-2 border-b border-border/60 px-4 py-3"
                    data-testid={`cart-line-${l.product.sku.toLowerCase()}`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{l.product.name}</p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {formatIDR(l.product.selling_price)} × {l.qty}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="icon-xs"
                        data-testid={`cart-decrement-${l.product.sku.toLowerCase()}`}
                        onClick={() => decrementQty(l.product.id)}
                      >
                        <Minus />
                      </Button>
                      <span className="w-8 text-center font-mono text-sm" data-testid={`cart-qty-${l.product.sku.toLowerCase()}`}>
                        {l.qty}
                      </span>
                      <Button
                        variant="outline"
                        size="icon-xs"
                        data-testid={`cart-increment-${l.product.sku.toLowerCase()}`}
                        onClick={() => addToCart(l.product)}
                      >
                        <Plus />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`cart-remove-${l.product.sku.toLowerCase()}`}
                        onClick={() => setCart((prev) => prev.filter((x) => x.product.id !== l.product.id))}
                      >
                        <Trash2 className="text-red-700 dark:text-red-400" />
                      </Button>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </div>
          <div className="space-y-2 border-t border-border p-4">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="font-mono" data-testid="cart-subtotal">{formatIDR(grossAmount)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Service Fee Mekanik</span>
              <span className="font-mono" data-testid="cart-service-fee">{formatIDR(serviceFeeTotal)}</span>
            </div>
            <div className="flex justify-between font-heading text-lg font-bold">
              <span>Total</span>
              <span className="font-mono text-primary" data-testid="cart-total">{formatIDR(totalAmount)}</span>
            </div>
            <Button
              className="w-full"
              size="lg"
              data-testid="cart-checkout-button"
              disabled={cart.length === 0}
              onClick={() => setCheckoutOpen(true)}
            >
              Bayar
            </Button>
          </div>
        </aside>
      </div>

      {/* Dialog checkout */}
      <Dialog open={checkoutOpen} onOpenChange={setCheckoutOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md" data-testid="checkout-dialog">
          <DialogHeader>
            <DialogTitle>Checkout — {formatIDR(totalAmount)}</DialogTitle>
            <DialogDescription>
              Pilih metode pembayaran. Untuk tempo (kredit), pelanggan &amp; jatuh tempo wajib diisi — sistem akan
              otomatis membuat piutang.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                data-testid="payment-cash-btn"
                onClick={() => setPaymentMethod("cash")}
                className={cn(
                  "rounded-lg border px-3 py-3 font-semibold transition",
                  paymentMethod === "cash"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-muted-foreground"
                )}
              >
                Tunai
              </button>
              <button
                type="button"
                data-testid="payment-credit-btn"
                onClick={() => setPaymentMethod("credit")}
                className={cn(
                  "rounded-lg border px-3 py-3 font-semibold transition",
                  paymentMethod === "credit"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-muted-foreground"
                )}
              >
                Tempo (Kredit)
              </button>
            </div>
            <div className="space-y-2">
              <Label htmlFor="checkout-payment-method">Tipe pembayaran</Label>
              <select id="checkout-payment-method" data-testid="checkout-payment-method" className="bk-control" value={paymentMethod} onChange={e => setPaymentMethod(e.target.value as PaymentMethod)}>
                {PAYMENT_OPTIONS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </div>
            {paymentMethod === 'credit' && <div className="space-y-3 rounded-lg border border-border p-3">
              <p className="text-sm font-semibold">Tambahan harga tempo per unit</p>
              {cart.map(line => <div key={line.product.id} className="space-y-1">
                <Label htmlFor={`surcharge-${line.product.id}`}>{line.product.name} · {line.qty} unit</Label>
                <Input id={`surcharge-${line.product.id}`} aria-label={`Tambahan tempo ${line.product.name}`} type="number" min="0" max="1000000000000" step="0.01"
                  value={surcharges[line.product.id] ?? '0'} onChange={e => setSurcharges(previous => ({ ...previous, [line.product.id]: e.target.value }))} />
                <p className="text-xs text-muted-foreground">Harga tempo/unit: {formatIDR(unitPrice(line.product))}</p>
              </div>)}
            </div>}
            <div className="space-y-2 rounded-lg border border-border p-3">
              {cart.map(line => <div key={line.product.id} className="space-y-1">
                <Label htmlFor={`item-discount-${line.product.id}`}>Potongan item {line.product.name} (Rp, total {line.qty} unit)</Label>
                <Input id={`item-discount-${line.product.id}`} data-testid={`item-discount-${line.product.id}`} type="number" min="0" max={unitPrice(line.product) * line.qty} step="0.01" value={itemDiscounts[line.product.id] || '0'} onChange={e => setItemDiscounts(prev => ({ ...prev, [line.product.id]: e.target.value }))} />
              </div>)}
              <Label htmlFor="checkout-discount">Potongan total nota (Rp)</Label>
              <Input id="checkout-discount" data-testid="checkout-discount" type="number" min="0" max={Math.max(0, grossAmount - itemDiscountTotal)} step="0.01" value={discountInput} onChange={e => setDiscountInput(e.target.value)} />
              <p className="text-sm">Sebelum potongan: {formatIDR(grossAmount)}</p>
              <p className="text-sm font-semibold" data-testid="checkout-net-total">Total bayar: {formatIDR(totalAmount)}</p>
              <p className="text-sm" data-testid="checkout-mechanic-fee">Komisi montir: {formatIDR(serviceFeeTotal)}. SERVICE: 50% setelah potongan; item lain sesuai DATABASE.</p>
              {pricingInvalid && <p className="text-xs text-red-700 dark:text-red-400">Periksa tambahan harga dan potongan. Potongan tidak boleh melebihi total; total tempo harus lebih dari nol.</p>}
            </div>
            {paymentMethod === "cash" && <div className="space-y-2 rounded-lg border border-border p-3">
              <Label htmlFor="checkout-cash-received">Uang diterima (Rp)</Label>
              <div className="flex gap-2">
                <Input id="checkout-cash-received" data-testid="checkout-cash-received" type="number" inputMode="decimal"
                  min={totalAmount} max={1e12} step="0.01" value={cashInput ?? totalAmount}
                  aria-invalid={cashInvalid} onChange={(event) => setCashInput(event.target.value)} />
                <Button type="button" variant="outline" onClick={() => setCashInput(null)}>Uang pas</Button>
              </div>
              {cashInvalid ? <p className="text-xs text-red-700 dark:text-red-400">Isi uang diterima minimal sebesar total transaksi.</p>
                : <p className="flex justify-between text-sm"><span>Kembalian</span><strong data-testid="checkout-change">{formatIDR(Math.round((cashReceived - totalAmount) * 100) / 100)}</strong></p>}
            </div>}
            <div className="space-y-2">
              <Label htmlFor="checkout-customer">
                Pelanggan {paymentMethod === "credit" ? "(wajib)" : "(opsional)"}
              </Label>
              <Select value={customerId || "none"} onValueChange={(v) => setCustomerId(v === "none" ? "" : v)}>
                <SelectTrigger id="checkout-customer" data-testid="checkout-customer-select">
                  <SelectValue>
                    {(v) => {
                      const val = v as string;
                      if (val === "none") return "Umum / Tanpa Nama";
                      return (customersQuery.data ?? []).find((c) => c.id === val)?.name ?? "Pilih pelanggan";
                    }}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Umum / Tanpa Nama</SelectItem>
                  {(customersQuery.data ?? []).map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {paymentMethod === "credit" ? (
              <div className="space-y-2">
                <Label htmlFor="checkout-due-date">Jatuh Tempo (wajib)</Label>
                <Input
                  id="checkout-due-date"
                  data-testid="checkout-due-date-input"
                  type="date"
                  min={todayLocalISO()}
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                />
              </div>
            ) : null}
            <div className="space-y-2">
              <Label htmlFor="checkout-vehicle-plate">Nomor Polisi (opsional)</Label>
              <Input
                id="checkout-vehicle-plate"
                data-testid="checkout-vehicle-plate-input"
                className="font-mono uppercase"
                value={vehiclePlate}
                onChange={(e) => setVehiclePlate(e.target.value)}
                placeholder="mis. B 1234 XYZ"
              />
              <p className="text-xs text-muted-foreground">
                Diisi agar servis tercatat di Riwayat Kendaraan (ban &amp; oli terakhir).
              </p>
            </div>
            {creditMissing ? (
              <p className="text-xs text-red-700 dark:text-red-400" data-testid="checkout-credit-warning">
                Pembayaran tempo wajib memilih pelanggan dan tanggal jatuh tempo.
              </p>
            ) : null}
            <Button
              className="w-full"
              size="lg"
              data-testid="checkout-submit-button"
              disabled={checkoutMutation.isPending || creditMissing || cashInvalid || pricingInvalid}
              onClick={submitCheckout}
            >
              {checkoutMutation.isPending ? "Menyimpan…" : `Bayar ${formatIDR(totalAmount)}`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <SalesNoteModal transaction={receipt} open={receiptOpen} onOpenChange={setReceiptOpen} />
    </div>
  );
}
