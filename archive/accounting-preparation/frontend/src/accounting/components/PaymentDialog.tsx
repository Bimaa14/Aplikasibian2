import React, { useState } from 'react';
import { ArrowDownLeft, Loader2, ShieldCheck } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { api, Debt, errorMessage, makeId, rupiah } from '../lib';
import { Field, FormError, inputProps } from './Common';

export const PaymentDialog = ({ debt, today, onClose, onSave }: { debt: Debt; today: string; onClose: () => void; onSave: () => void }) => {
  const [amount, setAmount] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [requestId] = useState(makeId);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setError('');
    if (!Number.isSafeInteger(Number(amount)) || Number(amount) <= 0 || Number(amount) > debt.remaining) { setError('Masukkan nominal bulat antara Rp 1 dan sisa tagihan.'); return; }
    setBusy(true);
    const values = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api.post(`/debts/${debt.id}/pay`, { ...values, amount: Number(amount), request_id: requestId });
      toast.success('Pembayaran berhasil dicatat'); onSave(); onClose();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open && !busy) onClose(); }}><DialogContent className="accounting-dialog" data-testid="payment-dialog"><DialogHeader><span className="dialog-icon"><ArrowDownLeft size={23} /></span><DialogTitle data-testid="payment-title">Catat pembayaran</DialogTitle><DialogDescription data-testid="payment-description">{debt.party} · {debt.reference}</DialogDescription></DialogHeader>
    <div className="payment-summary" data-testid="payment-summary"><div><span>Total tagihan</span><strong>{rupiah(debt.total)}</strong></div><div><span>Sudah dibayar</span><strong>{rupiah(debt.paid_amount)}</strong></div><div className="remaining"><span>Sisa tagihan</span><strong>{rupiah(debt.remaining)}</strong></div></div>
    <form onSubmit={submit} className="accounting-form"><Field label="Nominal pembayaran (Rp)" name="payment-amount"><input {...inputProps('payment-amount')} type="number" min="1" max={debt.remaining} step="1" required value={amount} onChange={e => setAmount(e.target.value)} placeholder="Masukkan nominal cicilan" autoFocus /><button className="text-link align-right" type="button" data-testid="pay-full-amount" onClick={() => setAmount(String(debt.remaining))}>Bayar seluruh sisa</button></Field>
      <div className="form-grid"><Field label="Tanggal pembayaran" name="payment-date"><input {...inputProps('payment-date')} type="date" name="payment_date" defaultValue={today} min={debt.issued_date} max={today} required /></Field><Field label="Metode pembayaran" name="payment-method"><select {...inputProps('payment-method')} name="method"><option value="cash">Tunai / kas bengkel</option><option value="transfer">Transfer bank</option></select></Field></div>
      <Field label="Catatan (opsional)" name="payment-note"><textarea {...inputProps('payment-note')} name="note" rows={2} maxLength={500} placeholder="Contoh: Cicilan pertama" /></Field>
      <div className="info-inline" data-testid="payment-audit-notice"><ShieldCheck size={16} />Pembayaran tersimpan dalam riwayat dan laporan kas.</div><FormError error={error} />
      <div className="dialog-actions"><Button type="button" variant="outline" data-testid="cancel-payment" disabled={busy} onClick={onClose}>Batal</Button><Button className="btn-primary" type="submit" data-testid="submit-payment" disabled={busy}>{busy && <Loader2 className="spin" />}Simpan pembayaran</Button></div>
    </form></DialogContent></Dialog>;
};