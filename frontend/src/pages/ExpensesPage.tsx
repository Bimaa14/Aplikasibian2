import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "@/components/StateBlock";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import { formatDate, formatIDR, getApiErrorMessage, todayLocalISO } from "@/lib/format";
import type { Expense } from "@/lib/types";

const CATEGORIES = ["Gaji Montir", "Gaji Karyawan", "Pajak", "Operasional", "Cicilan Mesin", "Sewa Tempat", "Bengkel", "Lainnya"];

export default function ExpensesPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ date: todayLocalISO(), amount: "", category: "Operasional", description: "", payment_source: "Cashier" });

  const expensesQuery = useQuery({ queryKey: ["expenses"], queryFn: () => apiGet<Expense[]>("/expenses") });

  const createMutation = useMutation({
    mutationFn: () =>
      apiPost<Expense>("/expenses", {
        date: form.date || undefined,
        amount: Number(form.amount || 0),
        category: form.category,
        description: form.description.trim(),
        payment_source: form.payment_source,
      }),
    onSuccess: () => {
      toast.success("Pengeluaran dicatat");
      setForm((f) => ({ ...f, amount: "", description: "" }));
      void queryClient.invalidateQueries({ queryKey: ["expenses"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiDelete(`/expenses/${id}`),
    onSuccess: () => {
      toast.success("Pengeluaran dihapus");
      void queryClient.invalidateQueries({ queryKey: ["expenses"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const expenses = expensesQuery.data ?? [];
  const total = expenses.reduce((sum, e) => sum + e.amount, 0);

  return (
    <div className="page-workspace space-y-5">
      <div className="page-heading">
        <div className="min-w-0">
        <h1 data-testid="expenses-page-title" className="font-heading text-2xl font-bold tracking-tight">Pengeluaran</h1>
        <p className="text-sm text-muted-foreground">
          Pengeluaran mengurangi laba bersih di dashboard (gaji montir, operasional, sewa, dll).
        </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        {/* Form catat pengeluaran */}
        <Card className="min-w-0 self-start xl:col-span-4">
          <CardHeader>
            <CardTitle className="font-heading text-base">Catat Pengeluaran</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1" onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }}>
            <div className="space-y-2">
              <Label htmlFor="expense-form-date">Tanggal</Label>
              <Input
                id="expense-form-date"
                data-testid="expense-form-date-input"
                type="date"
                value={form.date}
                onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="expense-form-amount">Jumlah (Rp)</Label>
              <Input
                id="expense-form-amount"
                data-testid="expense-form-amount-input"
                type="number"
                min={0}
                required
                value={form.amount}
                onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                placeholder="mis. 450000"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="expense-form-category">Kategori</Label>
              <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
                <SelectTrigger id="expense-form-category" data-testid="expense-form-category-select">
                  <SelectValue>{form.category}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="expense-form-payment-source">Sumber pembayaran</Label>
              <Select value={form.payment_source} onValueChange={(v) => setForm((f) => ({ ...f, payment_source: v }))}>
                <SelectTrigger id="expense-form-payment-source" data-testid="expense-form-payment-source-select">
                  <SelectValue>{form.payment_source === 'Cashier' ? 'Kasir (Cashier)' : 'IBU'}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Cashier">Kasir (Cashier)</SelectItem>
                  <SelectItem value="IBU">IBU</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">Kas harian dikurangi hanya jika dibayar dari kasir. Semua pengeluaran masuk laporan bulanan.</p>
            </div>
            <div className="space-y-2 sm:col-span-2 xl:col-span-1">
              <Label htmlFor="expense-form-description">Keterangan</Label>
              <Textarea
                id="expense-form-description"
                data-testid="expense-form-description-input"
                rows={3}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="mis. Gaji 3 montir bulan ini"
              />
            </div>
            <Button
              className="w-full sm:col-span-2 xl:col-span-1"
              data-testid="expense-submit-button"
              type="submit"
              disabled={createMutation.isPending || form.amount === "" || !Number.isFinite(Number(form.amount)) || Number(form.amount) < 0}
            >
              {createMutation.isPending ? "Menyimpan…" : "Simpan Pengeluaran"}
            </Button>
            </form>
          </CardContent>
        </Card>

        {/* Tabel pengeluaran */}
        <div className="min-w-0 xl:col-span-8">
          {expensesQuery.isPending ? (
            <LoadingBlock />
          ) : expensesQuery.isError ? (
            <ErrorBlock error={expensesQuery.error} onRetry={() => void expensesQuery.refetch()} />
          ) : expenses.length === 0 ? (
            <EmptyBlock title="Belum ada pengeluaran" description="Isi formulir catat pengeluaran untuk menyimpan pengeluaran pertama." />
          ) : (
            <div className="data-table-panel bk-panel" data-testid="expenses-table">
              <div className="section-heading flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
                <div><h2 className="font-heading text-base font-semibold">Riwayat pengeluaran</h2><p className="text-sm text-muted-foreground">{expenses.length} catatan tersimpan</p></div>
                <div className="text-right"><p className="text-xs text-muted-foreground">Total pengeluaran</p><strong className="font-mono text-lg">{formatIDR(total)}</strong></div>
              </div>
              <Table className="min-w-[43rem]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Tanggal</TableHead>
                    <TableHead>Kategori</TableHead>
                    <TableHead>Keterangan</TableHead>
                    <TableHead>Dibayar dari</TableHead>
                    <TableHead className="text-right">Jumlah</TableHead>
                    <TableHead className="text-right">Aksi</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {expenses.map((e) => (
                    <TableRow key={e.id} data-testid={`expense-row-${e.id.slice(0, 8)}`}>
                      <TableCell className="text-sm">{formatDate(e.date)}</TableCell>
                      <TableCell>
                        <span className="text-sm font-medium">
                          {e.category}
                        </span>
                      </TableCell>
                      <TableCell className="min-w-40 whitespace-normal text-sm text-muted-foreground">{e.description || "-"}</TableCell>
                      <TableCell className="text-sm">{e.payment_source ?? 'Cashier'}</TableCell>
                      <TableCell className="text-right font-mono text-sm text-red-700 dark:text-red-400">-{formatIDR(e.amount)}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          data-testid={`expense-delete-btn-${e.id.slice(0, 8)}`}
                          title="Hapus"
                          aria-label={`Hapus pengeluaran ${e.category} ${formatDate(e.date)}`}
                          onClick={() => deleteMutation.mutate(e.id)}
                        >
                          <Trash2 className="text-red-700 dark:text-red-400" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex justify-between border-t border-border px-4 py-3 text-sm">
                <span className="font-semibold">Total Pengeluaran</span>
                <span className="font-mono font-bold" data-testid="expenses-total">
                  {formatIDR(total)}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
