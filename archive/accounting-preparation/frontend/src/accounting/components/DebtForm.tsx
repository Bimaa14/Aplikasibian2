import React, { useState } from 'react';
import { Plus, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { api, errorMessage } from '../lib';
import { Field, FormError, inputProps } from './Common';

export const DebtForm = ({ kind, today, onClose, onSave }: any) => {
  const receivable = kind === 'receivable';
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError('');
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api.post('/debts', { ...fields, kind, total: Number(fields.total), hpp: receivable ? Number(fields.hpp) : 0 });
      toast.success(`${receivable ? 'Piutang' : 'Hutang'} berhasil dicatat`); onSave(); onClose();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open && !busy) onClose(); }}><DialogContent className="accounting-dialog" data-testid="create-debt-dialog"><DialogHeader><span className="dialog-icon"><Plus size={22} /></span><DialogTitle data-testid="create-debt-title">Tambah {receivable ? 'piutang pelanggan' : 'hutang supplier'}</DialogTitle><DialogDescription data-testid="create-debt-description">Catat transaksi kredit. Pembayaran dicatat terpisah setelah tagihan disimpan.</DialogDescription></DialogHeader>
    <form onSubmit={submit} className="accounting-form">
      <Field label={receivable ? 'Nama pelanggan' : 'Nama supplier'} name="debt-party"><input {...inputProps('debt-party')} name="party" required maxLength={120} placeholder={receivable ? 'Contoh: Budi Santoso' : 'Contoh: PT Sumber Ban'} /></Field>
      <Field label="Nomor invoice" name="debt-reference"><input {...inputProps('debt-reference')} name="reference" required maxLength={60} placeholder="Contoh: INV-2026-001" /></Field>
      <div className="form-grid"><Field label="Tanggal transaksi" name="debt-issued"><input {...inputProps('debt-issued')} type="date" name="issued_date" required defaultValue={today} max={today} /></Field><Field label="Jatuh tempo" name="debt-due"><input {...inputProps('debt-due')} type="date" name="due_date" required defaultValue={today} /></Field></div>
      <div className={receivable ? 'form-grid' : ''}><Field label="Total tagihan (Rp)" name="debt-total"><input {...inputProps('debt-total')} type="number" step="1" min="1" max="1000000000000" name="total" required placeholder="0" /></Field>{receivable && <Field label="HPP / modal terjual (Rp)" name="debt-hpp"><input {...inputProps('debt-hpp')} type="number" step="1" min="0" max="1000000000000" name="hpp" required defaultValue="0" /></Field>}</div>
      <Field label="Keterangan (opsional)" name="debt-description"><textarea {...inputProps('debt-description')} name="description" maxLength={500} rows={2} placeholder="Rincian barang atau jasa…" /></Field>
      <FormError error={error} /><div className="dialog-actions"><Button type="button" variant="outline" data-testid="cancel-create-debt" disabled={busy} onClick={onClose}>Batal</Button><Button className="btn-primary" type="submit" data-testid="submit-create-debt" disabled={busy}>{busy && <Loader2 className="spin" />}Simpan tagihan</Button></div>
    </form></DialogContent></Dialog>;
};