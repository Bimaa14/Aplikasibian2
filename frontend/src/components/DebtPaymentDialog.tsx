import { PAYMENT_OPTIONS } from '@/lib/payments';
import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { apiPost } from '@/lib/api';
import { formatIDR, getApiErrorMessage } from '@/lib/format';
import type { DebtRow } from '@/pages/DebtPage';

export function DebtPaymentDialog({ debt, kind, today, onClose, onSaved }: { debt: DebtRow; kind: string; today: string; onClose: () => void; onSaved: () => void }) {
  const [amount, setAmount] = useState(''), [profit, setProfit] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [requestId] = useState(() => crypto.randomUUID());
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError('');
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try { await apiPost(`/${kind}/${debt.id}/pay`, { ...data, amount: Number(amount), request_id: requestId, ...(profit !== '' ? { profit_amount: Number(profit) } : {}) }); toast.success('Cicilan berhasil dicatat'); onSaved(); onClose(); }
    catch (e) { setError(getApiErrorMessage(e)); } finally { setBusy(false); }
  }
  return <Dialog open onOpenChange={o => { if (!o && !busy) onClose(); }}><DialogContent data-testid="payment-dialog"><DialogHeader><DialogTitle>Catat pembayaran</DialogTitle><DialogDescription>{debt.invoice_number} · Total {formatIDR(debt.amount)}</DialogDescription></DialogHeader><p data-testid="payment-remaining" className="bk-notice">Sudah dibayar {formatIDR(debt.paid_amount)} · Sisa <b>{formatIDR(debt.remaining)}</b></p><form className="space-y-4" onSubmit={submit}><label className="block text-sm">Nominal cicilan (Rp)<Input data-testid="payment-amount" type="number" min="0.01" step="0.01" max={debt.remaining} required value={amount} onChange={e => setAmount(e.target.value)} /></label><Button type="button" size="sm" variant="outline" data-testid="payment-full-amount" onClick={() => setAmount(String(debt.remaining))}>Isi seluruh sisa</Button><div className="grid grid-cols-2 gap-3"><label className="block text-sm">Tanggal<Input data-testid="payment-date" type="date" name="payment_date" defaultValue={today} min={debt.issued_date || undefined} max={today} required /></label><label className="block text-sm">Metode<select className="bk-control" data-testid="payment-method" name="method">{PAYMENT_OPTIONS.filter(([method]) => method !== 'credit').map(([method, label]) => <option key={method} value={method}>{label}</option>)}<option value="transfer">Transfer lainnya</option></select></label></div>{kind === 'receivables' && <label className="block text-sm">Porsi laba cicilan (Rp, opsional)<Input data-testid="payment-profit" type="number" step="0.01" value={profit} onChange={e => setProfit(e.target.value)} placeholder="Kosong: prorata laba transaksi" /><small data-testid="payment-profit-help" className="block mt-1 text-muted-foreground">Sesuai kolom PROFIT di PAYMENT CREDIT. Untuk saldo awal tanpa transaksi, isi sesuai catatan; otomatisnya 0.</small></label>}<Input data-testid="payment-note" name="note" maxLength={500} placeholder="Catatan pembayaran" />{error && <p role="alert" data-testid="payment-error" className="text-sm text-red-700 dark:text-red-400">{error}</p>}<div className="flex justify-end gap-2"><Button variant="outline" type="button" data-testid="payment-cancel" onClick={onClose} disabled={busy}>Batal</Button><Button type="submit" data-testid="payment-submit" disabled={busy}>{busy ? 'Menyimpan…' : 'Simpan pembayaran'}</Button></div></form></DialogContent></Dialog>;
}