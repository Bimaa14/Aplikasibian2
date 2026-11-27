import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, History, Search, Printer, Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { ErrorBlock, LoadingBlock } from '@/components/StateBlock';
import { apiGet } from '@/lib/api';
import { formatDate, formatIDR } from '@/lib/format';
import { formatPaymentMethodDetail } from '@/lib/payments';
import type { AccountsPayable, AccountsReceivable } from '@/lib/types';
import { DebtPaymentDialog } from '@/components/DebtPaymentDialog';
import { DebtFormDialog } from '@/components/DebtFormDialog';
import { printReceipt } from '@/lib/receipt';

export type DebtRow = AccountsPayable | AccountsReceivable;
const labels = { unpaid: 'Belum dibayar', partial: 'Sebagian dibayar', paid: 'Lunas', void: 'Retur / Void' };
const partyName = (d: DebtRow) => 'customer_name' in d ? d.customer_name : d.supplier_name;

type CustomerReceivableSummary = {
  customer_id: string | null;
  customer_name: string;
  total_credit: number;
  total_paid: number;
  outstanding: number;
  invoice_count: number;
};

const normalizeCustomer = (name: string) => name.trim().replace(/\s+/g, ' ').toLocaleLowerCase('id-ID');

function CustomerReceivables({ onOpen }: { onOpen: (customer: CustomerReceivableSummary) => void }) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('outstanding-desc');
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ['receivables-summary'], queryFn: () => apiGet<CustomerReceivableSummary[]>('/receivables/summary/by-customer') });
  const rows = useMemo(() => {
    const result = (query.data ?? []).filter(row => normalizeCustomer(row.customer_name).includes(normalizeCustomer(search)));
    return result.sort((a, b) => {
      const nameOrder = a.customer_name.localeCompare(b.customer_name, 'id');
      if (sort === 'name') return nameOrder;
      const [field, direction] = sort.split('-') as ['outstanding' | 'total_credit' | 'total_paid', string];
      return (a[field] - b[field]) * (direction === 'asc' ? 1 : -1) || nameOrder;
    });
  }, [query.data, search, sort]);
  const pages = Math.max(1, Math.ceil(rows.length / 15));
  const current = Math.min(page, pages);
  return <section className="space-y-3" aria-label="Rekap piutang per pelanggan" data-testid="customer-receivables">
    <div><h2 className="font-heading text-lg font-semibold">Rekap per pelanggan</h2><p className="text-sm text-muted-foreground">Total seluruh nota dan cicilan pelanggan, termasuk uang muka. Nota retur atau Void tidak dihitung.</p></div>
    <div className="page-toolbar flex flex-wrap gap-3">
      <div className="min-w-0 flex-1 basis-60"><label htmlFor="customer-debt-search" className="mb-1 block text-sm">Cari pelanggan</label><Input id="customer-debt-search" data-testid="customer-debt-search" placeholder="Nama pelanggan" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} /></div>
      <div className="min-w-0 w-full sm:w-auto"><label htmlFor="customer-debt-sort" className="mb-1 block text-sm">Urutkan</label><select id="customer-debt-sort" data-testid="customer-debt-sort" className="bk-control w-full" value={sort} onChange={e => { setSort(e.target.value); setPage(1); }}><option value="outstanding-desc">Sisa piutang terbesar</option><option value="outstanding-asc">Sisa piutang terkecil</option><option value="total_credit-desc">Total kredit terbesar</option><option value="total_paid-desc">Pembayaran terbesar</option><option value="name">Nama A sampai Z</option></select></div>
    </div>
    {query.isPending ? <LoadingBlock label="Memuat rekap piutang pelanggan…" /> : query.isError ? <ErrorBlock error={query.error} onRetry={() => void query.refetch()} /> : <div className="data-table-panel bk-panel">
      <div className="overflow-x-auto"><table className="bk-table"><thead><tr><th>Pelanggan</th><th>Total kredit</th><th>Total pembayaran</th><th>Sisa piutang</th><th>Nota</th><th>Aksi</th></tr></thead><tbody>{rows.slice((current - 1) * 15, current * 15).map(row => <tr key={row.customer_id ? `id:${row.customer_id}` : `name:${normalizeCustomer(row.customer_name)}`} data-testid="customer-receivable-row"><td className="font-semibold">{row.customer_name || 'Tanpa nama'}</td><td>{formatIDR(row.total_credit)}</td><td>{formatIDR(row.total_paid)}</td><td className="font-semibold">{formatIDR(row.outstanding)}</td><td>{row.invoice_count}</td><td><Button className="min-h-11" variant="outline" onClick={() => onOpen(row)}>Lihat nota</Button></td></tr>)}</tbody></table></div>
      {rows.length === 0 && <p data-testid="empty-customer-receivables" className="p-6 text-center text-muted-foreground">{query.data?.length ? 'Tidak ada pelanggan dengan nama tersebut. Ubah pencarian untuk melihat rekap lainnya.' : 'Belum ada piutang pelanggan. Penjualan Tempo dari kasir akan tercatat di sini.'}</p>}
      <div className="page-pagination flex flex-wrap items-center justify-between gap-3 border-t border-border p-3"><span className="text-sm text-muted-foreground">{rows.length} pelanggan · halaman {current}/{pages}</span><div className="flex gap-2"><Button className="min-h-11" variant="outline" disabled={current === 1} onClick={() => setPage(current - 1)}>Sebelumnya</Button><Button className="min-h-11" variant="outline" disabled={current === pages} onClick={() => setPage(current + 1)}>Berikutnya</Button></div></div>
    </div>}
  </section>;
}

export default function DebtPage() {
  const [kind, setKind] = useState<'receivables' | 'payables'>('receivables'), [status, setStatus] = useState('all'), [aging, setAging] = useState('all'), [search, setSearch] = useState(''), [page, setPage] = useState(1);
  const [view, setView] = useState<'invoices' | 'customers'>('invoices');
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerReceivableSummary | null>(null);
  const showSummary = kind === 'receivables' && view === 'customers';
  const [payment, setPayment] = useState<DebtRow | null>(null), [history, setHistory] = useState<DebtRow | null>(null), [adding, setAdding] = useState(false), [editing, setEditing] = useState<DebtRow | null>(null);
  const client = useQueryClient();
  const query = useQuery({ queryKey: [kind], queryFn: () => apiGet<DebtRow[]>(`/${kind}`) });
  const system = useQuery({ queryKey: ['system'], queryFn: () => apiGet<{ today: string; timezone: string }>('/system') });
  const canPay = !!system.data && !system.isPending && !system.isError;
  const fallbackToday = new Date().toISOString().slice(0, 10);
  function refresh() { for (const key of ['receivables', 'receivables-summary', 'payables', 'dashboard', 'excel-report', 'excel-reports', 'monthly-report', 'books-daily', 'books-monthly']) void client.invalidateQueries({ queryKey: [key] }); }
  const rows = useMemo(() => query.data ?? [], [query.data]);
  const active = rows.filter(d => ['unpaid', 'partial'].includes(d.status));
  const filtered = useMemo(() => rows.filter(d => {
    const customerMatches = kind !== 'receivables' || !selectedCustomer || ('customer_name' in d && (selectedCustomer.customer_id ? d.customer_id === selectedCustomer.customer_id : !d.customer_id && normalizeCustomer(d.customer_name) === normalizeCustomer(selectedCustomer.customer_name)));
    return customerMatches && (status === 'all' || d.status === status) && (aging === 'all' || d.aging_bucket === aging || (aging === 'upcoming' && d.days_remaining > 0)) && `${partyName(d)} ${d.invoice_number} ${d.note || ''}`.toLowerCase().includes(search.toLowerCase());
  }), [rows, status, aging, search, kind, selectedCustomer]);
  const pages = Math.max(1, Math.ceil(filtered.length / 15)), current = Math.min(page, pages);
  return <div className="page-workspace space-y-5">
    <header className="page-heading"><div className="min-w-0"><h1 data-testid="debt-page-title" className="font-heading text-2xl font-bold">Piutang dan hutang</h1><p data-testid="debt-page-description" className="text-sm text-muted-foreground">Tagihan dari kasir tempo, stok masuk, maupun pencatatan manual beserta riwayat cicilannya.</p></div>{kind === 'receivables' ? <Button className="min-h-11" data-testid="add-receivable-button" onClick={() => setAdding(true)}><Plus />Catat piutang</Button> : <Button className="min-h-11" data-testid="add-payable-button" onClick={() => setAdding(true)}><Plus />Catat hutang</Button>}</header>
    <div className="page-tabs flex flex-wrap gap-2" aria-label="Jenis tagihan"><Button data-testid="tab-receivables" aria-pressed={kind === 'receivables'} variant={kind === 'receivables' ? 'default' : 'outline'} onClick={() => { setKind('receivables'); setPage(1); }}>Piutang pelanggan</Button><Button data-testid="tab-payables" aria-pressed={kind === 'payables'} variant={kind === 'payables' ? 'default' : 'outline'} onClick={() => { setKind('payables'); setPage(1); }}>Hutang distributor</Button></div>
    {query.data && <div className="metric-strip grid grid-cols-1 sm:grid-cols-3">{[['Sisa tagihan aktif', active.reduce((s, d) => s+d.remaining, 0)], ['Terbayar (tanpa Void)', rows.filter(d => d.status !== 'void').reduce((s, d) => s+d.paid_amount, 0)], ['Lewat jatuh tempo', active.filter(d => d.days_overdue > 0).reduce((s, d) => s+d.remaining, 0)]].map(([title, amount], i) => <div className="metric-strip-item min-w-0 p-4" key={title} data-testid={`debt-summary-${i}`}><p className="text-sm text-muted-foreground">{title}</p><strong className="font-mono text-xl block mt-2">{formatIDR(Number(amount))}</strong></div>)}</div>}
    {kind === 'receivables' && <div className="flex flex-wrap gap-2" aria-label="Tampilan piutang"><Button className="min-h-11" data-testid="receivables-view-invoices" aria-pressed={!showSummary} variant={!showSummary ? 'default' : 'outline'} onClick={() => setView('invoices')}>Per nota</Button><Button className="min-h-11" data-testid="receivables-view-customers" aria-pressed={showSummary} variant={showSummary ? 'default' : 'outline'} onClick={() => setView('customers')}>Per pelanggan</Button></div>}
    {showSummary ? <CustomerReceivables onOpen={customer => { setSelectedCustomer(customer); setView('invoices'); setSearch(''); setStatus('all'); setAging('all'); setPage(1); }} /> : <>
    {kind === 'receivables' && selectedCustomer && <div className="bk-notice flex flex-wrap items-center justify-between gap-2"><span>Nota pelanggan: <b>{selectedCustomer.customer_name || 'Tanpa nama'}</b></span><Button className="min-h-11" variant="outline" data-testid="clear-customer-filter" onClick={() => { setSelectedCustomer(null); setPage(1); }}>Lihat semua pelanggan</Button></div>}
    <section className="bk-panel p-4 space-y-3" aria-label="Umur tagihan"><h2 className="text-sm font-semibold">Pilih umur tagihan</h2><div className="flex flex-wrap gap-2">{[['all', 'Semua umur'], ['upcoming', 'Belum jatuh tempo'], ['0-30', '0–30 hari'], ['31-60', '31–60 hari'], ['61-90', '61–90 hari'], ['90+', '>90 hari']].map(([value, label]) => <Button key={value} size="sm" aria-pressed={aging === value} variant={aging === value ? 'default' : 'outline'} data-testid={`aging-filter-${value}`} onClick={() => { setAging(value); setPage(1); }}>{label}{query.data && <span className="text-xs">{formatIDR(active.filter(d => value === 'all' || (value === 'upcoming' ? d.days_remaining > 0 : d.aging_bucket === value)).reduce((s, d) => s+d.remaining, 0))}</span>}</Button>)}</div></section>
    <div className="page-toolbar flex flex-wrap gap-3"><div className="relative min-w-0 flex-1 basis-64"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input aria-label="Cari nama atau invoice tagihan" className="pl-9" data-testid="debt-search" placeholder="Cari nama atau invoice" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} /></div><select data-testid="debt-status-filter" aria-label="Filter status" className="bk-control w-full sm:max-w-48" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="all">Semua status</option>{Object.entries(labels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
    {query.isPending ? <LoadingBlock /> : query.isError ? <ErrorBlock error={query.error} onRetry={() => void query.refetch()} /> : <div className="data-table-panel bk-panel">
      <div className="overflow-x-auto"><table className="bk-table"><thead><tr><th>Invoice / Nama</th><th>Total</th><th>Bayar</th><th>Sisa</th><th>Jatuh tempo</th><th>Status</th><th>Aksi</th></tr></thead><tbody>{filtered.slice((current-1)*15, current*15).map(d => <tr key={d.id} data-testid={`debt-row-${d.id}`}><td><b>{partyName(d)}</b><small>{d.invoice_number}</small>{d.note && <small className="block text-muted-foreground" data-testid={`debt-note-${d.id}`}>{d.note}</small>}</td><td data-testid={`debt-total-${d.id}`}>{formatIDR(d.amount)}</td><td data-testid={`debt-paid-${d.id}`}>{formatIDR(d.paid_amount)}</td><td data-testid={`debt-remaining-${d.id}`} className="font-semibold">{formatIDR(d.remaining)}</td><td><span>{formatDate(d.due_date)}</span><small className={d.days_overdue > 0 ? 'text-red-700 dark:text-red-400' : ''} data-testid={`debt-aging-${d.id}`}>{d.due_label}</small></td><td data-testid={`debt-status-${d.id}`}><span className={`bk-status ${d.status}`}>{labels[d.status]}</span></td><td><div className="flex gap-2"><Button variant="outline" size="icon-sm" aria-label="Riwayat pembayaran" data-testid={`history-${d.id}`} onClick={() => setHistory(d)}><History /></Button>{d.status !== 'void' && <Button variant="outline" size="icon-sm" aria-label="Edit tagihan" data-testid={`edit-${d.id}`} onClick={() => setEditing(d)}><Pencil /></Button>}{['unpaid', 'partial'].includes(d.status) && <Button size="sm" data-testid={`pay-${d.id}`} disabled={!canPay} onClick={() => setPayment(d)}>Bayar</Button>}</div></td></tr>)}</tbody></table></div>
      {filtered.length === 0 && <p data-testid="empty-debts" className="p-8 text-center text-muted-foreground">{rows.length ? 'Tidak ada tagihan sesuai filter. Ubah pencarian, umur, atau status tagihan.' : kind === 'receivables' ? 'Belum ada piutang pelanggan. Piutang dibuat melalui kasir tempo atau tombol Catat piutang.' : 'Belum ada hutang distributor. Hutang dibuat melalui stok masuk atau tombol Catat hutang.'}</p>}
      <div className="page-pagination flex flex-wrap justify-between items-center gap-3 p-3 border-t border-border"><span data-testid="debt-pagination-info" className="text-xs text-muted-foreground">{filtered.length} tagihan · halaman {current}/{pages}</span><div className="flex gap-2"><Button size="sm" variant="outline" data-testid="debt-prev-page" disabled={current === 1} onClick={() => setPage(current-1)}>Sebelumnya</Button><Button size="sm" variant="outline" data-testid="debt-next-page" disabled={current === pages} onClick={() => setPage(current+1)}>Berikutnya</Button></div></div>
    </div>}
    {system.isPending ? <p data-testid="debt-system-loading" role="status" className="text-sm text-muted-foreground">Memuat tanggal server. Tombol Bayar tersedia setelah tanggal berhasil dimuat.</p> : system.isError ? <section data-testid="debt-system-error" className="space-y-3"><p className="text-sm text-muted-foreground">Tanggal server belum dapat dimuat, sehingga pembayaran belum bisa dicatat. Coba muat kembali tanggal server.</p><ErrorBlock error={system.error} onRetry={() => void system.refetch()} /></section> : system.data && <p data-testid="aging-server-note" className="text-xs text-muted-foreground">Umur tagihan berdasarkan server {system.data.today} ({system.data.timezone}). 0–30 termasuk jatuh tempo hari ini; lunas dan Void tidak masuk perhitungan umur.</p>}
    </>}
    {payment && system.data && <DebtPaymentDialog debt={payment} kind={kind} today={system.data.today} onClose={() => setPayment(null)} onSaved={refresh} />}
    <Dialog open={!!history} onOpenChange={o => !o && setHistory(null)}><DialogContent data-testid="payment-history-dialog"><DialogHeader><DialogTitle>Riwayat pembayaran</DialogTitle><DialogDescription>{history?.invoice_number} · {history && partyName(history)}</DialogDescription></DialogHeader>{history?.legacy_payment_history_missing && <p data-testid="legacy-payment-warning" className="bk-notice">Saldo terbayar berasal dari data lama; tanggal cicilan belum tersedia. Tidak dihitung sebagai penerimaan bulan ini.</p>}<div className="max-h-80 overflow-auto">{history?.payments.length ? history.payments.map((p, idx) => { const cum = history.payments.slice(0, idx + 1).reduce((s, x) => s + x.amount, 0); const methodText = formatPaymentMethodDetail({ method: p.method, cash_amount: p.cash_amount, transfer_amount: p.transfer_amount, transfer_method: p.transfer_method, formatMoney: formatIDR }); return <div key={p.id} data-testid={`payment-history-${p.id}`} className="flex flex-wrap justify-between items-center gap-2 border-b border-border py-3 text-sm"><div className="min-w-0 flex-1 basis-40">{formatDate(p.payment_date)}<small className="block break-words text-muted-foreground">{methodText}{p.note ? ` · ${p.note}` : ''}</small></div><div className="flex min-w-0 flex-wrap items-center gap-2"><b className="break-words font-mono">{formatIDR(p.amount)}</b><Button variant="outline" size="icon-sm" aria-label="Cetak kwitansi" data-testid={`print-receipt-${p.id}`} onClick={() => printReceipt({ kind, party: partyName(history), debt: history, payment: p, cumulativePaid: cum })}><Printer /></Button></div></div>; }) : <p data-testid="no-payment-history" className="text-sm text-muted-foreground">Belum ada riwayat cicilan bertanggal.</p>}</div></DialogContent></Dialog>
    {adding && <DebtFormDialog kind={kind} mode="create" today={system.data?.today ?? fallbackToday} onClose={() => setAdding(false)} onSaved={refresh} />}
    {editing && <DebtFormDialog kind={kind} mode="edit" debt={editing} today={system.data?.today ?? fallbackToday} onClose={() => setEditing(null)} onSaved={refresh} />}
  </div>;
}
