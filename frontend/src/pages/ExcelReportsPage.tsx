import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FileSpreadsheet, Settings2, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { ErrorBlock, LoadingBlock } from '@/components/StateBlock';
import { apiGet, apiPut } from '@/lib/api';
import { formatIDR, getApiErrorMessage, todayLocalISO } from '@/lib/format';

const STORE_LABELS: Record<string, string> = { pendapatan: 'E · Total pendapatan (tanpa oli)', modal: 'F · Modal', laba: 'G · Laba', spooring: 'H · Spooring / Service', supplier: 'I · Pembayaran supplier', pengeluaran: 'J · Pengeluaran', total_modal: 'K · Total modal tersisa', nett_laba: 'L · Nett laba', nett_spooring: 'M · Nett spooring (= H)' };
const SEPT_LABELS: Record<string, string> = { total_pendapatan: 'B8 · Total pendapatan termasuk oli', modal_bersih: 'B12 · Sisa uang modal', laba_kotor: 'E10 · Total laba', laba_bersih: 'E15 · Laba bersih', spooring_bersih: 'H12 · Sisa spooring', jumlah_aset: 'B22 · Jumlah aset', sisa_aset: 'B24 · Sisa aset setelah hutang' };
const INPUT_LABELS: Record<string, string> = { pendapatan_toko: 'B4 · Pendapatan toko (modal)', pendapatan_laba: 'B5 · Pendapatan laba', spooring: 'B6 · Spooring', oli: 'B7 · Oli', distributor: 'B11 · Distributor', gaji: 'E11 · Gaji karyawan', pajak: 'E12 · Pajak', operasional: 'E13 · Operasional', pengeluaran: 'E14 · Pengeluaran', cicilan_mesin: 'H11 · Cicilan mesin', stok: 'B19 · Nilai stok', piutang: 'B21 · Sisa piutang', hutang: 'B23 · Sisa hutang' };
type ReportData = { month: string; origin: string; store: Record<string, number> | null; september: Record<string, number> | null; inputs: Record<string, number> | null; overrides?: Record<string, number>; notice: string; asset_snapshot_missing?: boolean; store_check?: { differences: Record<string, number> }; september_check?: { differences: Record<string, number> }; source_filename?: string; cash?: { income: number; supplier: number; expenses: number; transfers: number; service_fee: number; modal_bian: number; laba_bian: number; net: number; final: number } };

export default function ExcelReportsPage() {
  const [month, setMonth] = useState(todayLocalISO().slice(0, 7)), [origin, setOrigin] = useState('live'), [paramsOpen, setParamsOpen] = useState(false);
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['excel-report', month, origin], queryFn: () => apiGet<ReportData>(`/excel/reports?month=${month}&origin=${origin}`) });
  const r = query.data;
  const sourceDescription = r?.source_filename
    ? `Acuan perhitungan: ${r.source_filename}.`
    : 'Acuan perhitungan mengikuti sumber laporan.';
  const save = useMutation({ mutationFn: (values: Record<string, number>) => apiPut(`/excel/parameters/${month}`, { values }), onSuccess: () => { toast.success('Parameter bulan disimpan'); setParamsOpen(false); void client.invalidateQueries({ queryKey: ['excel-report'] }); }, onError: e => toast.error(getApiErrorMessage(e)) });
  function exportCsv() {
    if (!r) return;
    const rows: (string | number)[][] = [['Sumber', origin === 'preview' ? 'PRATINJAU EXCEL, BELUM DATA KASIR' : 'Data kasir tersimpan'], ['Periode', month], ['STORE REPORT', 'Nominal'], ...Object.entries(r.store ?? {}).map(([k, v]) => [STORE_LABELS[k], v]), ['LAPORAN LABA RUGI', 'Nominal'], ...Object.entries(r.september ?? {}).map(([k, v]) => [SEPT_LABELS[k], r.asset_snapshot_missing && ['jumlah_aset', 'sisa_aset'].includes(k) ? 'Snapshot historis belum diisi' : v])];
    const content = '\ufeff' + rows.map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\r\n');
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' })); const a = document.createElement('a'); a.href=url; a.download=`perkasa-jaya-${origin}-${month}.csv`; a.click(); URL.revokeObjectURL(url);
  }
  return <div className="page-workspace space-y-5"><header className="page-heading"><div className="min-w-0"><h1 data-testid="excel-report-title" className="font-heading text-2xl font-bold">Laporan sesuai Excel</h1><p data-testid="excel-report-description" className="break-words text-sm text-muted-foreground mt-1">{sourceDescription}</p></div><div className="report-actions flex flex-wrap gap-2"><input className="bk-control w-full sm:w-40" data-testid="excel-report-month" aria-label="Periode" type="month" value={month} onChange={e => e.target.value && setMonth(e.target.value)} /><Button variant="outline" data-testid="excel-export" disabled={!r || query.isFetching} onClick={exportCsv}><Download />Unduh CSV</Button></div></header>
    <div className="page-toolbar flex flex-wrap items-center gap-3"><div className="page-tabs flex flex-wrap gap-2" aria-label="Sumber laporan"><Button data-testid="excel-source-preview" aria-pressed={origin === 'preview'} variant={origin === 'preview' ? 'default' : 'outline'} onClick={() => setOrigin('preview')}>Pratinjau Excel asli</Button><Button data-testid="excel-source-live" aria-pressed={origin === 'live'} variant={origin === 'live' ? 'default' : 'outline'} onClick={() => setOrigin('live')}>Data kasir tersimpan</Button></div><Link className="inline-flex min-h-11 items-center text-sm text-primary sm:ml-auto" data-testid="excel-margin-link" to="/laporan">Lihat laporan bulanan</Link></div>
    {query.isPending ? <LoadingBlock /> : query.isError ? <ErrorBlock error={query.error} onRetry={() => void query.refetch()} /> : r && <>
      <p data-testid="excel-source-notice" className="bk-notice">{r.notice}</p>
      <div className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-2">
        {[
          ['store', 'Store Information System', 'Sheet REPORT', r.store, STORE_LABELS, r.store_check],
          ['september', 'Laporan aset tambahan', 'Sheet Laporan Laba - Rugi', r.september, SEPT_LABELS, r.september_check],
        ].map(([id, title, sheet, values, labels, check]) => {
          const data = values as Record<string, number> | null;
          const differences = (check as { differences: Record<string, number> } | undefined)?.differences;
          const matched = differences && Object.values(differences).every(v => Math.abs(v) <= 0.01);
          return <section className="bk-panel ledger-statement min-w-0" key={String(id)}>
            <div className="section-heading flex flex-wrap items-center gap-3 border-b border-border p-5">
              <FileSpreadsheet className="size-5 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1"><h2 className="font-heading text-lg font-semibold" data-testid={`profile-title-${id}`}>{String(title)}</h2><p className="text-sm text-muted-foreground" data-testid={`profile-sheet-${id}`}>{String(sheet)}</p></div>
              {matched && <span data-testid={`profile-matched-${id}`} className="flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-400"><CheckCircle2 className="size-4 shrink-0" />Cocok dengan Excel</span>}
            </div>
            {data ? <div>{Object.entries(data).map(([key, val]) => <div key={key} data-testid={`excel-${id}-${key}`} className={`bk-report-row ledger-line ${['nett_laba', 'laba_bersih', 'total', 'sisa_aset'].includes(key) ? 'bk-report-total ledger-total' : ''}`}><span>{(labels as Record<string, string>)[key]}</span><strong className={val < 0 ? 'text-red-700 dark:text-red-400' : ''}>{r.asset_snapshot_missing && ['jumlah_aset', 'sisa_aset'].includes(key) ? 'Perlu snapshot' : formatIDR(val)}</strong></div>)}</div> : <p data-testid={`profile-unavailable-${id}`} className="p-8 text-sm text-muted-foreground">Workbook ini tidak memuat laporan periode tersebut. Pilih bulan lain untuk memeriksa laporan.</p>}
            <details className="border-t border-border p-4"><summary data-testid={`profile-formula-toggle-${id}`} className="min-h-11 cursor-pointer content-center text-sm font-medium">Rumus pada sheet sumber</summary><p data-testid={`profile-formula-${id}`} className="mt-2 text-sm leading-relaxed text-muted-foreground">{id === 'store' ? 'E = penjualan tunai tanpa OIL + pembayaran piutang − fee tunai. G = laba tunai tanpa OIL/SERVICE + laba cicilan − fee kredit. F = E − G − H. K = F − I. L = G − J. M = H (spooring tetap terpisah).' : 'B8 = B4+B5+B6+B7. B12 = B10−B11. E15 = E10−SUM(E11:E14). H12 = H10−H11. B24 = stok + sisa modal + piutang − hutang. Oli ikut B8, tetapi tidak masuk E15.'}</p></details>
          </section>;
        })}
      </div>
      {r.cash && <section className="bk-panel p-5"><h2 data-testid="cash-flow-title" className="font-heading text-lg mb-4">Kas sesuai DAILY REPORT</h2><div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">{[['Penjualan tanpa oli + pembayaran piutang', r.cash.income], ['Transfer', r.cash.transfers], ['Pengeluaran dari kasir', r.cash.expenses], ['Komisi montir', r.cash.service_fee], ['Kas sebelum pengambilan BIAN', r.cash.net], ['Pengambilan modal + laba BIAN', r.cash.modal_bian + r.cash.laba_bian], ['Kas akhir', r.cash.final]].map(([label, value], i) => <div data-testid={`live-cash-${i}`} key={String(label)} className={i === 6 ? 'ledger-total rounded-md p-3 sm:col-span-2 xl:col-span-4' : 'min-w-0'}><span className="text-sm text-muted-foreground">{label}</span><b className={`font-mono block mt-1 ${i === 6 ? 'text-xl' : ''}`}>{formatIDR(Number(value))}</b></div>)}</div></section>}
      {origin === 'live' && <div className="bk-panel p-5 flex flex-wrap items-center justify-between gap-4"><div><h2 data-testid="monthly-input-title" className="font-heading text-lg">Parameter & snapshot bulanan</h2><p data-testid="monthly-input-description" className="text-sm text-muted-foreground">Gaji/pajak/pengeluaran otomatis dari kategori kasir. Isi override hanya jika perlu mengikuti catatan manual Excel.</p>{r.asset_snapshot_missing && <p data-testid="asset-snapshot-warning" className="text-amber-700 dark:text-amber-400 text-xs mt-2">Nilai aset historis belum lengkap. Isi stok, piutang, dan hutang posisi akhir bulan; jangan menggunakan saldo hari ini.</p>}</div><Button variant="outline" data-testid="edit-monthly-inputs" onClick={() => setParamsOpen(true)}><Settings2 />Atur parameter</Button></div>}
      {origin === 'preview' && <Link data-testid="report-to-import" to="/impor" className="block bk-panel p-4 text-sm text-primary">Periksa produk, stok, transaksi, dan tagihan sebelum mengimpor</Link>}
    </>}
    <Dialog open={paramsOpen} onOpenChange={setParamsOpen}><DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="monthly-parameters-dialog"><DialogHeader><DialogTitle>Parameter {month}</DialogTitle><DialogDescription>Kolom kosong mengikuti data otomatis. Nominal yang diisi menggantikan nilai otomatis. Kosongkan kembali untuk menghapus override.</DialogDescription></DialogHeader><form className="space-y-4" onSubmit={e => { e.preventDefault(); const fields=Object.fromEntries(new FormData(e.currentTarget)); save.mutate(Object.fromEntries(Object.entries(fields).filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]))); }}><div className="grid sm:grid-cols-2 gap-3">{Object.entries(INPUT_LABELS).map(([k, label]) => <label key={k} className="text-xs block" data-testid={`parameter-label-${k}`}>{label}<input className="bk-control mt-1" data-testid={`parameter-${k}`} name={k} type="number" step="0.01" defaultValue={r?.overrides?.[k] ?? ''} placeholder={`Otomatis: ${r?.inputs?.[k] ?? 0}`} /></label>)}</div><Button data-testid="save-monthly-parameters" type="submit" disabled={save.isPending}>Simpan parameter</Button></form></DialogContent></Dialog>
  </div>;
}
