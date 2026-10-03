import { PAYMENT_OPTIONS } from '@/lib/payments';
import { todayLocalISO } from '@/lib/format';

export type SalesFilterValues = { month: string; owner: string; category: string; tax: string; payment_method: string };
export const initialSalesFilters = (): SalesFilterValues => ({ month: todayLocalISO().slice(0, 7), owner: '', category: '', tax: '', payment_method: '' });
export function salesFilterQuery(filters: SalesFilterValues) {
  return new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== '')).toString();
}
export default function SalesFilters({ value, onChange, showTax = true }: {
  value: SalesFilterValues; onChange: (value: SalesFilterValues) => void; showTax?: boolean;
}) {
  const set = (key: keyof SalesFilterValues, next: string) => onChange({ ...value, [key]: next });
  return <div className="grid gap-3 rounded-lg border border-border bg-card p-3 sm:grid-cols-2 xl:grid-cols-5">
    <label className="space-y-1 text-xs">Bulan<input aria-label="Bulan laporan" type="month" className="bk-control" value={value.month} onChange={e => { if (e.target.value) set('month', e.target.value); }} /></label>
    <label className="space-y-1 text-xs">Kepemilikan<select aria-label="Pemilik laporan" className="bk-control" value={value.owner} onChange={e => set('owner', e.target.value)}>
      <option value="">Semua pemilik</option><option value="bian">Bian</option><option value="ibu">Ibu</option>{["non", "polosan", "non vpt", "non vat"].map(o => <option key={o} value={o}>{o.toUpperCase()}</option>)}<option value="unassigned">Belum ditandai</option>
    </select></label>
    <label className="space-y-1 text-xs">Kategori<select aria-label="Kategori laporan" className="bk-control" value={value.category} onChange={e => set('category', e.target.value)}>
      <option value="">Semua kategori</option><option value="TIRE">Ban</option><option value="OIL">Oli</option><option value="SERVICE">Servis</option><option value="COMPLEMENTARY">Pelengkap</option><option value="unassigned">Belum ditandai</option>
    </select></label>
    {showTax && <label className="space-y-1 text-xs">TAX<select aria-label="TAX laporan" className="bk-control" value={value.tax} onChange={e => set('tax', e.target.value)}>
      <option value="">Semua TAX</option><option value="1">1 — Kena pajak laporan</option><option value="0">0 — Tidak kena pajak</option><option value="unassigned">Belum ditandai</option>
    </select></label>}
    <label className="space-y-1 text-xs">Pembayaran<select aria-label="Pembayaran laporan" className="bk-control" value={value.payment_method} onChange={e => set('payment_method', e.target.value)}>
      <option value="">Semua pembayaran</option>{PAYMENT_OPTIONS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select></label>
  </div>;
}
