import React, { useMemo, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, ChevronLeft, ChevronRight, Clock3, Plus, Search, Wallet, CircleCheck, SlidersHorizontal } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { csv, Debt, download, rupiah, statusLabel, useLoad } from '../lib';
import { DueLabel, EmptyState, ExportButton, LoadState, Metric, PageHeading, Status } from '../components/Common';
import { DebtForm } from '../components/DebtForm';
import { DebtDetail } from '../components/DebtDetail';
import { PaymentDialog } from '../components/PaymentDialog';

export default function DebtPage({ kind }: { kind: 'receivable' | 'payable' }) {
  const receivable = kind === 'receivable';
  const { today }: any = useOutletContext();
  const [params, setParams] = useSearchParams();
  const { data, loading, error, reload } = useLoad<Debt[]>(`/debts?kind=${kind}`);
  const [query, setQuery] = useState(''), [status, setStatus] = useState('all'), [page, setPage] = useState(1);
  const [create, setCreate] = useState(false), [selected, setSelected] = useState<Debt | null>(null), [paying, setPaying] = useState<Debt | null>(null);
  const bucket = params.get('aging') || 'all';
  const rows = data || [];
  const active = rows.filter(d => ['unpaid', 'partial'].includes(d.status));
  const remaining = active.reduce((s, d) => s + d.remaining, 0);
  const filtered = useMemo(() => (data || []).filter(d => {
    const match = `${d.party} ${d.reference}`.toLowerCase().includes(query.toLowerCase());
    return match && (status === 'all' || status === d.status) && (bucket === 'all' || d.aging_bucket === bucket || (bucket === 'upcoming' && d.days_remaining > 0));
  }), [data, status, bucket, query]);
  const maxPage = Math.max(1, Math.ceil(filtered.length / 8));
  const current = Math.min(page, maxPage);
  const changeBucket = (value: string) => { setParams(value === 'all' ? {} : { aging: value }); setPage(1); };
  function exportRows() {
    download(`${receivable ? 'piutang' : 'hutang'}-perkasa-jaya.csv`, csv([['Invoice', receivable ? 'Pelanggan' : 'Supplier', 'Tanggal', 'Jatuh tempo', 'Total', 'Terbayar', 'Sisa', 'Status', 'Hari terlambat'], ...filtered.map(d => [d.reference, d.party, d.issued_date, d.due_date, d.total, d.paid_amount, d.remaining, statusLabel[d.status], d.days_overdue])]));
  }
  return <div className="page-enter"><PageHeading title={receivable ? 'Piutang pelanggan' : 'Hutang supplier'} description={receivable ? 'Pantau tagihan pelanggan. Setiap cicilan tercatat, setiap rupiah terhitung.' : 'Kelola kewajiban supplier dan jaga pembayaran tetap tepat waktu.'}><ExportButton onClick={exportRows} /><Button className="btn-primary" data-testid="add-debt-button" onClick={() => setCreate(true)} disabled={!today}><Plus size={17} />Tambah {receivable ? 'piutang' : 'hutang'}</Button></PageHeading>
    <LoadState {...{ loading, error, reload }} />{!loading && !error && <>
      <div className="metrics-grid"><Metric title={`Sisa ${receivable ? 'piutang' : 'hutang'} aktif`} value={remaining} note={`${active.length} tagihan belum selesai`} icon={receivable ? ArrowDownLeft : ArrowUpRight} id="debt-outstanding" /><Metric title="Pembayaran tercatat" value={rows.filter(d => d.status !== 'void').reduce((s, d) => s + d.paid_amount, 0)} note="Akumulasi cicilan · tanpa retur" icon={CircleCheck} tone="green" id="debt-paid" /><Metric title="Lewat jatuh tempo" value={active.filter(d => d.days_overdue > 0).reduce((s, d) => s + d.remaining, 0)} note={`${active.filter(d => d.days_overdue > 0).length} tagihan perlu ditindaklanjuti`} icon={Clock3} tone="orange" id="debt-overdue" /><Metric title="Jatuh tempo hari ini" value={active.filter(d => d.days_remaining === 0).reduce((s, d) => s + d.remaining, 0)} note="Berdasarkan tanggal server" icon={Wallet} tone="slate" id="debt-due-today" /></div>
      <div className="aging-filter"><div className="aging-filter-label" data-testid="aging-filter-label"><Clock3 size={17} /><strong>Umur tagihan</strong><small>Sejak jatuh tempo</small></div>{[['all', 'Semua'], ['upcoming', 'Belum jatuh tempo'], ['0-30', '0–30 hari'], ['31-60', '31–60 hari'], ['61-90', '61–90 hari'], ['90+', '>90 hari']].map(([value, label]) => <button key={value} className={`aging-filter-button ${bucket === value ? 'selected' : ''}`} data-testid={`aging-filter-${value}`} onClick={() => changeBucket(value)}><span>{label}</span><b>{rupiah(active.filter(d => value === 'all' || (value === 'upcoming' ? d.days_remaining > 0 : d.aging_bucket === value)).reduce((s, d) => s + d.remaining, 0))}</b></button>)}</div>
      <section className="panel debt-panel"><div className="panel-title"><div><h2 data-testid="debt-list-title">Daftar {receivable ? 'piutang' : 'hutang'} <span className="count-pill">{rows.length}</span></h2><p data-testid="debt-list-description">Seluruh tagihan dan progres pembayarannya.</p></div><span className="small-muted" data-testid="debt-currency">Dalam Rupiah (IDR)</span></div>
        <div className="table-toolbar"><label className="search-input"><Search size={17} /><input data-testid="debt-search" aria-label="Cari nama atau invoice" placeholder={`Cari ${receivable ? 'pelanggan' : 'supplier'} atau nomor invoice…`} value={query} onChange={e => { setQuery(e.target.value); setPage(1); }} /></label><label className="status-filter"><SlidersHorizontal size={15} /><select data-testid="debt-status-filter" aria-label="Filter status" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="all">Semua status</option>{Object.entries(statusLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></div>
        {filtered.length === 0 ? <EmptyState title={rows.length === 0 ? `Belum ada ${receivable ? 'piutang' : 'hutang'} tercatat` : 'Tidak ada tagihan yang cocok'} description={rows.length === 0 ? 'Mulai dengan menambahkan tagihan pertama. Total, cicilan, dan sisa akan dihitung otomatis.' : 'Coba kata kunci lain atau ubah filter tagihan.'}>{rows.length === 0 && <Button className="btn-secondary" variant="outline" data-testid="empty-add-debt" onClick={() => setCreate(true)} disabled={!today}><Plus size={15} />Tambah tagihan pertama</Button>}</EmptyState> : <>
          <div className="table-container"><table className="data-table"><thead><tr data-testid="debt-table-header"><th>{receivable ? 'PELANGGAN / INVOICE' : 'SUPPLIER / INVOICE'}</th><th>JATUH TEMPO</th><th className="numeric">TOTAL</th><th className="numeric">TERBAYAR</th><th className="numeric">SISA</th><th>STATUS</th><th /></tr></thead><tbody>{filtered.slice((current - 1) * 8, current * 8).map(d => <tr key={d.id} data-testid={`debt-row-${d.id}`} className={d.status === 'void' ? 'void-row' : ''}><td><button className="table-party" data-testid={`debt-detail-${d.id}`} onClick={() => setSelected(d)}>{d.party}<small>{d.reference}</small></button></td><td><DueLabel debt={d} /></td><td className="numeric" data-testid={`debt-total-${d.id}`}>{rupiah(d.total)}</td><td className="numeric paid-amount" data-testid={`debt-paid-${d.id}`}>{rupiah(d.paid_amount)}</td><td className="numeric bold" data-testid={`debt-remaining-${d.id}`}>{rupiah(d.remaining)}</td><td><Status status={d.status} id={d.id} /></td><td>{['unpaid', 'partial'].includes(d.status) ? <Button variant="outline" size="sm" className="pay-button" data-testid={`pay-debt-${d.id}`} onClick={() => setPaying(d)}>Bayar <ArrowUpRight size={13} /></Button> : <Button variant="ghost" size="sm" data-testid={`view-debt-${d.id}`} onClick={() => setSelected(d)}>Detail</Button>}</td></tr>)}</tbody></table></div>
          <div className="pagination"><span data-testid="debt-results-count">Menampilkan {(current - 1) * 8 + 1}–{Math.min(current * 8, filtered.length)} dari {filtered.length} tagihan</span><div><Button variant="outline" size="icon" data-testid="previous-debt-page" aria-label="Halaman sebelumnya" disabled={current <= 1} onClick={() => setPage(current - 1)}><ChevronLeft size={15} /></Button><span data-testid="current-debt-page">{current} / {maxPage}</span><Button variant="outline" size="icon" data-testid="next-debt-page" aria-label="Halaman berikutnya" disabled={current >= maxPage} onClick={() => setPage(current + 1)}><ChevronRight size={15} /></Button></div></div>
        </>}
      </section><p className="footnote" data-testid="aging-footnote">Aging menggunakan tanggal server ({today}, Asia/Jakarta). Bucket 0–30 mencakup tagihan yang jatuh tempo hari ini; tagihan lunas dan retur tidak ikut dihitung.</p>
    </>}
    {create && <DebtForm kind={kind} today={today} onClose={() => setCreate(false)} onSave={reload} />}{selected && <DebtDetail debt={selected} onClose={() => setSelected(null)} onSave={reload} onPay={() => { setPaying(selected); setSelected(null); }} />}{paying && <PaymentDialog debt={paying} today={today} onClose={() => setPaying(null)} onSave={reload} />}
  </div>;
}