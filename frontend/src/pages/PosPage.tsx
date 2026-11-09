import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Minus, Plus, Search, Trash2 } from "lucide-react";
import SalesNoteModal from "@/components/pos/SalesNoteModal";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiGet, apiPost } from "@/lib/api";
import { formatIDR, getApiErrorMessage } from "@/lib/format";
import type { Customer, NonCashMethod, PaymentMethod, Product, Transaction } from "@/lib/types";
import { cn } from "@/lib/utils";
import { NON_CASH_OPTIONS, PAYMENT_OPTIONS } from "@/lib/payments";
import { mechanicFeeTotal } from "@/lib/pos-pricing";

type CartLine = { product: Product; qty: number };
type TabKey = "semua" | "barang" | "jasa";
type CheckoutBody = {
  request_id: string;
  items: { product_id: string; qty: number; credit_surcharge: number; discount_per_unit: number }[];
  discount_total: number;
  payment_method: PaymentMethod;
  cash_received: number | null;
  cash_amount: number | null;
  transfer_amount: number | null;
  transfer_method: NonCashMethod | null;
  customer_id: string | null;
  due_date: string | null;
  credit_term_days: number | null;
  down_payment_amount: number;
  down_payment_method: Exclude<PaymentMethod, "credit"> | null;
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
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [receivedInput, setReceivedInput] = useState<string | null>(null);
  const [mixCashInput, setMixCashInput] = useState("");
  const [mixTransferInput, setMixTransferInput] = useState("");
  const [mixTransferMethod, setMixTransferMethod] = useState<NonCashMethod>("transfer_bca");
  const [itemDiscounts, setItemDiscounts] = useState<Record<string, string>>({});
  const [surcharges, setSurcharges] = useState<Record<string, string>>({});
  const [customerId, setCustomerId] = useState("");
  const [creditTermDays, setCreditTermDays] = useState("14");
  const [useDownPayment, setUseDownPayment] = useState(false);
  const [downPaymentInput, setDownPaymentInput] = useState("");
  const [downPaymentMethod, setDownPaymentMethod] = useState<Exclude<PaymentMethod, "credit">>("cash");
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [receipt, setReceipt] = useState<Transaction | null>(null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [autoPrint, setAutoPrint] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const cartRef = useRef<HTMLElement>(null);
  const checkoutRef = useRef<HTMLDivElement>(null);
  const submitting = useRef(false);
  const checkoutRequest = useRef<{ payload: string; id: string } | null>(null);

  const productsQuery = useQuery({ queryKey: ["products"], queryFn: () => apiGet<Product[]>("/products") });
  const customersQuery = useQuery({ queryKey: ["customers"], queryFn: () => apiGet<Customer[]>("/customers") });
  const systemQuery = useQuery({ queryKey: ["system"], queryFn: () => apiGet<{ today: string }>("/system") });

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    const products = productsQuery.data ?? [];
    return products.filter((p) => {
      if (tab !== "semua" && p.type !== tab) return false;
      if (!term) return true;
      return (
        p.name.toLowerCase().includes(term) ||
        p.sku.toLowerCase().includes(term) ||
        p.brand.toLowerCase().includes(term)
      );
    });
  }, [productsQuery.data, search, tab]);

  const unitPrice = (product: Product) => product.selling_price + (paymentMethod === 'credit' ? Number(surcharges[product.id] || 0) : 0);
  const grossAmount = cart.reduce((sum, line) => sum + Math.round(unitPrice(line.product) * 100) * line.qty, 0) / 100;
  const isCredit = paymentMethod === "credit";
  const itemDiscount = (productId: string) => isCredit ? 0 : Number(itemDiscounts[productId] || 0);
  const itemDiscountTotal = cart.reduce((sum, l) => sum + Math.round(itemDiscount(l.product.id) * 100) * l.qty, 0) / 100;
  const totalAmount = Math.max(0, Math.round((grossAmount - itemDiscountTotal) * 100) / 100);
  const pricingInvalid = cart.some(l => {
    const discount = itemDiscount(l.product.id);
    return !Number.isFinite(discount) || discount < 0 || discount > unitPrice(l.product) || discount > 1e12;
  }) ||
    (paymentMethod === 'credit' && (totalAmount <= 0 || cart.some(l => !Number.isFinite(Number(surcharges[l.product.id] || 0)) || Number(surcharges[l.product.id] || 0) < 0 || Number(surcharges[l.product.id] || 0) > 1e12)));
  const serviceFeeTotal = mechanicFeeTotal(cart.map(l => ({ ...l, price: unitPrice(l.product), discount: itemDiscount(l.product.id) * l.qty })), 0, isCredit);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "F2") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === "F4") {
        e.preventDefault();
        if (cart.length > 0) {
          checkoutRef.current?.scrollIntoView({ block: "center" });
          checkoutRef.current?.focus({ preventScroll: true });
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cart.length]);

  function addToCart(product: Product) {
    if (submitting.current) return;
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
      submitting.current = false;
      checkoutRequest.current = null;
      toast.success(`Transaksi ${tx.invoice_number} berhasil disimpan`);
      setReceipt(tx);
      setAutoPrint(true);
      setReceiptOpen(true);
      setCart([]);
      setPaymentMethod("cash");
      setReceivedInput(null);
      setMixCashInput("");
      setMixTransferInput("");
      setMixTransferMethod("transfer_bca");
      setItemDiscounts({});
      setSurcharges({});
      setCustomerId("");
      setCreditTermDays("14");
      setUseDownPayment(false);
      setDownPaymentInput("");
      setDownPaymentMethod("cash");
      setVehiclePlate("");
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["receivables"] });
      void queryClient.invalidateQueries({ queryKey: ["receivables-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["books"] });
      void queryClient.invalidateQueries({ queryKey: ["books-daily"] });
      void queryClient.invalidateQueries({ queryKey: ["books-monthly"] });
      void queryClient.invalidateQueries({ queryKey: ["excel-reports"] });
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
    onError: (error) => {
      submitting.current = false;
      toast.error(getApiErrorMessage(error));
    },
  });

  const termDays = Number(creditTermDays);
  const termInvalid = isCredit && (!Number.isInteger(termDays) || termDays < 1 || termDays > 3650);
  const creditMissing = isCredit && (!customerId || !(customersQuery.data ?? []).some(customer => customer.id === customerId));
  const downPaymentAmount = isCredit && useDownPayment ? Number(downPaymentInput) : 0;
  const downPaymentInvalid = isCredit && useDownPayment && (downPaymentInput === "" || !Number.isFinite(downPaymentAmount) || downPaymentAmount <= 0 || downPaymentAmount >= totalAmount || downPaymentAmount > 1e12);
  const remainingAmount = Math.max(0, Math.round((totalAmount - downPaymentAmount) * 100) / 100);
  const dueDatePreview = isCredit && !termInvalid && systemQuery.data?.today
    ? (() => { const date = new Date(`${systemQuery.data.today}T12:00:00Z`); date.setUTCDate(date.getUTCDate() + termDays); return date.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }); })()
    : null;

  const isMixPayment = isCredit ? (useDownPayment && downPaymentMethod === "mix") : paymentMethod === "mix";
  const mixTargetAmount = isCredit ? downPaymentAmount : totalAmount;
  const mixCashAmount = isMixPayment ? Number(mixCashInput) : 0;
  const mixTransferAmount = isMixPayment ? Number(mixTransferInput) : 0;
  const mixSumMatches = Math.round((mixCashAmount + mixTransferAmount) * 100) === Math.round(mixTargetAmount * 100);
  const mixInvalid = isMixPayment && (
    mixCashInput === "" ||
    mixTransferInput === "" ||
    !Number.isFinite(mixCashAmount) ||
    !Number.isFinite(mixTransferAmount) ||
    mixCashAmount <= 0 ||
    mixTransferAmount <= 0 ||
    !mixSumMatches
  );

  function handleMixCashChange(val: string) {
    setMixCashInput(val);
    const cashNum = Number(val);
    if (val !== "" && Number.isFinite(cashNum) && cashNum >= 0 && Number.isFinite(mixTargetAmount) && mixTargetAmount > 0 && cashNum < mixTargetAmount) {
      setMixTransferInput(String(Math.max(0, Math.round((mixTargetAmount - cashNum) * 100) / 100)));
    }
  }

  function handleMixTransferChange(val: string) {
    setMixTransferInput(val);
    const tfNum = Number(val);
    if (val !== "" && Number.isFinite(tfNum) && tfNum >= 0 && Number.isFinite(mixTargetAmount) && mixTargetAmount > 0 && tfNum < mixTargetAmount) {
      setMixCashInput(String(Math.max(0, Math.round((mixTargetAmount - tfNum) * 100) / 100)));
    }
  }

  const amountReceived = paymentMethod === "mix" ? totalAmount : (receivedInput === null ? totalAmount : Number(receivedInput));
  const receivedInvalid = paymentMethod !== "credit" && paymentMethod !== "mix" && (receivedInput === "" || !Number.isFinite(amountReceived) || amountReceived < totalAmount || amountReceived > 1e12);

  function submitCheckout() {
    if (cart.length === 0 || creditMissing || termInvalid || downPaymentInvalid || receivedInvalid || mixInvalid || pricingInvalid || submitting.current || checkoutMutation.isPending) return;
    const body = {
      items: cart.map((l) => ({ product_id: l.product.id, qty: l.qty, credit_surcharge: isCredit ? Number(surcharges[l.product.id] || 0) : 0, discount_per_unit: itemDiscount(l.product.id) })),
      discount_total: 0,
      payment_method: paymentMethod,
      cash_received: paymentMethod !== "credit" ? amountReceived : null,
      cash_amount: isMixPayment ? mixCashAmount : null,
      transfer_amount: isMixPayment ? mixTransferAmount : null,
      transfer_method: isMixPayment ? mixTransferMethod : null,
      customer_id: customerId || null,
      due_date: null,
      credit_term_days: isCredit ? termDays : null,
      down_payment_amount: downPaymentAmount,
      down_payment_method: isCredit && useDownPayment ? downPaymentMethod : null,
      vehicle_plate: vehiclePlate.trim().toUpperCase() || null,
    };
    const payload = JSON.stringify(body);
    if (checkoutRequest.current?.payload !== payload) {
      checkoutRequest.current = { payload, id: crypto.randomUUID() };
    }
    submitting.current = true;
    checkoutMutation.mutate({ ...body, request_id: checkoutRequest.current.id });
  }

  return (
    <div className="page-workspace">
      <div className="page-heading">
        <div>
          <h1 className="font-heading">Kasir penjualan</h1>
          <p className="text-sm text-muted-foreground">Cari barang/jasa, masukkan ke keranjang, lalu bayar.</p>
        </div>
        <div className="hidden gap-2 md:flex">
          <span className="text-xs text-muted-foreground"><kbd className="rounded border border-input px-2 py-1">F2</kbd> Cari barang</span>
          <span className="text-xs text-muted-foreground"><kbd className="rounded border border-input px-2 py-1">F4</kbd> Pembayaran</span>
        </div>
      </div>

      {receipt ? <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-card px-4 py-3">
        <p className="text-sm">{receipt.invoice_number} sudah tersimpan.</p>
        <Button variant="outline" size="sm" data-testid="reprint-last-transaction" onClick={() => { setAutoPrint(false); setReceiptOpen(true); }}>Cetak ulang nota</Button>
      </div> : null}

      {cart.length > 0 ? (
        <Button variant="outline" className="pos-cart-jump mb-4 w-full justify-between" data-testid="pos-cart-jump" onClick={() => cartRef.current?.scrollIntoView({ block: 'start' })}>
          <span>Lihat keranjang ({cart.length} item)</span><span className="font-mono">{formatIDR(totalAmount)}</span>
        </Button>
      ) : null}
      <div className="pos-layout">
        <section className="pos-catalog flex flex-col gap-3" aria-label="Katalog barang dan jasa">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={searchRef}
              data-testid="pos-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari nama, SKU, atau merek ban/oli/jasa…"
              aria-label="Cari barang atau jasa"
              className="pl-9"
            />
          </div>
          <div className="flex flex-wrap gap-2" data-testid="pos-tabs" aria-label="Jenis produk">
            {TABS.map((t) => (
              <Button
                key={t.key}
                data-testid={`pos-tab-${t.key}`}
                variant={tab === t.key ? "default" : "outline"}
                size="sm"
                onClick={() => setTab(t.key)}
                aria-pressed={tab === t.key}
              >
                {t.label}
              </Button>
            ))}
          </div>
          <div className="pos-catalog-products min-w-0">
            {productsQuery.isPending ? (
              <LoadingBlock />
            ) : productsQuery.isError ? (
              <ErrorBlock error={productsQuery.error} onRetry={() => void productsQuery.refetch()} />
            ) : filtered.length === 0 ? (
              <EmptyBlock title="Produk tidak ditemukan" description="Coba kata kunci lain atau pilih tab jenis produk." />
            ) : (
              <div className="pos-catalog-grid">
                {filtered.map((p) => {
                  const out = p.type === "barang" && p.stock < 1;
                  return (
                    <button
                      key={p.id}
                      data-testid={`pos-product-card-${p.sku.toLowerCase()}`}
                      disabled={out || checkoutMutation.isPending}
                      onClick={() => addToCart(p)}
                      className="pos-product"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-xs text-muted-foreground">{p.sku}</span>
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

        <aside ref={cartRef} className="pos-cart pos-checkout !static !max-h-none scroll-mt-20" aria-label="Keranjang dan pembayaran">
          <fieldset disabled={checkoutMutation.isPending} className="m-0 min-w-0 border-0 p-0">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <p className="font-heading font-bold">Keranjang ({cart.length} item)</p>
            {cart.length > 0 ? (
              <Button variant="ghost" size="xs" data-testid="cart-clear-button" onClick={() => setCart([])}>
                Kosongkan
              </Button>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-2 border-b border-border p-4" aria-label="Jenis penjualan">
            <Button type="button" variant={isCredit ? "outline" : "secondary"} className={cn(!isCredit && "border-primary ring-1 ring-primary font-semibold")} data-testid="payment-cash-btn" aria-pressed={!isCredit}
              onClick={() => setPaymentMethod(current => current === "credit" ? "cash" : current)}>Cash</Button>
            <Button type="button" variant={isCredit ? "secondary" : "outline"} className={cn(isCredit && "border-primary ring-1 ring-primary font-semibold")} data-testid="payment-credit-btn" aria-pressed={isCredit}
              onClick={() => setPaymentMethod("credit")}>Tempo</Button>
          </div>
          <div>
            {cart.length === 0 ? (
              <EmptyBlock
                title="Keranjang kosong"
                description="Klik produk di katalog untuk menambah ke keranjang."
                className="m-4 border-0 bg-transparent"
              />
            ) : (
              <div>
                {cart.map((l) => (
                  <div
                    key={l.product.id}
                    className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3"
                    data-testid={`cart-line-${l.product.sku.toLowerCase()}`}
                  >
                    <div className="min-w-0 flex-[1_1_160px]">
                      <p className="text-sm font-semibold">{l.product.name}</p>
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
                        aria-label={`Kurangi jumlah ${l.product.name}`}
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
                        aria-label={`Tambah jumlah ${l.product.name}`}
                      >
                        <Plus />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`cart-remove-${l.product.sku.toLowerCase()}`}
                        onClick={() => setCart((prev) => prev.filter((x) => x.product.id !== l.product.id))}
                        aria-label={`Hapus ${l.product.name} dari keranjang`}
                      >
                        <Trash2 className="text-red-700 dark:text-red-400" />
                      </Button>
                    </div>
                    <div className="w-full space-y-1">
                      <Label htmlFor={isCredit ? `surcharge-${l.product.id}` : `item-discount-${l.product.id}`}>
                        {isCredit ? "Tambahan tempo (Rp per unit)" : "Potongan harga (Rp per unit)"}
                      </Label>
                      {isCredit ? <Input id={`surcharge-${l.product.id}`} data-testid={`surcharge-${l.product.id}`} type="number" inputMode="decimal" min="0" max="1000000000000" step="0.01"
                        value={surcharges[l.product.id] ?? "0"} onChange={event => setSurcharges(previous => ({ ...previous, [l.product.id]: event.target.value }))} />
                        : <Input id={`item-discount-${l.product.id}`} data-testid={`item-discount-${l.product.id}`} type="number" inputMode="decimal" min="0" max={l.product.selling_price} step="0.01"
                          value={itemDiscounts[l.product.id] ?? "0"} onChange={event => setItemDiscounts(previous => ({ ...previous, [l.product.id]: event.target.value }))} />}
                      <p className="text-xs text-muted-foreground">{isCredit ? "Harga tempo" : "Harga setelah potongan"}/unit: {formatIDR(unitPrice(l.product) - itemDiscount(l.product.id))}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {cart.length > 0 ? <div ref={checkoutRef} tabIndex={-1} className="space-y-4 border-t border-border p-4 focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2" data-testid="checkout-panel" aria-label="Pembayaran">
            <div className="space-y-2">
              <Label htmlFor="checkout-customer">Pelanggan {isCredit ? "(wajib)" : "(opsional)"}</Label>
              <select id="checkout-customer" data-testid="checkout-customer-select" className="bk-control" value={customerId}
                disabled={customersQuery.isPending || customersQuery.isError} aria-invalid={creditMissing} onChange={event => setCustomerId(event.target.value)}>
                <option value="">{customersQuery.isPending ? "Memuat pelanggan..." : isCredit ? "Pilih pelanggan" : "Umum / Tanpa Nama"}</option>
                {(customersQuery.data ?? []).map(customer => <option key={customer.id} value={customer.id}>{customer.name}</option>)}
              </select>
              {customersQuery.isError ? <div role="alert" className="text-sm text-destructive">{getApiErrorMessage(customersQuery.error)} <Button type="button" size="sm" variant="outline" onClick={() => void customersQuery.refetch()}>Muat ulang pelanggan</Button></div>
                : !customersQuery.isPending && (customersQuery.data ?? []).length === 0 ? <p className="text-xs text-muted-foreground">Belum ada pelanggan. Tambahkan melalui menu Pelanggan sebelum penjualan tempo.</p> : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="checkout-vehicle-plate">Nomor mobil (opsional)</Label>
              <Input id="checkout-vehicle-plate" data-testid="checkout-vehicle-plate-input" className="font-mono uppercase" maxLength={30}
                value={vehiclePlate} onChange={event => setVehiclePlate(event.target.value)} placeholder="mis. B 1234 XYZ" />
            </div>
            {isCredit ? <>
              <div className="space-y-2">
                <Label htmlFor="checkout-term-days">Tenor tempo (hari)</Label>
                <Input id="checkout-term-days" data-testid="checkout-term-days" type="number" inputMode="numeric" min="1" max="3650" step="1"
                  value={creditTermDays} aria-invalid={termInvalid} aria-describedby="checkout-term-feedback" onChange={event => setCreditTermDays(event.target.value)} />
                <p id="checkout-term-feedback" className={cn("text-xs", termInvalid ? "text-destructive" : "text-muted-foreground")}>
                  {termInvalid ? "Isi tenor 1 sampai 3650 hari, tanpa desimal." : dueDatePreview ? `Jatuh tempo: ${dueDatePreview}` : "Jatuh tempo dihitung dari tanggal transaksi saat disimpan."}
                </p>
                {systemQuery.isPending ? <p role="status" className="text-xs text-muted-foreground">Memuat tanggal transaksi...</p> : systemQuery.isError ? <div className="text-xs text-muted-foreground">Tanggal pratinjau belum tersedia. <Button type="button" size="sm" variant="outline" onClick={() => void systemQuery.refetch()}>Muat ulang tanggal</Button></div> : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="checkout-down-payment-option">Uang muka</Label>
                <select id="checkout-down-payment-option" data-testid="checkout-down-payment-option" className="bk-control" value={useDownPayment ? "with" : "none"}
                  onChange={event => setUseDownPayment(event.target.value === "with")}>
                  <option value="none">Tanpa uang muka</option><option value="with">Pakai uang muka</option>
                </select>
              </div>
              {useDownPayment ? <div className="space-y-2">
                <Label htmlFor="checkout-down-payment-amount">Nominal uang muka (Rp)</Label>
                <Input id="checkout-down-payment-amount" data-testid="checkout-down-payment-amount" type="number" inputMode="decimal" min="0.01" max={Math.max(0, totalAmount - 0.01)} step="0.01"
                  value={downPaymentInput} aria-invalid={downPaymentInvalid} aria-describedby="checkout-dp-feedback" onChange={event => setDownPaymentInput(event.target.value)} />
                {downPaymentInvalid ? <p id="checkout-dp-feedback" role="alert" className="text-xs text-destructive">Uang muka harus lebih dari nol dan lebih kecil dari total. Untuk pelunasan penuh, pilih Cash.</p> : null}
              </div> : null}
            </> : null}
            <div className="space-y-2">
              <Label htmlFor="checkout-payment-method">{isCredit ? "Pembayaran uang muka" : "Pembayaran"}</Label>
              <select id="checkout-payment-method" data-testid="checkout-payment-method" className="bk-control" disabled={isCredit && !useDownPayment}
                value={isCredit ? downPaymentMethod : paymentMethod}
                onChange={event => isCredit ? setDownPaymentMethod(event.target.value as Exclude<PaymentMethod, "credit">) : setPaymentMethod(event.target.value as PaymentMethod)}>
                {PAYMENT_OPTIONS.filter(([key]) => key !== "credit").map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
              {isCredit && !useDownPayment ? <p className="text-xs text-muted-foreground">Belum ada pembayaran. Seluruh total menjadi piutang.</p> : null}
            </div>
            {isMixPayment ? (
              <div className="space-y-3 rounded-lg border border-border bg-secondary/30 p-3" data-testid="checkout-mix-panel">
                <p className="text-xs font-medium text-muted-foreground">
                  Rincian Mix (Tunai + Transfer) untuk {isCredit ? "uang muka" : "total transaksi"} ({formatIDR(Number.isFinite(mixTargetAmount) ? mixTargetAmount : 0)})
                </p>
                <div className="space-y-2">
                  <Label htmlFor="checkout-mix-cash">Nominal tunai (Rp)</Label>
                  <Input
                    id="checkout-mix-cash"
                    data-testid="checkout-mix-cash"
                    type="number"
                    inputMode="decimal"
                    min="0.01"
                    max={Math.max(0.01, (Number.isFinite(mixTargetAmount) ? mixTargetAmount : totalAmount) - 0.01)}
                    step="0.01"
                    value={mixCashInput}
                    aria-invalid={mixInvalid}
                    onChange={event => handleMixCashChange(event.target.value)}
                    placeholder="Nominal bayar tunai"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="checkout-mix-transfer">Nominal transfer (Rp)</Label>
                  <Input
                    id="checkout-mix-transfer"
                    data-testid="checkout-mix-transfer"
                    type="number"
                    inputMode="decimal"
                    min="0.01"
                    max={Math.max(0.01, (Number.isFinite(mixTargetAmount) ? mixTargetAmount : totalAmount) - 0.01)}
                    step="0.01"
                    value={mixTransferInput}
                    aria-invalid={mixInvalid}
                    onChange={event => handleMixTransferChange(event.target.value)}
                    placeholder="Nominal bayar transfer"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="checkout-mix-method">Rekening / kanal transfer</Label>
                  <select
                    id="checkout-mix-method"
                    data-testid="checkout-mix-method"
                    className="bk-control"
                    value={mixTransferMethod}
                    onChange={event => setMixTransferMethod(event.target.value as NonCashMethod)}
                  >
                    {NON_CASH_OPTIONS.map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>
                {mixInvalid ? (
                  <p role="alert" data-testid="checkout-mix-error" className="text-xs text-destructive">
                    Isi nominal tunai dan transfer lebih dari 0 dengan jumlah tepat sebesar {formatIDR(Number.isFinite(mixTargetAmount) ? mixTargetAmount : 0)}.
                  </p>
                ) : null}
              </div>
            ) : null}
            {!isCredit && paymentMethod !== "mix" ? <div className="space-y-2">
              <Label htmlFor="checkout-cash-received">Bayar (Rp)</Label>
              <div className="flex gap-2">
                <Input id="checkout-cash-received" data-testid="checkout-cash-received" type="number" inputMode="decimal" min={totalAmount} max={1e12} step="0.01"
                  value={receivedInput ?? (Number.isFinite(totalAmount) ? totalAmount : "")} aria-invalid={receivedInvalid} aria-describedby={receivedInvalid ? "checkout-received-error" : "checkout-received-feedback"} onChange={event => setReceivedInput(event.target.value)} />
                <Button type="button" variant="outline" onClick={() => setReceivedInput(null)}>Uang pas</Button>
              </div>
              {receivedInvalid ? <p id="checkout-received-error" role="alert" className="text-xs text-destructive">Isi pembayaran minimal sebesar total transaksi.</p> : null}
            </div> : null}
            {creditMissing ? <p role="alert" className="text-xs text-destructive" data-testid="checkout-credit-warning">Pilih pelanggan untuk penjualan tempo.</p> : null}
            {pricingInvalid ? <p role="alert" className="text-xs text-destructive">Periksa tambahan harga dan potongan. Potongan maksimal sebesar harga barang, dan total tempo harus lebih dari nol.</p> : null}
          </div> : null}
          <div className="pos-cart-total space-y-3 border-t border-border p-4">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="font-mono" data-testid="cart-subtotal">{formatIDR(grossAmount)}</span>
            </div>
            {itemDiscountTotal > 0 ? <div className="flex justify-between text-sm"><span className="text-muted-foreground">Potongan</span><span className="font-mono">-{formatIDR(itemDiscountTotal)}</span></div> : null}
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Service Fee Mekanik</span>
              <span className="font-mono" data-testid="cart-service-fee">{formatIDR(serviceFeeTotal)}</span>
            </div>
            <div className="flex justify-between font-heading text-lg font-bold">
              <span>Total</span>
              <span className="font-mono text-primary" data-testid="cart-total">{formatIDR(totalAmount)}</span>
            </div>
            {cart.length > 0 ? <>
              <p className="text-xs text-muted-foreground" data-testid="checkout-mechanic-fee">Komisi SERVICE: 50% {isCredit ? "harga tunai" : "setelah potongan"}; item lain mengikuti komisi yang tersimpan.</p>
              {isCredit ? <div className="space-y-2 border-t border-border pt-3 text-sm" aria-live="polite">
                <div className="flex justify-between gap-2"><span>Uang muka</span><span className="font-mono">{formatIDR(Number.isFinite(downPaymentAmount) ? downPaymentAmount : 0)}</span></div>
                <div className="flex justify-between gap-2 font-semibold"><span>Sisa piutang</span><span data-testid="checkout-remaining" className="font-mono">{formatIDR(Number.isFinite(remainingAmount) ? remainingAmount : 0)}</span></div>
              </div> : <p id="checkout-received-feedback" className="flex justify-between gap-2 border-t border-border pt-3 text-sm" aria-live="polite"><span>{paymentMethod === "cash" ? "Kembalian" : "Kelebihan pembayaran"}</span><strong className="font-mono" data-testid="checkout-change">{formatIDR(receivedInvalid || mixInvalid || pricingInvalid ? 0 : Math.round((amountReceived - totalAmount) * 100) / 100)}</strong></p>}
              {checkoutMutation.isError ? <p role="alert" data-testid="checkout-save-error" className="text-sm text-destructive">{getApiErrorMessage(checkoutMutation.error)}. Coba Print lagi untuk melanjutkan permintaan yang sama.</p> : null}
            <Button
              className="pos-pay-button w-full"
              size="lg"
              data-testid="checkout-submit-button"
              disabled={checkoutMutation.isPending || creditMissing || termInvalid || downPaymentInvalid || receivedInvalid || mixInvalid || pricingInvalid}
              onClick={submitCheckout}
            >
              {checkoutMutation.isPending ? "Menyimpan..." : "Print"}
            </Button>
            <p className="text-xs text-muted-foreground">Transaksi disimpan sebelum dialog cetak dibuka. Batal cetak tetap tersimpan.</p>
            </> : null}
          </div>
          </fieldset>
        </aside>
      </div>

      <SalesNoteModal transaction={receipt} open={receiptOpen} autoPrint={autoPrint} onOpenChange={setReceiptOpen} />
    </div>
  );
}
