import React, { useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, Banknote, Plus, Search } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { csv, dateLabel, download, initialMonth, rupiah, useLoad } from '../lib';
import { EmptyState, ExportButton, LoadState, Metric, MonthPicker, PageHeading } from '../components/Common';
import { EntryForm } from '../components/EntryForm';

const labels = { sale: 'Penjualan tunai', expense: 'Operasional', supplier_payment: 'Pembelian supplier', receivable: 'Pembayaran piutang', payable: 'Pembayaran hutang', refund: 'Pengembalian retur' };

export default function EntriesPage() {
  const [month, setMonth] = useState(initialMonth), [query, setQuery] = useState('');
  const { today }: any = useOutletContext();
  const [params, setParams] = useSearchParams();
  const { data, loading, error, reload } = useLoad(`/reports?month=${month}`);
  const activities = (data?.activities || []).filter((a: any) => a.label.toLowerCase().includes(query.toLowerCase()));
  function exportRows() { download(`catatan-kas-${month}.csv`, csv([['Tanggal', 'Keterangan', 'Jenis', 'Kas masuk', 'Kas keluar'], ...activities.map((a: any) => [a.date, a.label, labels[a.type], a.direction === 'in' ? a.amount : 0, a.direction === 'out' ? a.amount : 0])])); }
  return <div className="page-enter"><PageHeading title="Catatan kas" description="Semua uang masuk dan keluar, tersusun dalam satu catatan."><MonthPicker {...{ month, setMonth }} /><Button className="btn-primary" data-testid="add-entry-button" disabled={!today} onClick={() => setParams({ new: '1' })}><Plus size={17} />Catat transaksi</Button></PageHeading><LoadState {...{ loading, error, reload }} />
    {!loading && !error && data && <><div className="metrics-grid three"><Metric title="Total kas masuk" value={data.cash.income} note="Penjualan tunai + pembayaran piutang" icon={ArrowDownLeft} tone="green" id="entries-in" /><Metric title="Total kas keluar" value={data.cash.outgoing} note="Supplier + operasional + pengembalian" icon={ArrowUpRight} tone="orange" id="entries-out" /><Metric title="Arus kas bersih" value={data.cash.net} note="Selisih kas pada periode terpilih" icon={Banknote} tone="blue" id="entries-net" /></div>
    <section className="panel"><div className="panel-title"><div><h2 data-testid="entries-list-title">Riwayat pergerakan kas <span className="count-pill">{data.activities.length}</span></h2><p data-testid="entries-list-description">Pembayaran piutang dan hutang otomatis muncul di sini.</p></div><ExportButton onClick={exportRows} /></div><div className="table-toolbar"><label className="search-input"><Search size={17} /><input data-testid="entry-search" aria-label="Cari catatan kas" placeholder="Cari keterangan atau nama…" value={query} onChange={e => setQuery(e.target.value)} /></label></div>
    {activities.length ? <div className="table-container"><table className="data-table"><thead><tr data-testid="entries-table-header"><th>TANGGAL</th><th>KETERANGAN</th><th>JENIS</th><th className="numeric">KAS MASUK</th><th className="numeric">KAS KELUAR</th></tr></thead><tbody>{activities.map((a: any) => <tr key={a.id} data-testid={`entry-row-${a.id}`}><td>{dateLabel(a.date)}</td><td className="bold">{a.label}</td><td><span className="entry-type">{labels[a.type]}</span></td><td className="numeric paid-amount">{a.direction === 'in' ? rupiah(a.amount) : '—'}</td><td className="numeric">{a.direction === 'out' ? rupiah(a.amount) : '—'}</td></tr>)}</tbody></table></div> : <EmptyState title={query ? 'Catatan tidak ditemukan' : 'Belum ada pergerakan kas'} description={query ? 'Coba kata kunci lain.' : 'Catat penjualan tunai, pembayaran supplier, atau pengeluaran pertama pada periode ini.'}><Button variant="outline" data-testid="empty-add-entry" disabled={!today} onClick={() => setParams({ new: '1' })}><Plus size={15} />Catat transaksi</Button></EmptyState>}</section>
    <p className="footnote" data-testid="cash-recording-note">Piutang baru bukan kas masuk. Hutang baru bukan kas keluar. Hanya pembayaran nyata yang masuk catatan ini.</p></>}
    {params.get('new') === '1' && today && <EntryForm today={today} onClose={() => setParams({})} onSave={reload} />}
  </div>;
}