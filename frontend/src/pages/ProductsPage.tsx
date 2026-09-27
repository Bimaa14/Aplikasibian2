import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
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
  category: Product['category'];
  type: ProductType;
  sku: string;
  name: string;
  brand: string;
  size: string;
  owner: ProductOwner;
  stock: string;
  cost_price: string;
  selling_price: string;
  service_fee: string;
};

const OWNER_LABEL: Record<ProductOwner, string> = {
  bian: "Barang Bian",
  ibu: "Barang Ibu (Mamah Bian)",
};

const EMPTY_FORM: ProductForm = {
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

  const productsQuery = useQuery({ queryKey: ["products"], queryFn: () => apiGet<Product[]>("/products") });

  const set = <K extends keyof ProductForm>(key: K, value: ProductForm[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        category: form.category,
        type: form.type,
        sku: form.sku.trim(),
        name: form.name.trim(),
        brand: form.brand.trim(),
        size: form.size.trim(),
        owner: form.owner,
        stock: form.type === "barang" ? Number(form.stock || 0) : 0,
        cost_price: form.type === "barang" ? Number(form.cost_price || 0) : 0,
        selling_price: Number(form.selling_price || 0),
        service_fee: form.type === "jasa" ? Number(form.service_fee || 0) : 0,
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
      category: p.category || (p.type === 'jasa' ? 'SERVICE' : 'TIRE'),
      type: p.type,
      sku: p.sku,
      name: p.name,
      brand: p.brand,
      size: p.size,
      owner: p.owner ?? "bian",
      stock: String(p.stock),
      cost_price: String(p.cost_price),
      selling_price: String(p.selling_price),
      service_fee: String(p.service_fee),
    });
    setDialogOpen(true);
  }

  const allProducts = productsQuery.data ?? [];
  const products = ownerFilter === "all" ? allProducts : allProducts.filter((p) => p.owner === ownerFilter);

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Produk</h1>
          <p className="text-sm text-muted-foreground">Data master barang (ban, oli, sparepart) dan jasa servis.</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            data-testid="product-owner-filter"
            className="bk-control h-9 w-auto"
            value={ownerFilter}
            onChange={(e) => setOwnerFilter(e.target.value as "all" | ProductOwner)}
          >
            <option value="all">Semua Pemilik</option>
            <option value="bian">Barang Bian</option>
            <option value="ibu">Barang Ibu (Mamah Bian)</option>
          </select>
          <Button data-testid="product-add-button" onClick={openCreate}>
            <Plus className="size-4" /> Tambah Produk
          </Button>
        </div>
      </div>

      {productsQuery.isPending ? (
        <LoadingBlock />
      ) : productsQuery.isError ? (
        <ErrorBlock error={productsQuery.error} onRetry={() => void productsQuery.refetch()} />
      ) : products.length === 0 ? (
        <EmptyBlock title="Belum ada produk" description="Tambahkan produk pertama Anda." />
      ) : (
        <div className="rounded-xl border border-border bg-card" data-testid="products-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Nama</TableHead>
                <TableHead>Jenis</TableHead>
                <TableHead>Pemilik</TableHead>
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
                  <TableCell className="font-mono text-xs">{p.sku}</TableCell>
                  <TableCell className="max-w-52 truncate text-sm font-medium">{p.name}</TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={cn(
                        "rounded-sm",
                        p.type === "jasa" ? "border-sky-500/30 text-sky-400" : "border-amber-500/30 text-amber-400"
                      )}
                    >
                      {p.type === "jasa" ? "Jasa" : "Barang"}
                    </Badge>
                  </TableCell>
                  <TableCell data-testid={`product-owner-${p.sku.toLowerCase()}`}>
                    {p.owner ? (
                      <Badge
                        variant="outline"
                        className={cn(
                          "rounded-sm",
                          p.owner === "ibu" ? "border-fuchsia-500/30 text-fuchsia-400" : "border-emerald-500/30 text-emerald-400"
                        )}
                      >
                        {p.owner === "ibu" ? "Ibu" : "Bian"}
                      </Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{[p.brand, p.size].filter(Boolean).join(" · ") || "-"}</TableCell>
                  <TableCell
                    className={cn("text-right font-mono text-sm", p.type === "barang" && p.stock <= 4 && "font-bold text-red-400")}
                  >
                    {p.type === "barang" ? p.stock : "-"}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">{p.type === "barang" ? formatIDR(p.cost_price) : "-"}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{formatIDR(p.selling_price)}</TableCell>
                  <TableCell className="text-right font-mono text-xs">{p.type === "jasa" ? formatIDR(p.service_fee) : "-"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`product-edit-btn-${p.sku.toLowerCase()}`}
                        title="Edit"
                        onClick={() => openEdit(p)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`product-delete-btn-${p.sku.toLowerCase()}`}
                        title="Hapus"
                        onClick={() => setDeleting(p)}
                      >
                        <Trash2 className="text-red-400" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialog form produk */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg" data-testid="product-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Produk" : "Tambah Produk"}</DialogTitle>
            <DialogDescription>
              Laba barang = harga jual − modal. Laba jasa = harga jual − komisi montir.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Jenis</Label>
              <Select value={form.type} onValueChange={(v) => setForm(f => ({ ...f, type: v as ProductType, category: v === 'jasa' ? 'SERVICE' : 'TIRE' }))}>
                <SelectTrigger data-testid="product-form-type-select">
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
                placeholder="mis. BAN-006"
              />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="product-category" data-testid="product-category-label">Kategori laporan Excel</Label>
              <select id="product-category" data-testid="product-category-select" className="bk-control" value={form.category} onChange={e => set('category', e.target.value as Product['category'])}>
                <option value="TIRE">Ban / Tire</option><option value="OIL">Oli / Oil</option><option value="SERVICE">Service / Spooring</option><option value="COMPLEMENTARY">Pelengkap / Complementary</option>
              </select>
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="product-owner" data-testid="product-owner-label">Pemilik barang</Label>
              <select id="product-owner" data-testid="product-form-owner-select" className="bk-control" value={form.owner} onChange={e => set('owner', e.target.value as ProductOwner)}>
                <option value="bian">{OWNER_LABEL.bian}</option>
                <option value="ibu">{OWNER_LABEL.ibu}</option>
              </select>
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="product-form-name">Nama</Label>
              <Input
                id="product-form-name"
                data-testid="product-form-name-input"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="mis. Ban Mobil GT Radial"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-form-brand">Merek</Label>
              <Input id="product-form-brand" data-testid="product-form-brand-input" value={form.brand} onChange={(e) => set("brand", e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-form-size">Ukuran</Label>
              <Input id="product-form-size" data-testid="product-form-size-input" value={form.size} onChange={(e) => set("size", e.target.value)} placeholder="mis. 185/65 R15" />
            </div>
            {form.type === "barang" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="product-form-stock">Stok</Label>
                  <Input id="product-form-stock" data-testid="product-form-stock-input" type="number" min={0} value={form.stock} onChange={(e) => set("stock", e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="product-form-cost">Modal (Rp)</Label>
                  <Input id="product-form-cost" data-testid="product-form-cost-input" type="number" min={0} value={form.cost_price} onChange={(e) => set("cost_price", e.target.value)} />
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="product-form-fee">Komisi Montir (Rp)</Label>
                <Input id="product-form-fee" data-testid="product-form-fee-input" type="number" min={0} value={form.service_fee} onChange={(e) => set("service_fee", e.target.value)} />
              </div>
            )}
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
              {saveMutation.isPending ? "Menyimpan…" : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog konfirmasi hapus */}
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
