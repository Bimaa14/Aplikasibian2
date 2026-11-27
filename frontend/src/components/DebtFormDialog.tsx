import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlock';
import { apiGet, apiPost, apiPut } from '@/lib/api';
import { formatIDR, getApiErrorMessage } from '@/lib/format';
import type { AccountsPayable, AccountsReceivable, Customer, Supplier } from '@/lib/types';

type DebtKind = 'receivables' | 'payables';
type DebtRow = AccountsPayable | AccountsReceivable;

interface DebtFormDialogProps {
  kind: DebtKind;
  mode: 'create' | 'edit';
  debt?: DebtRow | null;
  today: string;
  onClose: () => void;
  onSaved: () => void;
}

export function DebtFormDialog({ kind, mode, debt, today, onClose, onSaved }: DebtFormDialogProps) {
  const isReceivable = kind === 'receivables';
  const isEdit = mode === 'edit' && !!debt;
  const initialReceivable = isEdit && isReceivable && debt && 'customer_name' in debt ? debt : null;
  const initialPayable = isEdit && !isReceivable && debt && 'supplier_id' in debt ? debt : null;

  const [customerId, setCustomerId] = useState(initialReceivable?.customer_id || '');
  const [customerName, setCustomerName] = useState(initialReceivable?.customer_name || '');
  const [supplierId, setSupplierId] = useState(initialPayable?.supplier_id || '');
  const [invoiceNumber, setInvoiceNumber] = useState(debt?.invoice_number || '');
  const [amount, setAmount] = useState(debt ? String(debt.amount) : '');
  const [issuedDate, setIssuedDate] = useState(debt?.issued_date || today);
  const [dueDate, setDueDate] = useState(debt?.due_date || today);
  const [note, setNote] = useState(debt?.note || '');
  const [error, setError] = useState('');

  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: () => apiGet<Customer[]>('/customers'),
    enabled: isReceivable,
  });

  const suppliers = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => apiGet<Supplier[]>('/suppliers'),
    enabled: !isReceivable,
  });

  const minAmount = isEdit && debt ? Math.max(0.01, debt.paid_amount) : 0.01;
  const earliestPaymentDate =
    isEdit && debt?.payments?.length
      ? debt.payments.reduce((earliest, p) => (p.payment_date < earliest ? p.payment_date : earliest), debt.payments[0].payment_date)
      : undefined;

  const save = useMutation({
    mutationFn: async () => {
      const numericAmount = Number(amount);
      if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
        throw new Error('Nominal tagihan harus lebih dari 0.');
      }
      if (isEdit && debt && numericAmount < debt.paid_amount) {
        throw new Error(`Nominal tagihan tidak boleh lebih kecil dari total yang sudah dibayar (${formatIDR(debt.paid_amount)}).`);
      }

      if (isReceivable) {
        const payload = {
          customer_id: customerId || null,
          customer_name: customerId ? null : customerName.trim(),
          invoice_number: invoiceNumber.trim(),
          amount: numericAmount,
          issued_date: issuedDate || undefined,
          due_date: dueDate,
          note: note.trim(),
        };
        if (!payload.customer_id && !payload.customer_name) {
          throw new Error('Pilih pelanggan terdaftar atau isi nama pelanggan.');
        }
        return isEdit && debt
          ? apiPut(`/receivables/${debt.id}`, payload)
          : apiPost('/receivables', payload);
      }

      const payload = {
        supplier_id: supplierId,
        invoice_number: invoiceNumber.trim(),
        amount: numericAmount,
        issued_date: issuedDate || undefined,
        due_date: dueDate,
        note: note.trim(),
      };
      return isEdit && debt
        ? apiPut(`/payables/${debt.id}`, payload)
        : apiPost('/payables', payload);
    },
    onSuccess: () => {
      toast.success(
        isReceivable
          ? isEdit
            ? 'Data piutang diperbarui'
            : 'Piutang berhasil dicatat'
          : isEdit
            ? 'Data hutang diperbarui'
            : 'Hutang berhasil dicatat',
      );
      onSaved();
      onClose();
    },
    onError: (err) => {
      const msg = err instanceof Error && !('status' in err) ? err.message : getApiErrorMessage(err);
      setError(msg);
      toast.error(msg);
    },
  });

  const dialogTestId = isReceivable
    ? isEdit
      ? 'receivable-edit-dialog'
      : 'receivable-form-dialog'
    : isEdit
      ? 'payable-edit-dialog'
      : 'payable-form-dialog';

  const title = isReceivable
    ? isEdit
      ? 'Edit piutang pelanggan'
      : 'Catat piutang pelanggan'
    : isEdit
      ? 'Edit hutang distributor'
      : 'Catat hutang distributor';

  const description = isReceivable
    ? isEdit
      ? 'Perbarui pelanggan, nomor invoice, nominal, jatuh tempo, atau catatan piutang.'
      : 'Catat piutang manual atau saldo piutang lama di luar transaksi kasir.'
    : isEdit
      ? 'Perbarui distributor, nomor invoice, nominal, jatuh tempo, atau catatan hutang.'
      : 'Stok masuk sudah membuat hutang otomatis. Jangan catat invoice yang sama dua kali.';

  const hasMatchingCustomer = !customerId || (customers.data ?? []).some((c) => c.id === customerId);
  const hasMatchingSupplier = !supplierId || (suppliers.data ?? []).some((s) => s.id === supplierId);

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !save.isPending) onClose(); }}>
      <DialogContent data-testid={dialogTestId} className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {!isReceivable && suppliers.isPending ? (
          <div data-testid="payable-suppliers-loading">
            <LoadingBlock label="Memuat daftar distributor…" />
          </div>
        ) : !isReceivable && suppliers.isError ? (
          <div data-testid="payable-suppliers-error">
            <ErrorBlock error={suppliers.error} onRetry={() => void suppliers.refetch()} />
          </div>
        ) : !isReceivable && !suppliers.data?.length && !isEdit ? (
          <div data-testid="payable-suppliers-empty">
            <EmptyBlock
              title="Belum ada distributor"
              description="Tutup formulir ini lalu tambahkan distributor melalui menu Distributor sebelum mencatat hutang."
            />
          </div>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              setError('');
              save.mutate();
            }}
          >
            {isEdit && initialReceivable?.transaction_id && (
              <p className="bk-notice text-xs" data-testid="debt-edit-pos-notice">
                Tagihan ini terhubung dengan transaksi kasir. Perubahan memperbarui saldo piutang dan jatuh tempo tanpa mengubah nota barang aslinya.
              </p>
            )}

            {isEdit && debt && debt.paid_amount > 0 && (
              <p className="bk-notice text-xs" data-testid="debt-edit-paid-notice">
                Sudah dibayar <b>{formatIDR(debt.paid_amount)}</b>. Nominal tagihan minimal {formatIDR(debt.paid_amount)}.
              </p>
            )}

            {isReceivable ? (
              <div className="space-y-3">
                <label className="block text-sm">
                  Pelanggan terdaftar
                  <select
                    className="bk-control mt-1"
                    data-testid="receivable-form-customer-select"
                    aria-label="Pelanggan terdaftar"
                    value={customerId}
                    disabled={save.isPending}
                    onChange={(e) => {
                      const nextId = e.target.value;
                      setCustomerId(nextId);
                      const picked = customers.data?.find((c) => c.id === nextId);
                      if (picked) setCustomerName(picked.name);
                    }}
                  >
                    <option value="">Tulis nama pelanggan manual</option>
                    {!hasMatchingCustomer && initialReceivable && (
                      <option value={customerId}>{initialReceivable.customer_name || 'Pelanggan sebelumnya'}</option>
                    )}
                    {(customers.data ?? []).map((c) => (
                      <option value={c.id} key={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>

                {!customerId && (
                  <label className="block text-sm">
                    Nama pelanggan
                    <Input
                      className="mt-1"
                      data-testid="receivable-form-customer-name-input"
                      aria-label="Nama pelanggan"
                      placeholder="Masukkan nama pelanggan"
                      required
                      disabled={save.isPending}
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                    />
                  </label>
                )}
              </div>
            ) : (
              <label className="block text-sm">
                Distributor
                <select
                  className="bk-control mt-1"
                  data-testid="payable-form-supplier-select"
                  aria-label="Distributor"
                  required
                  disabled={save.isPending}
                  value={supplierId}
                  onChange={(e) => setSupplierId(e.target.value)}
                >
                  <option value="">Pilih distributor</option>
                  {!hasMatchingSupplier && initialPayable && (
                    <option value={supplierId}>{initialPayable.supplier_name || 'Distributor sebelumnya'}</option>
                  )}
                  {(suppliers.data ?? []).map((s) => (
                    <option value={s.id} key={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label className="block text-sm">
              Nomor invoice / nota
              <Input
                className="mt-1"
                data-testid={isReceivable ? 'receivable-form-invoice-input' : 'payable-form-invoice-input'}
                aria-label="Nomor invoice"
                placeholder={isReceivable ? 'Contoh: INV-PIUTANG-001' : 'Nomor invoice distributor'}
                required
                disabled={save.isPending}
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
              />
            </label>

            <label className="block text-sm">
              Nominal tagihan (Rp)
              <Input
                className="mt-1 font-mono"
                data-testid={isReceivable ? 'receivable-form-amount-input' : 'payable-form-amount-input'}
                aria-label={isReceivable ? 'Nominal piutang' : 'Nominal hutang'}
                type="number"
                min={minAmount}
                max="1000000000000"
                step="0.01"
                placeholder="Nominal (Rp)"
                required
                disabled={save.isPending}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                Tanggal tagihan
                <Input
                  className="mt-1"
                  data-testid={isReceivable ? 'receivable-form-issued-input' : 'payable-form-issued-input'}
                  type="date"
                  max={earliestPaymentDate}
                  required
                  disabled={save.isPending}
                  value={issuedDate}
                  onChange={(e) => setIssuedDate(e.target.value)}
                />
              </label>
              <label className="block text-sm">
                Jatuh tempo
                <Input
                  className="mt-1"
                  data-testid={isReceivable ? 'receivable-form-due-input' : 'payable-form-due-input'}
                  type="date"
                  required
                  disabled={save.isPending}
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                />
              </label>
            </div>

            <label className="block text-sm">
              Catatan (opsional)
              <Input
                className="mt-1"
                data-testid={isReceivable ? 'receivable-form-note-input' : 'payable-form-note-input'}
                placeholder="Keterangan saldo awal atau alasan penyesuaian"
                maxLength={500}
                disabled={save.isPending}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>

            {error && (
              <p className="text-sm text-destructive" role="alert" data-testid="debt-form-error">
                {error}
              </p>
            )}

            <div className="flex flex-wrap justify-end gap-2 pt-1">
              <Button
                type="button"
                variant="outline"
                className="min-h-11"
                disabled={save.isPending}
                onClick={onClose}
              >
                Batal
              </Button>
              <Button
                type="submit"
                className="min-h-11"
                data-testid={isReceivable ? 'receivable-form-submit-button' : 'payable-form-submit-button'}
                disabled={save.isPending}
              >
                {save.isPending
                  ? 'Menyimpan…'
                  : isEdit
                    ? 'Simpan perubahan'
                    : isReceivable
                      ? 'Simpan piutang'
                      : 'Simpan hutang'}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
