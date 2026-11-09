import { NON_CASH_OPTIONS, PAYMENT_OPTIONS } from '@/lib/payments';
import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { apiPost } from '@/lib/api';
import { formatIDR, getApiErrorMessage } from '@/lib/format';
import type { DebtRow } from '@/pages/DebtPage';
import type { NonCashMethod } from '@/lib/types';

export function DebtPaymentDialog({ debt, kind, today, onClose, onSaved }: { debt: DebtRow; kind: string; today: string; onClose: () => void; onSaved: () => void }) {
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState('cash');
  const [mixCash, setMixCash] = useState('');
  const [mixTransfer, setMixTransfer] = useState('');
  const [mixMethod, setMixMethod] = useState<NonCashMethod | 'transfer'>('transfer_bca');
  const [profit, setProfit] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [requestId] = useState(() => crypto.randomUUID());

  const totalNum = Number(amount);

  function handleAmountChange(val: string) {
    setAmount(val);
    const num = Number(val);
    if (method === 'mix' && Number.isFinite(num) && num > 0) {
      const cashNum = Number(mixCash);
      if (mixCash !== '' && Number.isFinite(cashNum) && cashNum > 0 && cashNum < num) {
        setMixTransfer(String(Math.max(0, Math.round((num - cashNum) * 100) / 100)));
      }
    }
  }

  function handleMixCashChange(val: string) {
    setMixCash(val);
    const cashNum = Number(val);
    if (val !== '' && Number.isFinite(cashNum) && cashNum >= 0 && Number.isFinite(totalNum) && totalNum > 0 && cashNum < totalNum) {
      setMixTransfer(String(Math.max(0, Math.round((totalNum - cashNum) * 100) / 100)));
    }
  }

  function handleMixTransferChange(val: string) {
    setMixTransfer(val);
    const tfNum = Number(val);
    if (val !== '' && Number.isFinite(tfNum) && tfNum >= 0 && Number.isFinite(totalNum) && totalNum > 0 && tfNum < totalNum) {
      setMixCash(String(Math.max(0, Math.round((totalNum - tfNum) * 100) / 100)));
    }
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    if (method === 'mix') {
      const c = Number(mixCash);
      const t = Number(mixTransfer);
      if (!Number.isFinite(c) || !Number.isFinite(t) || c <= 0 || t <= 0 || Math.round((c + t) * 100) !== Math.round(totalNum * 100)) {
        setError('Untuk metode Mix, nominal tunai dan transfer harus lebih dari 0 dan jumlahnya tepat sama dengan nominal cicilan.');
        return;
      }
    }
    setBusy(true);
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await apiPost(`/${kind}/${debt.id}/pay`, {
        ...data,
        method,
        amount: totalNum,
        request_id: requestId,
        ...(method === 'mix'
          ? {
              cash_amount: Number(mixCash),
              transfer_amount: Number(mixTransfer),
              transfer_method: mixMethod,
            }
          : {}),
        ...(profit !== '' ? { profit_amount: Number(profit) } : {}),
      });
      toast.success('Cicilan berhasil dicatat');
      onSaved();
      onClose();
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={o => { if (!o && !busy) onClose(); }}>
      <DialogContent data-testid="payment-dialog">
        <DialogHeader>
          <DialogTitle>Catat pembayaran</DialogTitle>
          <DialogDescription>{debt.invoice_number} · Total {formatIDR(debt.amount)}</DialogDescription>
        </DialogHeader>
        <p data-testid="payment-remaining" className="bk-notice">
          Sudah dibayar {formatIDR(debt.paid_amount)} · Sisa <b>{formatIDR(debt.remaining)}</b>
        </p>
        <form className="space-y-4" onSubmit={submit}>
          <label className="block text-sm">
            Nominal cicilan (Rp)
            <Input
              data-testid="payment-amount"
              type="number"
              min="0.01"
              step="0.01"
              max={debt.remaining}
              required
              value={amount}
              onChange={e => handleAmountChange(e.target.value)}
            />
          </label>
          <Button
            type="button"
            size="sm"
            className="min-h-11"
            variant="outline"
            data-testid="payment-full-amount"
            onClick={() => handleAmountChange(String(debt.remaining))}
          >
            Isi seluruh sisa
          </Button>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              Tanggal
              <Input
                data-testid="payment-date"
                type="date"
                name="payment_date"
                defaultValue={today}
                min={debt.issued_date || undefined}
                max={today}
                required
              />
            </label>
            <label className="block text-sm">
              Metode pembayaran
              <select
                className="bk-control"
                data-testid="payment-method"
                name="method"
                value={method}
                onChange={e => setMethod(e.target.value)}
              >
                {PAYMENT_OPTIONS.filter(([m]) => m !== 'credit').map(([m, label]) => (
                  <option key={m} value={m}>{label}</option>
                ))}
                <option value="transfer">Transfer lainnya</option>
              </select>
            </label>
          </div>
          {method === 'mix' && (
            <div className="space-y-3 rounded-lg border border-border bg-secondary/30 p-3" data-testid="payment-mix-panel">
              <p className="text-xs font-medium text-muted-foreground">
                Rincian pembayaran Mix (Tunai + Transfer)
              </p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  Nominal tunai (Rp)
                  <Input
                    data-testid="payment-mix-cash"
                    type="number"
                    min="0.01"
                    step="0.01"
                    max={Math.max(0.01, (Number(amount) || debt.remaining) - 0.01)}
                    required
                    value={mixCash}
                    onChange={e => handleMixCashChange(e.target.value)}
                    placeholder="Nominal tunai"
                  />
                </label>
                <label className="block text-sm">
                  Nominal transfer (Rp)
                  <Input
                    data-testid="payment-mix-transfer"
                    type="number"
                    min="0.01"
                    step="0.01"
                    max={Math.max(0.01, (Number(amount) || debt.remaining) - 0.01)}
                    required
                    value={mixTransfer}
                    onChange={e => handleMixTransferChange(e.target.value)}
                    placeholder="Nominal transfer"
                  />
                </label>
              </div>
              <label className="block text-sm">
                Rekening / kanal transfer
                <select
                  className="bk-control mt-1"
                  data-testid="payment-mix-method"
                  value={mixMethod}
                  onChange={e => setMixMethod(e.target.value as NonCashMethod | 'transfer')}
                >
                  {NON_CASH_OPTIONS.map(([m, label]) => (
                    <option key={m} value={m}>{label}</option>
                  ))}
                  <option value="transfer">Transfer lainnya</option>
                </select>
              </label>
            </div>
          )}
          {kind === 'receivables' && (
            <label className="block text-sm">
              Porsi laba cicilan (Rp, opsional)
              <Input
                data-testid="payment-profit"
                type="number"
                min="0"
                max={Math.max(0, Number(amount) || 0)}
                step="0.01"
                value={profit}
                onChange={e => setProfit(e.target.value)}
                placeholder="Kosong: laba diambil lebih dulu"
              />
              <small data-testid="payment-profit-help" className="block mt-1 text-muted-foreground">
                Otomatis mengambil sisa laba nota, maksimal sebesar pembayaran ini. Setelah laba terpenuhi, cicilan berikutnya menjadi modal toko. Isi manual untuk penyesuaian atau saldo awal tanpa rincian transaksi.
              </small>
            </label>
          )}
          <Input data-testid="payment-note" aria-label="Catatan pembayaran" name="note" maxLength={500} placeholder="Catatan pembayaran" />
          {error && <p role="alert" data-testid="payment-error" className="text-sm text-red-700 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button className="min-h-11" variant="outline" type="button" data-testid="payment-cancel" onClick={onClose} disabled={busy}>
              Batal
            </Button>
            <Button className="min-h-11" type="submit" data-testid="payment-submit" disabled={busy}>
              {busy ? 'Menyimpan…' : 'Simpan pembayaran'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
