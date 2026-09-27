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

const CATEGORIES = ["Gaji Montir", "Operasional", "Sewa Tempat", "Bengkel", "Lainnya"];

export default function ExpensesPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ date: todayLocalISO(), amount: "", category: "Operasional", description: "" });

  const expensesQuery = useQuery({ queryKey: ["expenses"], queryFn: () => apiGet<Expense[]>("/expenses") });

  const createMutation = useMutation({
    mutationFn: () =>
      apiPost<Expense>("/expenses", {
        date: form.date || undefined,
        amount: Number(form.amount || 0),
        category: form.category,
        description: form.description.trim(),
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
    <div className="p-4 md:p-6">
      <div className="mb-4">
        <h1 className="font-heading text-2xl font-bold tracking-tight">Pengeluaran</h1>
        <p className="text-sm text-muted-foreground">
          Pengeluaran mengurangi laba bersih di dashboard (gaji montir, operasional, sewa, dll).
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        {/* Form catat pengeluaran */}
        <Card className="xl:col-span-4">
          <CardHeader>
            <CardTitle className="font-heading text-base">Catat Pengeluaran</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
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
                value={form.amount}
                onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                placeholder="mis. 450000"
              />
            </div>
            <div className="space-y-2">
              <Label>Kategori</Label>
              <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
                <SelectTrigger data-testid="expense-form-category-select">
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
              className="w-full"
              data-testid="expense-submit-button"
              disabled={createMutation.isPending || form.amount === ""}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? "Menyimpan…" : "Simpan Pengeluaran"}
            </Button>
          </CardContent>
        </Card>

        {/* Tabel pengeluaran */}
        <div className="xl:col-span-8">
          {expensesQuery.isPending ? (
            <LoadingBlock />
          ) : expensesQuery.isError ? (
            <ErrorBlock error={expensesQuery.error} onRetry={() => void expensesQuery.refetch()} />
          ) : expenses.length === 0 ? (
            <EmptyBlock title="Belum ada pengeluaran" description="Catat pengeluaran pertama Anda di form sebelah kiri." />
          ) : (
            <div className="rounded-xl border border-border bg-card" data-testid="expenses-table">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tanggal</TableHead>
                    <TableHead>Kategori</TableHead>
                    <TableHead>Keterangan</TableHead>
                    <TableHead className="text-right">Jumlah</TableHead>
                    <TableHead className="text-right">Aksi</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {expenses.map((e) => (
                    <TableRow key={e.id} data-testid={`expense-row-${e.id.slice(0, 8)}`}>
                      <TableCell className="text-sm">{formatDate(e.date)}</TableCell>
                      <TableCell>
                        <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-300">
                          {e.category}
                        </span>
                      </TableCell>
                      <TableCell className="max-w-64 truncate text-sm text-muted-foreground">{e.description || "-"}</TableCell>
                      <TableCell className="text-right font-mono text-sm text-red-400">-{formatIDR(e.amount)}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          data-testid={`expense-delete-btn-${e.id.slice(0, 8)}`}
                          title="Hapus"
                          onClick={() => deleteMutation.mutate(e.id)}
                        >
                          <Trash2 className="text-red-400" />
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
