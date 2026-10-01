import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
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

  const customers = customersQuery.data ?? [];

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Pelanggan</h1>
          <p className="text-sm text-muted-foreground">Data pelanggan untuk transaksi tunai maupun tempo (kredit).</p>
        </div>
        <Button data-testid="customer-add-button" onClick={openCreate}>
          <Plus className="size-4" /> Tambah Pelanggan
        </Button>
      </div>

      {customersQuery.isPending ? (
        <LoadingBlock />
      ) : customersQuery.isError ? (
        <ErrorBlock error={customersQuery.error} onRetry={() => void customersQuery.refetch()} />
      ) : customers.length === 0 ? (
        <EmptyBlock title="Belum ada pelanggan" description="Tambahkan pelanggan pertama Anda." />
      ) : (
        <div className="rounded-xl border border-border bg-card" data-testid="customers-table">
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
                  <TableCell className="text-sm font-medium">{c.name}</TableCell>
                  <TableCell className="font-mono text-xs">{c.phone || "-"}</TableCell>
                  <TableCell className="max-w-72 truncate text-xs text-muted-foreground">{c.address || "-"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`customer-edit-btn-${c.id.slice(0, 8)}`}
                        title="Edit"
                        onClick={() => openEdit(c)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`customer-delete-btn-${c.id.slice(0, 8)}`}
                        title="Hapus"
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
        <DialogContent className="sm:max-w-md" data-testid="customer-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Pelanggan" : "Tambah Pelanggan"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="customer-form-name">Nama</Label>
              <Input id="customer-form-name" data-testid="customer-form-name-input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="customer-form-phone">Telepon</Label>
              <Input id="customer-form-phone" data-testid="customer-form-phone-input" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} placeholder="08…" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="customer-form-address">Alamat</Label>
              <Textarea id="customer-form-address" data-testid="customer-form-address-input" value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} rows={2} />
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
              {saveMutation.isPending ? "Menyimpan…" : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent className="sm:max-w-md" data-testid="customer-delete-dialog">
          <DialogHeader>
            <DialogTitle>Hapus pelanggan {deleting?.name}?</DialogTitle>
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
