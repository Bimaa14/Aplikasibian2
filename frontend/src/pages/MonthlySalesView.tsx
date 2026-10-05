import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet, fileUrl } from '@/lib/api';
import { formatIDR } from '@/lib/format';
import { PAYMENT_LABELS } from '@/lib/payments';
import type { PaymentMethod } from '@/lib/types';
import SalesFilters, { initialSalesFilters, salesFilterQuery } from '@/components/SalesFilters';
import { LoadingBlock, ErrorBlock } from '@/components/StateBlock';
import { Button } from '@/components/ui/button';

type SalesRow = { transaction_id: string; invoice_number: string; date: string; kind: string; payment_method: PaymentMethod; owner: string; category: string; tax: number | null; product_name: string; product_sku: string | null; qty: number; gross: number; discount: number; net: number };
type SalesReport = { gross: number; discount: number; net: number; tax_base: number; tax_amount: number; full_tax_base: number; tax_summary_row_limit: number; tax_eligible_line_count: number; unassigned_tax_net: number; transaction_count: number; line_count: number; page: number; page_size: number; rows: SalesRow[]; groups: Pick<SalesRow, 'owner' | 'category' | 'tax' | 'gross' | 'discount' | 'net'>[] };
const ownerName = (owner: string) => ({ bian: 'Bian', ibu: 'Ibu', unassigned: 'Belum ditandai' })[owner] || owner;

export default function MonthlySalesView() {
  const [filters, setFilters] = useState(initialSalesFilters);
  const [page, setPage] = useState(1);
  const params = salesFilterQuery(filters);
  const query = useQuery({ queryKey: ['monthly-sales', params, page], queryFn: () => apiGet<SalesReport>(`/books/sales?${params}&page=${page}`) });
  const report = query.data;
  return <div className="space-y-4">
    <SalesFilters value={filters} onChange={value => { setFilters(value); setPage(1); }} />
    <p className="text-xs leading-relaxed text-muted-foreground">Penjualan mengikuti harga dan potongan per unit. Retur mengurangi nilai pada bulan retur. Dasar Get Data Excel memakai tunai TAX = 1 dan tempo kategori Tire pada harga tunai. Estimasi PPh 0,5% ditampilkan terpisah dari tagihan pelanggan.</p>
    {query.isPending ? <LoadingBlock /> : query.isError ? <ErrorBlock error={query.error} onRetry={() => void query.refetch()} /> : report && <>
      <div className="metric-strip grid sm:grid-cols-2 xl:grid-cols-4">
        {([['Penjualan sebelum potongan', report.gross], ['Potongan per item', report.discount], ['Penjualan bersih', report.net], ['Estimasi PPh Get Data (0,5%)', report.tax_amount]] as const).map(([label, amount], index) => <div key={label} className="metric-strip-item min-w-0 p-4" data-testid={`monthly-sales-summary-${index}`}><p className="text-sm text-muted-foreground">{label}</p><strong className={`mt-2 block font-mono text-lg ${index === 2 ? 'font-bold' : ''}`}>{formatIDR(amount)}</strong></div>)}
      </div>
      {report.unassigned_tax_net !== 0 && <p className="bk-notice">Penjualan tunai {formatIDR(report.unassigned_tax_net)} belum memiliki TAX dan tidak masuk Get Data Excel. Mengubah produk hanya berlaku untuk transaksi berikutnya.</p>}
      {report.tax_eligible_line_count > report.tax_summary_row_limit && <p className="bk-notice">Dasar Get Data memakai {report.tax_summary_row_limit} baris pertama sesuai Excel. Total seluruh {report.tax_eligible_line_count} baris yang memenuhi aturan: {formatIDR(report.full_tax_base)}.</p>}
      <div className="section-heading flex flex-wrap items-center justify-between gap-3 text-sm">
        <span>{report.transaction_count} transaksi unik · {report.line_count} baris penjualan/retur · dasar pajak {formatIDR(report.tax_base)}</span>
        <a data-testid="monthly-sales-download-csv" className="inline-flex min-h-11 items-center rounded-md border border-border bg-card px-4 py-2 font-medium" href={fileUrl(`/books/sales/csv?${params}`)}>Unduh CSV sesuai filter</a>
      </div>
      <div className="data-table-panel bk-panel overflow-x-auto"><table className="bk-table" data-testid="monthly-sales-table">
        <thead><tr><th>Tanggal / Nota</th><th>Barang</th><th>Pemilik</th><th>Kategori / TAX</th><th>Pembayaran</th><th>Qty</th><th>Sebelum potongan</th><th>Potongan</th><th>Bersih</th></tr></thead>
        <tbody>{report.rows.map((row, index) => <tr key={`${row.transaction_id}-${row.kind}-${index}`}>
          <td>{row.date}<small>{row.invoice_number}{row.kind === 'return' ? ' · Retur' : ''}</small></td>
          <td>{row.product_name}<small>{row.product_sku || '-'}</small></td><td>{ownerName(row.owner)}</td>
          <td>{row.category}<small>TAX {row.tax ?? 'belum ditandai'}</small></td><td>{PAYMENT_LABELS[row.payment_method]}</td><td>{row.qty}</td>
          <td>{formatIDR(row.gross)}</td><td>{formatIDR(row.discount)}</td><td>{formatIDR(row.net)}</td>
        </tr>)}</tbody>
      </table>{!report.rows.length && <p data-testid="monthly-sales-empty" className="p-8 text-center text-sm text-muted-foreground">Tidak ada transaksi sesuai filter. Ubah periode atau pemilik untuk melihat transaksi lain.</p>}</div>
      <div className="page-pagination flex flex-wrap items-center justify-between gap-3"><span className="text-xs text-muted-foreground">Halaman {page} / {Math.max(1, Math.ceil(report.line_count / report.page_size))}</span><div className="flex gap-2">
        <Button data-testid="monthly-sales-prev" variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Sebelumnya</Button>
        <Button data-testid="monthly-sales-next" variant="outline" size="sm" disabled={page * report.page_size >= report.line_count} onClick={() => setPage(page + 1)}>Berikutnya</Button>
      </div></div>
      <section className="data-table-panel bk-panel"><h2 className="section-heading border-b border-border p-4 font-heading text-base font-semibold">Ringkasan pemilik dan kategori</h2><div className="overflow-x-auto"><table data-testid="monthly-sales-groups" className="bk-table"><thead><tr><th>Pemilik</th><th>Kategori</th><th>TAX</th><th>Penjualan bersih</th></tr></thead><tbody>
        {report.groups.map(row => <tr key={`${row.owner}-${row.category}-${row.tax}`}><td>{ownerName(row.owner)}</td><td>{row.category}</td><td>{row.tax ?? 'Belum ditandai'}</td><td>{formatIDR(row.net)}</td></tr>)}
      </tbody></table>{!report.groups.length && <p className="p-6 text-sm text-muted-foreground">Belum ada kelompok penjualan untuk filter ini.</p>}</div></section>
    </>}
  </div>;
}
