import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Archive, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ErrorBlock, LoadingBlock } from '@/components/StateBlock';
import { apiGet } from '@/lib/api';
import { formatIDR } from '@/lib/format';

type Row = {
  name: string; sku: string; snapshot_stock: number; cost_price: number; selling_price: number;
  value: number; current_stock: number | null; diff: number | null; matched: boolean;
};
type Snapshot = {
  source: string; snapshot_date: string | null; count: number; total_value: number;
  official_total: number | null; matched_count: number; rows: Row[]; note: string;
};

export default function StockSnapshotPage() {
  const [search, setSearch] = useState('');
  const query = useQuery({ queryKey: ['stock-snapshot'], queryFn: () => apiGet<Snapshot>('/excel/stock-snapshot?source=september') });
  const r = query.data;
  const rows = (r?.rows ?? []).filter(x => `${x.name} ${x.sku}`.toLowerCase().includes(search.toLowerCase()));

  return <div className="p-4 md:p-6 space-y-5">
    <header>
      <span data-testid="snapshot-eyebrow" className="text-xs text-primary tracking-widest">REFERENSI · TIDAK MENGUBAH STOK</span>
      <h1 data-testid="snapshot-title" className="font-heading text-2xl font-bold mt-1 flex items-center gap-2"><Archive className="size-6 text-primary" />Snapshot Stok 2 Juni 2026</h1>
      <p data-testid="snapshot-description" className="text-sm text-muted-foreground mt-1">Dari sheet "Laporan Data Barang". Cuma buat perbandingan dengan stok berjalan; stok produk aktif tidak diubah. <Link to="/impor" className="text-primary">Ke halaman impor →</Link></p>
    </header>

    {query.isPending ? <LoadingBlock label="Membaca snapshot workbook…" /> : query.isError ? <ErrorBlock error={query.error} onRetry={() => void query.refetch()} /> : r && <>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        {[['Baris snapshot', String(r.count)], ['Nilai snapshot (stok×modal)', formatIDR(r.total_value)], ['Nilai resmi laporan (B19)', r.official_total != null ? formatIDR(r.official_total) : '—'], ['Cocok dgn produk aktif', `${r.matched_count} / ${r.count}`]].map(([t, v], i) =>
          <div key={t} className="bk-panel p-4" data-testid={`snapshot-stat-${i}`}><p className="text-xs text-muted-foreground">{t}</p><strong className="font-mono text-lg block mt-2">{v}</strong></div>)}
      </div>
      <p data-testid="snapshot-note" className="bk-notice text-xs">{r.note}</p>
      <div className="relative max-w-sm"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" data-testid="snapshot-search" placeholder="Cari nama atau SKU…" value={search} onChange={e => setSearch(e.target.value)} /></div>
      <div className="bk-panel overflow-hidden"><div className="overflow-x-auto"><table className="bk-table"><thead><tr><th>Nama / SKU</th><th>Stok 2 Jun</th><th>Stok sekarang</th><th>Selisih</th><th>Modal</th><th>Nilai snapshot</th></tr></thead>
        <tbody>{rows.slice(0, 400).map(x => <tr key={x.sku} data-testid={`snapshot-row-${x.sku}`}>
          <td><b>{x.name}</b><small>{x.sku}</small></td>
          <td data-testid={`snapshot-stock-${x.sku}`}>{x.snapshot_stock}</td>
          <td>{x.current_stock == null ? <span className="text-muted-foreground text-xs">tidak ada di produk</span> : x.current_stock}</td>
          <td className={x.diff != null && x.diff !== 0 ? (x.diff > 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400') : ''}>{x.diff == null ? '—' : (x.diff > 0 ? `+${x.diff}` : x.diff)}</td>
          <td>{formatIDR(x.cost_price)}</td>
          <td className="font-semibold">{formatIDR(x.value)}</td>
        </tr>)}</tbody></table></div>
        {rows.length === 0 && <p data-testid="snapshot-empty" className="p-10 text-center text-muted-foreground text-sm">Tidak ada baris yang cocok.</p>}
        {rows.length > 400 && <p className="p-3 text-center text-xs text-muted-foreground">Menampilkan 400 dari {rows.length} baris. Gunakan pencarian untuk mempersempit.</p>}
      </div>
    </>}
  </div>;
}
