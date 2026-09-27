import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { DebtStatusBadge } from "@/components/StatusBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, apiPost } from "@/lib/api";
import { formatDate, formatIDR, getApiErrorMessage, todayLocalISO } from "@/lib/format";
import type { AccountsPayable, AccountsReceivable, Supplier } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function DebtPage() {
  const queryClient = useQueryClient();
  const [addPayableOpen, setAddPayableOpen] = useState(false);
  const [form, setForm] = useState({ supplier_id: "", invoice_number: "", amount: "", due_date: "" });

  const receivablesQuery = useQuery({ queryKey: ["receivables"], queryFn: () => apiGet<AccountsReceivable[]>("/receivables") });
  const payablesQuery = useQuery({ queryKey: ["payables"], queryFn: () => apiGet<AccountsPayable[]>("/payables") });
  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<Supplier[]>("/suppliers") });

  function invalidateDebts() {
    void queryClient.invalidateQueries({ queryKey: ["receivables"] });
    void queryClient.invalidateQueries({ queryKey: ["payables"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  }

  const payReceivableMutation = useMutation({
    mutationFn: (id: string) => apiPost<AccountsReceivable>(`/receivables/${id}/pay`),
    onSuccess: () => {
      toast.success("Piutang ditandai lunas");
      invalidateDebts();
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const payPayableMutation = useMutation({
    mutationFn: (id: string) => apiPost<AccountsPayable>(`/payables/${id}/pay`),
    onSuccess: () => {
      toast.success("Hutang ditandai lunas");
      invalidateDebts();
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const createPayableMutation = useMutation({
    mutationFn: () =>
      apiPost<AccountsPayable>("/payables", {
        supplier_id: form.supplier_id,
        invoice_number: form.invoice_number.trim(),
        amount: Number(form.amount || 0),
        due_date: form.due_date,
      }),
    onSuccess: () => {
      toast.success("Hutang distributor dicatat");
      setAddPayableOpen(false);
      setForm({ supplier_id: "", invoice_number: "", amount: "", due_date: "" });
      invalidateDebts();
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const receivables = receivablesQuery.data ?? [];
  const payables = payablesQuery.data ?? [];
  const formValid = form.supplier_id !== "" && form.invoice_number.trim() !== "" && form.amount !== "" && form.due_date !== "";

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Piutang &amp; Hutang</h1>
          <p className="text-sm text-muted-foreground">
            Piutang dibuat otomatis dari checkout tempo; hutang distributor dicatat manual.
          </p>
        </div>
      </div>

      <Tabs defaultValue="piutang">
        <TabsList data-testid="debt-tabs">
          <TabsTrigger value="piutang" data-testid="tab-receivables">Piutang Pelanggan</TabsTrigger>
          <TabsTrigger value="hutang" data-testid="tab-payables">Hutang Distributor</TabsTrigger>
        </TabsList>

        {/* ===== Piutang ===== */}
        <TabsContent value="piutang" className="mt-4">
          {receivablesQuery.isPending ? (
            <LoadingBlock />
          ) : receivablesQuery.isError ? (
            <ErrorBlock error={receivablesQuery.error} onRetry={() => void receivablesQuery.refetch()} />
          ) : receivables.length === 0 ? (
            <EmptyBlock title="Belum ada piutang" description="Piutang muncul otomatis saat ada penjualan tempo." />
          ) : (
            <div className="rounded-xl border border-border bg-card" data-testid="receivables-table">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Pelanggan</TableHead>
                    <TableHead className="text-right">Jumlah</TableHead>
                    <TableHead>Jatuh Tempo</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Aksi</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {receivables.map((r) => {
                    const overdue = r.status === "unpaid" && r.due_date < todayLocalISO();
                    return (
                      <TableRow key={r.id} data-testid={`receivable-row-${r.invoice_number.toLowerCase()}`} className={cn(overdue && "bg-red-500/5")}>
                        <TableCell className="font-mono text-xs">{r.invoice_number}</TableCell>
                        <TableCell className="text-sm">{r.customer_name}</TableCell>
                        <TableCell className="text-right font-mono text-sm">{formatIDR(r.amount)}</TableCell>
                        <TableCell className="text-sm">{formatDate(r.due_date)}</TableCell>
                        <TableCell><DebtStatusBadge status={r.status} dueDate={r.due_date} /></TableCell>
                        <TableCell className="text-right">
                          {r.status === "unpaid" ? (
                            <Button
                              size="xs"
                              variant="outline"
                              data-testid={`pay-receivable-btn-${r.invoice_number.toLowerCase()}`}
                              disabled={payReceivableMutation.isPending}
                              onClick={() => payReceivableMutation.mutate(r.id)}
                            >
                              Tandai Lunas
                            </Button>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* ===== Hutang ===== */}
        <TabsContent value="hutang" className="mt-4">
          <div className="mb-3 flex justify-end">
            <Button data-testid="add-payable-button" onClick={() => setAddPayableOpen(true)}>
              <Plus className="size-4" /> Catat Hutang
            </Button>
          </div>
          {payablesQuery.isPending ? (
            <LoadingBlock />
          ) : payablesQuery.isError ? (
            <ErrorBlock error={payablesQuery.error} onRetry={() => void payablesQuery.refetch()} />
          ) : payables.length === 0 ? (
            <EmptyBlock title="Belum ada hutang" description="Catat hutang distributor dengan tombol Catat Hutang." />
          ) : (
            <div className="rounded-xl border border-border bg-card" data-testid="payables-table">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Distributor</TableHead>
                    <TableHead className="text-right">Jumlah</TableHead>
                    <TableHead>Jatuh Tempo</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Aksi</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payables.map((p) => (
                    <TableRow key={p.id} data-testid={`payable-row-${p.invoice_number.toLowerCase()}`}>
                      <TableCell className="font-mono text-xs">{p.invoice_number}</TableCell>
                      <TableCell className="text-sm">{p.supplier_name}</TableCell>
                      <TableCell className="text-right font-mono text-sm">{formatIDR(p.amount)}</TableCell>
                      <TableCell className="text-sm">{formatDate(p.due_date)}</TableCell>
                      <TableCell><DebtStatusBadge status={p.status} dueDate={p.due_date} /></TableCell>
                      <TableCell className="text-right">
                        {p.status === "unpaid" ? (
                          <Button
                            size="xs"
                            variant="outline"
                            data-testid={`pay-payable-btn-${p.invoice_number.toLowerCase()}`}
                            disabled={payPayableMutation.isPending}
                            onClick={() => payPayableMutation.mutate(p.id)}
                          >
                            Tandai Lunas
                          </Button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Dialog catat hutang */}
      <Dialog open={addPayableOpen} onOpenChange={setAddPayableOpen}>
        <DialogContent className="sm:max-w-md" data-testid="payable-form-dialog">
          <DialogHeader>
            <DialogTitle>Catat Hutang Distributor</DialogTitle>
            <DialogDescription>Rekam invoice hutang beserta tanggal jatuh temponya.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Distributor</Label>
              <Select
                value={form.supplier_id || "none"}
                onValueChange={(v) => setForm((f) => ({ ...f, supplier_id: v === "none" ? "" : v }))}
              >
                <SelectTrigger data-testid="payable-form-supplier-select">
                  <SelectValue>
                    {(v) => {
                      const val = v as string;
                      if (val === "none") return "— Pilih Distributor —";
                      return (suppliersQuery.data ?? []).find((s) => s.id === val)?.name ?? "— Pilih Distributor —";
                    }}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— Pilih Distributor —</SelectItem>
                  {(suppliersQuery.data ?? []).map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="payable-form-invoice">No. Invoice</Label>
              <Input
                id="payable-form-invoice"
                data-testid="payable-form-invoice-input"
                value={form.invoice_number}
                onChange={(e) => setForm((f) => ({ ...f, invoice_number: e.target.value }))}
                placeholder="mis. GT/PO/2601"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="payable-form-amount">Jumlah (Rp)</Label>
                <Input
                  id="payable-form-amount"
                  data-testid="payable-form-amount-input"
                  type="number"
                  min={0}
                  value={form.amount}
                  onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="payable-form-due">Jatuh Tempo</Label>
                <Input
                  id="payable-form-due"
                  data-testid="payable-form-due-input"
                  type="date"
                  min={todayLocalISO()}
                  value={form.due_date}
                  onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" data-testid="payable-form-cancel-button" onClick={() => setAddPayableOpen(false)}>
              Batal
            </Button>
            <Button
              data-testid="payable-form-submit-button"
              disabled={!formValid || createPayableMutation.isPending}
              onClick={() => createPayableMutation.mutate()}
            >
              {createPayableMutation.isPending ? "Menyimpan…" : "Simpan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
