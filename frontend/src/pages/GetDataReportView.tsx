import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet, fileUrl } from '@/lib/api';
import { todayLocalISO, formatIDR } from '@/lib/format';
import { LoadingBlock, ErrorBlock } from '@/components/StateBlock';
import { Button } from '@/components/ui/button';

type Filters = { month: string; report: string; owner: string; category: string; tax: string; origin: string };
type Report = { total: number; full_total: number; summarized_count: number; summary_row_limit: number; tax_base: number; pph_final: number | null; count: number; page: number; page_size: number; notice: string; filename: string | null;
  rows: { date: string; invoice_date: string; item: string; invoice: string; amount: number; amount_without_vat: number | null; vat_amount: number | null; party: string; source_sheet: string; source_row: number | null }[] };
const owners = ['bian', 'ibu', 'non', 'polosan', 'non vpt', 'non vat'];
export default function GetDataReportView() {
  const initial: Filters = { month: todayLocalISO().slice(0, 7), report: 'sales', owner: '', category: '', tax: '', origin: 'live' };
  const [draft, setDraft] = useState(initial), [filters, setFilters] = useState(initial), [page, setPage] = useState(1);
  const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v !== ''));
  if (!filters.tax) params.set('all_tax', 'true');
  const query = useQuery({ queryKey: ['get-data-report', params.toString(), page], queryFn: () => apiGet<Report>(`/books/get-data?${params}&page=${page}`) });
  const set = (key: keyof Filters, value: string) => setDraft(prev => ({ ...prev, [key]: value }));
  const r = query.data;
  return <div className="space-y-4">
    <form className="bk-panel grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-4" onSubmit={e => { e.preventDefault(); setFilters({ ...draft }); setPage(1); if (JSON.stringify(draft) === JSON.stringify(filters)) void query.refetch(); }}>
      <label className="text-sm space-y-1">Bulan<input data-testid="get-data-month" aria-label="Bulan Get Data" type="month" className="bk-control" value={draft.month} required onChange={e => set('month', e.target.value)} /></label>
      <label className="text-sm space-y-1">Jenis laporan<select data-testid="get-data-report-kind" aria-label="Jenis report" className="bk-control" value={draft.report} onChange={e => set('report', e.target.value)}><option value="sales">Penjualan</option><option value="purchases">Pembelian</option></select></label>
      <label className="text-sm space-y-1">Pemilik (Owned by)<select data-testid="get-data-owner" aria-label="Pemilik Get Data" className="bk-control" value={draft.owner} onChange={e => set('owner', e.target.value)}><option value="">Semua</option>{owners.map(o => <option key={o} value={o}>{o.toUpperCase()}</option>)}<option value="unassigned">Belum ditandai</option></select></label>
      <label className="text-sm space-y-1">Filter TAX tambahan<select data-testid="get-data-tax" aria-label="TAX Get Data" className="bk-control" value={draft.tax} onChange={e => set('tax', e.target.value)}><option value="">Aturan Excel</option><option value="1">TAX = 1</option><option value="0">TAX = 0</option><option value="unassigned">Belum ditandai</option></select></label>
      <label className="text-sm space-y-1">Kategori<select data-testid="get-data-category" aria-label="Kategori Get Data" className="bk-control" value={draft.category} onChange={e => set('category', e.target.value)}><option value="">Semua kategori</option>{['TIRE', 'OIL', 'SERVICE', 'COMPLEMENTARY'].map(c => <option key={c}>{c}</option>)}</select></label>
      <label className="text-sm space-y-1 sm:col-span-2">Sumber<select data-testid="get-data-source" aria-label="Sumber Get Data" className="bk-control" value={draft.origin} onChange={e => set('origin', e.target.value)}><option value="live">Database aplikasi</option><option value="preview">Pratinjau file spreadsheet (belum impor)</option></select></label>
      <Button type="submit" className="self-end" data-testid="get-data-submit">Get Data</Button>
    </form>
    {query.isPending ? <LoadingBlock /> : query.isError ? <ErrorBlock error={query.error} onRetry={() => void query.refetch()} /> : r && <>
      <div className="section-heading flex flex-wrap items-center justify-between gap-3"><div className="min-w-0"><h2 className="font-heading text-lg font-semibold">Laporan {filters.report === 'sales' ? 'penjualan' : 'pembelian'} · {filters.month}</h2><p className="break-words text-sm text-muted-foreground">{filters.origin === 'preview' ? `Pratinjau: ${r.filename}` : 'Data tersimpan di aplikasi'} · {r.count} baris</p></div><a data-testid="get-data-download-csv" className="inline-flex min-h-11 items-center rounded-md border border-border bg-card px-4 py-2 text-sm font-medium" href={fileUrl(`/books/get-data/csv?${params}`)}>Unduh CSV Get Data</a></div>
      <div className="metric-strip grid gap-0 sm:grid-cols-2"><div className="metric-strip-item min-w-0 p-4"><p className="text-sm text-muted-foreground">Total sesuai Excel</p><strong data-testid="get-data-total" className="mt-2 block font-mono text-xl">{formatIDR(r.total)}</strong></div>{r.pph_final !== null && <div className="metric-strip-item min-w-0 p-4"><p className="text-sm text-muted-foreground">Estimasi PPh 0,5%</p><strong data-testid="get-data-pph" className="mt-2 block font-mono text-xl">{formatIDR(r.pph_final)}</strong></div>}</div>
      {r.count > r.summary_row_limit && <p className="bk-notice">Total Excel mencakup {r.summarized_count} baris pertama. Total seluruh {r.count} baris: {formatIDR(r.full_total)}.</p>}
      <p className="text-xs text-muted-foreground">{r.notice}</p>
      <div className="data-table-panel bk-panel overflow-x-auto"><table className="bk-table" data-testid="get-data-table"><thead><tr><th>Tanggal transaksi</th><th>Jenis barang</th><th>No. faktur</th><th>Tanggal faktur</th><th>Harga {filters.report === 'sales' ? 'jual' : 'beli'} termasuk PPN</th><th>Harga tanpa PPN</th><th>Nilai PPN</th><th>Nama pembeli / penjual</th></tr></thead><tbody>{r.rows.map((row, i) => <tr key={i}><td>{row.date}</td><td>{row.item}<small>{row.source_sheet}{row.source_row ? ` · baris ${row.source_row}` : ''}</small></td><td>{row.invoice}</td><td>{row.invoice_date}</td><td>{formatIDR(row.amount)}</td><td>{row.amount_without_vat == null ? '-' : formatIDR(row.amount_without_vat)}</td><td>{row.vat_amount == null ? '-' : formatIDR(row.vat_amount)}</td><td>{row.party || '-'}</td></tr>)}</tbody></table>{r.count === 0 && <p data-testid="get-data-empty" className="p-6 text-sm text-center">Tidak ada data sesuai filter. Ubah bulan, pemilik, atau sumber lalu tekan Get Data.</p>}</div>
      <div className="page-pagination flex flex-wrap items-center justify-between gap-3 text-sm"><span>Halaman {page} / {Math.max(1, Math.ceil(r.count / r.page_size))}</span><div className="flex gap-2"><Button data-testid="get-data-prev" variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Sebelumnya</Button><Button data-testid="get-data-next" variant="outline" disabled={page * r.page_size >= r.count} onClick={() => setPage(p => p + 1)}>Berikutnya</Button></div></div>
    </>}
  </div>;
}
