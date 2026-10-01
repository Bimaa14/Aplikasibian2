import React, { useState } from 'react';
import { Clock3, Undo2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { api, Debt, dateLabel, errorMessage, rupiah } from '../lib';
import { Field, FormError, inputProps, Status } from './Common';

export const DebtDetail = ({ debt, onClose, onSave, onPay }: { debt: Debt; onClose: () => void; onSave: () => void; onPay: () => void }) => {
  const [returning, setReturning] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError('');
    const values = Object.fromEntries(new FormData(e.currentTarget));
    try { await api.post(`/debts/${debt.id}/return`, { reason: values.reason, refund_confirmed: values.refund_confirmed === 'on' }); toast.success('Piutang diretur, tidak dihitung sebagai lunas'); onSave(); onClose(); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open && !busy) onClose(); }}><DialogContent className="accounting-dialog" data-testid="debt-detail-dialog"><DialogHeader><DialogTitle data-testid="debt-detail-title">{returning ? 'Retur seluruh transaksi kredit' : 'Detail tagihan'}</DialogTitle><DialogDescription data-testid="debt-detail-description">{debt.reference} · {debt.party}</DialogDescription></DialogHeader>
    <Status status={debt.status} id={`detail-${debt.id}`} /><div className="payment-summary" data-testid="detail-balances"><div><span>Total</span><strong>{rupiah(debt.total)}</strong></div><div><span>Terbayar</span><strong>{rupiah(debt.paid_amount)}</strong></div><div className="remaining"><span>Sisa</span><strong>{rupiah(debt.remaining)}</strong></div></div>
    {returning ? <form className="accounting-form" onSubmit={submit}><div className="warning-box" data-testid="return-warning">Seluruh penjualan dan HPP akan dibalik pada tanggal retur. Sisa piutang menjadi nol dengan status Void, bukan Lunas. Tindakan ini tidak dapat dibatalkan.</div>
      {debt.paid_amount > 0 && <label className="checkbox-field"><input data-testid="confirm-refund" type="checkbox" name="refund_confirmed" required /><span data-testid="refund-confirmation-label">Saya sudah mengembalikan {rupiah(debt.paid_amount)} kepada pelanggan hari ini. Catat sebagai kas keluar.</span></label>}
      <Field label="Alasan retur" name="return-reason"><textarea {...inputProps('return-reason')} name="reason" minLength={3} maxLength={500} required rows={3} /></Field><FormError error={error} /><div className="dialog-actions"><Button variant="outline" type="button" data-testid="cancel-return" disabled={busy} onClick={() => setReturning(false)}>Kembali</Button><Button variant="destructive" data-testid="submit-return" disabled={busy}>{busy && <Loader2 className="spin" />}Konfirmasi retur</Button></div></form> : <>
      <div className="detail-dates" data-testid="debt-detail-dates"><span>Transaksi <b>{dateLabel(debt.issued_date)}</b></span><span>Jatuh tempo <b>{dateLabel(debt.due_date)}</b></span></div>{debt.description && <p className="detail-description" data-testid="debt-note">{debt.description}</p>}
      <h3 className="section-small" data-testid="payment-history-title"><Clock3 size={16} />Riwayat pembayaran <span>{debt.payments.length}</span></h3>
      <div className="payment-history" data-testid="payment-history">{debt.payments.length === 0 ? <p className="history-empty" data-testid="no-payment-history">Belum ada pembayaran untuk tagihan ini.</p> : debt.payments.map(p => <div className="history-row" key={p.id} data-testid={`payment-record-${p.id}`}><div><strong>{dateLabel(p.payment_date)}</strong><small>{p.method === 'cash' ? 'Tunai' : 'Transfer'}{p.note ? ` · ${p.note}` : ''}</small></div><b>{rupiah(p.amount)}</b></div>)}</div>
      {debt.status === 'void' && <div className="warning-box" data-testid="return-detail">Diretur {dateLabel(debt.return_date!)}: {debt.return_reason}. Pengembalian kas: {rupiah(debt.refund_amount)}. Tidak masuk piutang lunas.</div>}
      <div className="dialog-actions spread">{debt.kind === 'receivable' && debt.status !== 'void' ? <Button variant="ghost" className="danger-text" data-testid="start-return" onClick={() => setReturning(true)}><Undo2 size={15} />Retur transaksi</Button> : <span />}{['unpaid', 'partial'].includes(debt.status) ? <Button className="btn-primary" data-testid="detail-pay" onClick={onPay}>Catat pembayaran</Button> : <Button variant="outline" data-testid="close-detail" onClick={onClose}>Tutup</Button>}</div>
    </>}
  </DialogContent></Dialog>;
};