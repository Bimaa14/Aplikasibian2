import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import type { Customer } from "@/lib/types";

type CustomerForm = { name: string; phone: string; address: string };
const EMPTY_FORM: CustomerForm = { name: "", phone: "", address: "" };

export default function CustomersPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerForm>(EMPTY_FORM);
  const [search, setSearch] = useState("");

  const customersQuery = useQuery({ queryKey: ["customers"], queryFn: () => apiGet<Customer[]>("/customers") });

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = { name: form.name.trim(), phone: form.phone.trim(), address: form.address.trim() };
      return editing
        ? apiPut<Customer>(`/customers/${editing.id}`, payload)
        : apiPost<Customer>("/customers", payload);
    },
    onSuccess: (customer) => {
      toast.success(editing ? `Pelanggan ${customer.name} diperbarui` : `Pelanggan ${customer.name} ditambahkan`);
      setDialogOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (customer: Customer) => apiDelete(`/customers/${customer.id}`),
    onSuccess: () => {
      toast.success("Pelanggan dihapus");
      setDeleting(null);
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }
  function openEdit(c: Customer) {
    setEditing(c);
    setForm({ name: c.name, phone: c.phone, address: c.address });
    setDialogOpen(true);
  }

  const allCustomers = customersQuery.data ?? [];
  const customers = allCustomers.filter(c => [c.name, c.phone, c.address].join(" ").toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <div className="page-workspace">
      <div className="page-heading">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Pelanggan</h1>
          <p className="text-sm text-muted-foreground">Kontak pelanggan untuk nota penjualan dan transaksi tempo.</p>
        </div>
        <Button data-testid="customer-add-button" onClick={openCreate}>
          <Plus className="size-4" /> Tambah pelanggan
        </Button>
      </div>

      <div className="page-toolbar">
        <div className="relative min-w-0 w-full sm:max-w-md">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input aria-label="Cari pelanggan" data-testid="customer-search-input" className="pl-10" value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari nama, telepon, atau alamat" />
        </div>
        {!customersQuery.isPending && !customersQuery.isError && <span className="text-sm text-muted-foreground" data-testid="customers-visible-count">{customers.length} pelanggan ditampilkan</span>}
      </div>

      {customersQuery.isPending ? (
        <LoadingBlock />
      ) : customersQuery.isError ? (
        <ErrorBlock error={customersQuery.error} onRetry={() => void customersQuery.refetch()} />
      ) : customers.length === 0 ? (
        <EmptyBlock title={allCustomers.length ? "Pelanggan tidak ditemukan" : "Belum ada pelanggan"} description={allCustomers.length ? "Ubah kata pencarian untuk melihat pelanggan lainnya." : "Pilih Tambah pelanggan untuk menyimpan kontak pelanggan."} />
      ) : (
        <div className="data-panel" data-testid="customers-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nama</TableHead>
                <TableHead>Telepon</TableHead>
                <TableHead>Alamat</TableHead>
                <TableHead className="text-right">Aksi</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {customers.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="min-w-40 whitespace-normal text-sm font-semibold">{c.name}</TableCell>
                  <TableCell className="font-mono text-xs">{c.phone || "-"}</TableCell>
                  <TableCell className="min-w-44 max-w-80 whitespace-normal text-sm text-muted-foreground">{c.address || "-"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`customer-edit-btn-${c.id.slice(0, 8)}`}
                        title="Edit"
                        aria-label={`Edit pelanggan ${c.name}`}
                        onClick={() => openEdit(c)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`customer-delete-btn-${c.id.slice(0, 8)}`}
                        title="Hapus"
                        aria-label={`Hapus pelanggan ${c.name}`}
                        onClick={() => setDeleting(c)}
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
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" data-testid="customer-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Pelanggan" : "Tambah Pelanggan"}</DialogTitle>
            <DialogDescription>Nama pelanggan wajib diisi. Telepon dan alamat dapat dilengkapi nanti.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="customer-form-name">Nama pelanggan</Label>
              <Input id="customer-form-name" data-testid="customer-form-name-input" autoComplete="name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="customer-form-phone">Telepon</Label>
              <Input id="customer-form-phone" data-testid="customer-form-phone-input" type="tel" autoComplete="tel" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} placeholder="Nomor telepon pelanggan" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="customer-form-address">Alamat</Label>
              <Textarea id="customer-form-address" data-testid="customer-form-address-input" autoComplete="street-address" value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} rows={3} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" data-testid="customer-form-cancel-button" onClick={() => setDialogOpen(false)}>
              Batal
            </Button>
            <Button
              data-testid="customer-form-submit-button"
              disabled={saveMutation.isPending || !form.name.trim()}
              onClick={() => saveMutation.mutate()}
            >
              {saveMutation.isPending ? "Menyimpan…" : "Simpan pelanggan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent className="sm:max-w-md" data-testid="customer-delete-dialog">
          <DialogHeader>
            <DialogTitle>Hapus pelanggan {deleting?.name}?</DialogTitle>
            <DialogDescription>Periksa nama pelanggan sebelum melanjutkan penghapusan.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" data-testid="customer-delete-cancel-button" onClick={() => setDeleting(null)}>
              Batal
            </Button>
            <Button
              variant="destructive"
              data-testid="customer-delete-confirm-button"
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
