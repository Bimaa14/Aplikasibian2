import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import { formatIDR, getApiErrorMessage } from "@/lib/format";
import type { Product, ProductOwner, ProductType } from "@/lib/types";
import { cn } from "@/lib/utils";

type ProductForm = {
  tax: string;
  category: Product['category'];
  type: ProductType;
  sku: string;
  name: string;
  brand: string;
  size: string;
  owner: ProductOwner | '';
  stock: string;
  cost_price: string;
  selling_price: string;
  service_fee: string;
};

const OWNER_LABEL: Record<ProductOwner, string> = {
  non: "NON", polosan: "POLOSAN", "non vpt": "NON VPT", "non vat": "NON VAT",
  bian: "Barang Bian",
  ibu: "Barang Ibu (Mamah Bian)",
};

const EMPTY_FORM: ProductForm = {
  tax: '0',
  category: 'TIRE',
  type: "barang",
  sku: "",
  name: "",
  brand: "",
  size: "",
  owner: "bian",
  stock: "0",
  cost_price: "0",
  selling_price: "0",
  service_fee: "0",
};

export default function ProductsPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [deleting, setDeleting] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductForm>(EMPTY_FORM);
  const [ownerFilter, setOwnerFilter] = useState<"all" | ProductOwner>("all");
  const [taxFilter, setTaxFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [search, setSearch] = useState("");

  const filters = new URLSearchParams();
  if (ownerFilter !== 'all') filters.set('owner', ownerFilter);
  if (taxFilter) filters.set('tax', taxFilter);
  if (categoryFilter) filters.set('category', categoryFilter);
  const productsQuery = useQuery({ queryKey: ["products", filters.toString()], queryFn: () => apiGet<Product[]>(`/products?${filters}`) });

  const set = <K extends keyof ProductForm>(key: K, value: ProductForm[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        ...(form.tax !== '' ? { tax: Number(form.tax) } : {}),
        category: form.category,
        type: form.type,
        sku: form.sku.trim(),
        name: form.name.trim(),
        brand: form.brand.trim(),
        size: form.size.trim(),
        ...(form.owner !== '' ? { owner: form.owner } : {}),
        ...(editing && Number(form.stock) === editing.stock ? {} : { stock: form.type === "barang" ? Number(form.stock || 0) : 0 }),
        cost_price: Number(form.cost_price || 0),
        selling_price: Number(form.selling_price || 0),
        service_fee: Number(form.service_fee || 0),
      };
      return editing
        ? apiPut<Product>(`/products/${editing.id}`, payload)
        : apiPost<Product>("/products", payload);
    },
    onSuccess: (product) => {
      toast.success(editing ? `Produk ${product.name} diperbarui` : `Produk ${product.name} ditambahkan`);
      setDialogOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (product: Product) => apiDelete(`/products/${product.id}`),
    onSuccess: () => {
      toast.success("Produk dihapus");
      setDeleting(null);
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(p: Product) {
    setEditing(p);
    setForm({
      tax: p.tax == null ? '' : String(p.tax),
      category: p.category || (p.type === 'jasa' ? 'SERVICE' : 'TIRE'),
      type: p.type,
      sku: p.sku,
      name: p.name,
      brand: p.brand,
      size: p.size,
      owner: p.owner ?? '',
      stock: String(p.stock),
      cost_price: String(p.cost_price),
      selling_price: String(p.selling_price),
      service_fee: String(p.service_fee),
    });
    setDialogOpen(true);
  }

  const allProducts = productsQuery.data ?? [];
  const products = allProducts.filter((p) =>
    (ownerFilter === "all" || p.owner === ownerFilter) &&
    [p.name, p.sku, p.brand, p.size].join(" ").toLowerCase().includes(search.trim().toLowerCase())
  );
  const filtersActive = !!search.trim() || ownerFilter !== "all" || !!taxFilter || !!categoryFilter;

  return (
    <div className="page-workspace">
      <div className="page-heading">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Produk</h1>
          <p className="text-sm text-muted-foreground">Stok, harga jual, dan modal barang serta jasa bengkel.</p>
        </div>
        <Button data-testid="product-add-button" onClick={openCreate}>
          <Plus className="size-4" /> Tambah produk
        </Button>
      </div>

      <div className="page-toolbar">
        <div className="relative min-w-0 flex-1 sm:min-w-64">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input aria-label="Cari produk" data-testid="product-search-input" className="pl-10" value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari nama, SKU, merek, atau ukuran" />
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <select data-testid="product-tax-filter" aria-label="Filter TAX produk" className="bk-control w-auto" value={taxFilter} onChange={e => setTaxFilter(e.target.value)}>
            <option value="">Semua TAX</option><option value="1">TAX = 1</option><option value="0">TAX = 0</option><option value="unassigned">TAX belum ditandai</option>
          </select>
          <select data-testid="product-category-filter" aria-label="Filter kategori produk" className="bk-control w-auto" value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
            <option value="">Semua kategori</option><option value="TIRE">Ban</option><option value="OIL">Oli</option><option value="SERVICE">Servis</option><option value="COMPLEMENTARY">Pelengkap</option>
          </select>
          <select
            data-testid="product-owner-filter"
            aria-label="Filter pemilik produk"
            className="bk-control w-auto"
            value={ownerFilter}
            onChange={(e) => setOwnerFilter(e.target.value as "all" | ProductOwner)}
          >
            <option value="all">Semua Pemilik</option>
            <option value="bian">Barang Bian</option>
            <option value="ibu">Barang Ibu (Mamah Bian)</option>{(["non", "polosan", "non vpt", "non vat"] as const).map(o => <option key={o} value={o}>{OWNER_LABEL[o]}</option>)}
          </select>
        </div>
      </div>

      {productsQuery.isPending ? (
        <LoadingBlock />
      ) : productsQuery.isError ? (
        <ErrorBlock error={productsQuery.error} onRetry={() => void productsQuery.refetch()} />
      ) : products.length === 0 ? (
        <EmptyBlock title={filtersActive ? "Produk tidak ditemukan" : "Belum ada produk"} description={filtersActive ? "Ubah kata pencarian atau filter untuk melihat produk lainnya." : "Pilih Tambah produk untuk mencatat barang atau jasa bengkel."} />
      ) : (
        <div className="data-panel" data-testid="products-table">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Daftar produk</h2>
            <span className="text-sm text-muted-foreground" data-testid="products-visible-count">{products.length} produk ditampilkan</span>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Produk</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Jenis</TableHead>
                <TableHead>Pemilik</TableHead>
                <TableHead>TAX</TableHead>
                <TableHead>Merek / Ukuran</TableHead>
                <TableHead className="text-right">Stok</TableHead>
                <TableHead className="text-right">Modal</TableHead>
                <TableHead className="text-right">Harga Jual</TableHead>
                <TableHead className="text-right">Komisi</TableHead>
                <TableHead className="text-right">Aksi</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="min-w-44 max-w-64 whitespace-normal text-sm font-semibold">{p.name}</TableCell>
                  <TableCell className="font-mono text-xs">{p.sku}</TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className="rounded-sm border-border text-foreground"
                    >
                      {p.type === "jasa" ? "Jasa" : "Barang"}
                    </Badge>
                  </TableCell>
                  <TableCell data-testid={`product-owner-${p.sku.toLowerCase()}`}>
                    {p.owner ? (
                      <span className="text-xs text-muted-foreground">
                        {OWNER_LABEL[p.owner]}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">Belum dipetakan</span>
                    )}
                  </TableCell>
                  <TableCell>{p.tax == null ? 'Belum ditandai' : p.tax}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{[p.brand, p.size].filter(Boolean).join(" · ") || "-"}</TableCell>
                  <TableCell
                    className={cn("text-right font-mono text-sm", p.type === "barang" && p.stock <= 4 && "font-bold text-red-700 dark:text-red-400")}
                  >
                    {p.type === "barang" ? p.stock : "-"}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">{formatIDR(p.cost_price)}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{formatIDR(p.selling_price)}</TableCell>
                  <TableCell className="text-right font-mono text-xs">{formatIDR(p.service_fee)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`product-edit-btn-${p.sku.toLowerCase()}`}
                        title="Edit"
                        aria-label={`Edit produk ${p.name}`}
                        onClick={() => openEdit(p)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`product-delete-btn-${p.sku.toLowerCase()}`}
                        title="Hapus"
                        aria-label={`Hapus produk ${p.name}`}
                        onClick={() => setDeleting(p)}
                      >
                        <Trash2 className="text-red-700 dark:text-red-400" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" data-testid="product-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Produk" : "Tambah Produk"}</DialogTitle>
            <DialogDescription>
              Laba dan komisi mengikuti kategori serta rumus Excel. Modal jasa dan pelengkap tetap dicatat.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <h3 className="col-span-full border-b border-border pb-2 text-sm font-semibold">Identitas dan kategori</h3>
            <div className="col-span-full space-y-2">
              <Label htmlFor="product-tax">Atribut TAX</Label>
              <select id="product-tax" className="bk-control" value={form.tax} onChange={e => set('tax', e.target.value)}>
                {form.tax === '' && <option value="">Belum ditandai</option>}
                <option value="0">0: Tidak masuk perhitungan pajak</option><option value="1">1: Masuk perhitungan pajak laporan</option>
              </select>
              <p className="text-xs text-muted-foreground">Berlaku untuk transaksi berikutnya. Tidak menambah harga atau mengubah pajak transaksi lama.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-form-type">Jenis</Label>
              <Select value={form.type} onValueChange={(v) => setForm(f => ({ ...f, type: v as ProductType, category: v === 'jasa' ? 'SERVICE' : 'TIRE' }))}>
                <SelectTrigger id="product-form-type" className="w-full" data-testid="product-form-type-select">
                  <SelectValue>{(v) => (v === "jasa" ? "Jasa Servis" : "Barang")}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="barang">Barang</SelectItem>
                  <SelectItem value="jasa">Jasa Servis</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-form-sku">SKU</Label>
              <Input
                id="product-form-sku"
                data-testid="product-form-sku-input"
                value={form.sku}
                onChange={(e) => set("sku", e.target.value)}
                placeholder="Kode produk"
              />
            </div>
            <div className="col-span-full space-y-2">
              <Label htmlFor="product-category" data-testid="product-category-label">Kategori laporan Excel</Label>
              <select id="product-category" data-testid="product-category-select" className="bk-control" value={form.category} onChange={e => set('category', e.target.value as Product['category'])}>
                <option value="TIRE">Ban / Tire</option><option value="OIL">Oli / Oil</option><option value="SERVICE">Service / Spooring</option><option value="COMPLEMENTARY">Pelengkap / Complementary</option>
              </select>
            </div>
            <div className="col-span-full space-y-2">
              <Label htmlFor="product-owner" data-testid="product-owner-label">Pemilik barang</Label>
              <select id="product-owner" data-testid="product-form-owner-select" className="bk-control" value={form.owner} onChange={e => set('owner', e.target.value as ProductOwner)}>
                {form.owner === '' && <option value="">Belum dipetakan</option>}
                <option value="bian">{OWNER_LABEL.bian}</option>
                <option value="ibu">{OWNER_LABEL.ibu}</option>
                {(["non", "polosan", "non vpt", "non vat"] as const).map(o => <option key={o} value={o}>{OWNER_LABEL[o]}</option>)}
              </select>
            </div>
            <div className="col-span-full space-y-2">
              <Label htmlFor="product-form-name">Nama</Label>
              <Input
                id="product-form-name"
                data-testid="product-form-name-input"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="Nama barang atau jasa"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-form-brand">Merek</Label>
              <Input id="product-form-brand" data-testid="product-form-brand-input" value={form.brand} onChange={(e) => set("brand", e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-form-size">Ukuran</Label>
              <Input id="product-form-size" data-testid="product-form-size-input" value={form.size} onChange={(e) => set("size", e.target.value)} placeholder="Ukuran barang" />
            </div>
            <h3 className="col-span-full mt-2 border-b border-border pb-2 text-sm font-semibold">Stok dan harga</h3>
            {form.type === "barang" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="product-form-stock">Jumlah stok</Label>
                  <Input id="product-form-stock" data-testid="product-form-stock-input" type="number" min={0} value={form.stock} onChange={(e) => set("stock", e.target.value)} />
                </div>
              </>
            ) : null}
              <div className="space-y-2">
                <Label htmlFor="product-form-cost">Modal (Rp)</Label>
                <Input id="product-form-cost" data-testid="product-form-cost-input" type="number" min={0} value={form.cost_price} onChange={(e) => set("cost_price", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="product-form-fee">Komisi mekanik per unit (Rp)</Label>
                <Input id="product-form-fee" data-testid="product-form-fee-input" type="number" min={0} value={form.service_fee} onChange={(e) => set("service_fee", e.target.value)} />
              </div>
            <div className="space-y-2">
              <Label htmlFor="product-form-price">Harga Jual (Rp)</Label>
              <Input id="product-form-price" data-testid="product-form-price-input" type="number" min={0} value={form.selling_price} onChange={(e) => set("selling_price", e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" data-testid="product-form-cancel-button" onClick={() => setDialogOpen(false)}>
              Batal
            </Button>
            <Button
              data-testid="product-form-submit-button"
              disabled={saveMutation.isPending || !form.sku.trim() || !form.name.trim() || form.selling_price === ""}
              onClick={() => saveMutation.mutate()}
            >
              {saveMutation.isPending ? "Menyimpan…" : "Simpan produk"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent className="sm:max-w-md" data-testid="product-delete-dialog">
          <DialogHeader>
            <DialogTitle>Hapus produk {deleting?.name}?</DialogTitle>
            <DialogDescription>Riwayat transaksi lama tetap tersimpan dengan snapshot data produk.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" data-testid="product-delete-cancel-button" onClick={() => setDeleting(null)}>
              Batal
            </Button>
            <Button
              variant="destructive"
              data-testid="product-delete-confirm-button"
              disabled={deleteMutation.isPending}
              onClick={() => deleting && deleteMutation.mutate(deleting)}
            >
              {deleteMutation.isPending ? "Menghapus…" : "Hapus"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
