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
import type { Supplier } from "@/lib/types";

type SupplierForm = { name: string; phone: string; address: string };
const EMPTY_FORM: SupplierForm = { name: "", phone: "", address: "" };

export default function SuppliersPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [deleting, setDeleting] = useState<Supplier | null>(null);
  const [form, setForm] = useState<SupplierForm>(EMPTY_FORM);

  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<Supplier[]>("/suppliers") });

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = { name: form.name.trim(), phone: form.phone.trim(), address: form.address.trim() };
      return editing
        ? apiPut<Supplier>(`/suppliers/${editing.id}`, payload)
        : apiPost<Supplier>("/suppliers", payload);
    },
    onSuccess: (supplier) => {
      toast.success(editing ? `Distributor ${supplier.name} diperbarui` : `Distributor ${supplier.name} ditambahkan`);
      setDialogOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (supplier: Supplier) => apiDelete(`/suppliers/${supplier.id}`),
    onSuccess: () => {
      toast.success("Distributor dihapus");
      setDeleting(null);
      void queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }
  function openEdit(s: Supplier) {
    setEditing(s);
    setForm({ name: s.name, phone: s.phone, address: s.address });
    setDialogOpen(true);
  }

  const suppliers = suppliersQuery.data ?? [];

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Distributor</h1>
          <p className="text-sm text-muted-foreground">Data distributor/supplier untuk pencatatan hutang.</p>
        </div>
        <Button data-testid="supplier-add-button" onClick={openCreate}>
          <Plus className="size-4" /> Tambah Distributor
        </Button>
      </div>

      {suppliersQuery.isPending ? (
        <LoadingBlock />
      ) : suppliersQuery.isError ? (
        <ErrorBlock error={suppliersQuery.error} onRetry={() => void suppliersQuery.refetch()} />
      ) : suppliers.length === 0 ? (
        <EmptyBlock title="Belum ada distributor" description="Tambahkan distributor pertama Anda." />
      ) : (
        <div className="rounded-xl border border-border bg-card" data-testid="suppliers-table">
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
              {suppliers.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="text-sm font-medium">{s.name}</TableCell>
                  <TableCell className="font-mono text-xs">{s.phone || "-"}</TableCell>
                  <TableCell className="max-w-72 truncate text-xs text-muted-foreground">{s.address || "-"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`supplier-edit-btn-${s.id.slice(0, 8)}`}
                        title="Edit"
                        onClick={() => openEdit(s)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        data-testid={`supplier-delete-btn-${s.id.slice(0, 8)}`}
                        title="Hapus"
                        onClick={() => setDeleting(s)}
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md" data-testid="supplier-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Distributor" : "Tambah Distributor"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="supplier-form-name">Nama</Label>
              <Input id="supplier-form-name" data-testid="supplier-form-name-input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="supplier-form-phone">Telepon</Label>
              <Input id="supplier-form-phone" data-testid="supplier-form-phone-input" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="supplier-form-address">Alamat</Label>
              <Textarea id="supplier-form-address" data-testid="supplier-form-address-input" value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" data-testid="supplier-form-cancel-button" onClick={() => setDialogOpen(false)}>
              Batal
            </Button>
            <Button
              data-testid="supplier-form-submit-button"
              disabled={saveMutation.isPending || !form.name.trim()}
              onClick={() => saveMutation.mutate()}
            >
              {saveMutation.isPending ? "Menyimpan…" : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <DialogContent className="sm:max-w-md" data-testid="supplier-delete-dialog">
          <DialogHeader>
            <DialogTitle>Hapus distributor {deleting?.name}?</DialogTitle>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" data-testid="supplier-delete-cancel-button" onClick={() => setDeleting(null)}>
              Batal
            </Button>
            <Button
              variant="destructive"
              data-testid="supplier-delete-confirm-button"
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
