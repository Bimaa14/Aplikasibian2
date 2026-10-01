import React, { useState } from 'react';
import { Loader2, ReceiptText } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { api, errorMessage, makeId } from '../lib';
import { Field, FormError, inputProps } from './Common';

export const EntryForm = ({ today, onClose, onSave }: any) => {
  const [kind, setKind] = useState('sale'), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [requestId] = useState(makeId);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError('');
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    try { await api.post('/entries', { ...fields, kind, amount: Number(fields.amount), hpp: kind === 'sale' ? Number(fields.hpp) : 0, request_id: requestId }); toast.success('Transaksi kas berhasil dicatat'); onSave(); onClose(); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open && !busy) onClose(); }}><DialogContent className="accounting-dialog" data-testid="entry-dialog"><DialogHeader><span className="dialog-icon"><ReceiptText size={22} /></span><DialogTitle data-testid="entry-title">Catat transaksi kas</DialogTitle><DialogDescription data-testid="entry-description">Catat transaksi yang langsung dibayar. Cicilan tagihan dicatat dari halaman piutang atau hutang.</DialogDescription></DialogHeader>
    <form className="accounting-form" onSubmit={submit}><Field label="Jenis transaksi" name="entry-kind"><select {...inputProps('entry-kind')} value={kind} onChange={e => setKind(e.target.value)}><option value="sale">Penjualan tunai</option><option value="expense">Pengeluaran operasional</option><option value="supplier_payment">Pembelian supplier tunai</option></select></Field>
      {kind === 'supplier_payment' && <div className="warning-box" data-testid="supplier-entry-notice">Hanya pembelian tunai tanpa hutang. Untuk melunasi hutang yang sudah tercatat, gunakan tombol Bayar di halaman Hutang supaya tidak terhitung dua kali.</div>}
      <Field label="Keterangan transaksi" name="entry-description-input"><input {...inputProps('entry-description-input')} name="description" minLength={3} maxLength={300} required placeholder={kind === 'sale' ? 'Contoh: Penjualan oli dan jasa servis' : kind === 'expense' ? 'Contoh: Pembayaran listrik bengkel' : 'Contoh: Pembelian ban tunai'} /></Field>
      <Field label="Tanggal transaksi" name="entry-date"><input {...inputProps('entry-date')} name="entry_date" type="date" required defaultValue={today} max={today} /></Field>
      <div className={kind === 'sale' ? 'form-grid' : ''}><Field label="Nominal (Rp)" name="entry-amount"><input {...inputProps('entry-amount')} name="amount" type="number" step="1" min="1" max="1000000000000" required placeholder="0" /></Field>{kind === 'sale' && <Field label="HPP / modal terjual (Rp)" name="entry-hpp"><input {...inputProps('entry-hpp')} name="hpp" type="number" step="1" min="0" max="1000000000000" required defaultValue="0" /></Field>}</div>
      <FormError error={error} /><div className="dialog-actions"><Button variant="outline" type="button" data-testid="cancel-entry" disabled={busy} onClick={onClose}>Batal</Button><Button className="btn-primary" type="submit" data-testid="submit-entry" disabled={busy}>{busy && <Loader2 className="spin" />}Simpan transaksi</Button></div>
    </form></DialogContent></Dialog>;
};