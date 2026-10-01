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
type SalesReport = { gross: number; discount: number; net: number; tax_base: number; tax_amount: number; unassigned_tax_net: number; transaction_count: number; line_count: number; page: number; page_size: number; rows: SalesRow[]; groups: Pick<SalesRow, 'owner' | 'category' | 'tax' | 'gross' | 'discount' | 'net'>[] };
const ownerName = (owner: string) => ({ bian: 'Bian', ibu: 'Ibu', unassigned: 'Belum ditandai' })[owner] || owner;

export default function MonthlySalesView() {
  const [filters, setFilters] = useState(initialSalesFilters);
  const [page, setPage] = useState(1);
  const params = salesFilterQuery(filters);
  const query = useQuery({ queryKey: ['monthly-sales', params, page], queryFn: () => apiGet<SalesReport>(`/books/sales?${params}&page=${page}`) });
  const report = query.data;
  return <div className="space-y-4">
    <SalesFilters value={filters} onChange={value => { setFilters(value); setPage(1); }} />
    <p className="text-xs leading-relaxed text-muted-foreground">Angka hanya mencakup item yang cocok dengan filter, setelah potongan nota. Retur mengurangi nilai pada bulan retur. Pajak 0,5% hanya untuk TAX = 1 dan tidak ditambahkan ke tagihan pelanggan.</p>
    {query.isPending ? <LoadingBlock /> : query.isError ? <ErrorBlock error={query.error} onRetry={() => void query.refetch()} /> : report && <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {([['Penjualan sebelum potongan', report.gross], ['Potongan nota', report.discount], ['Penjualan bersih', report.net], ['Pajak TAX = 1 (0,5%)', report.tax_amount]] as const).map(([label, amount]) => <div key={label} className="bk-panel p-4"><p className="text-xs text-muted-foreground">{label}</p><strong className="mt-2 block font-mono text-lg">{formatIDR(amount)}</strong></div>)}
      </div>
      {report.unassigned_tax_net !== 0 && <p className="bk-notice">Nilai {formatIDR(report.unassigned_tax_net)} belum memiliki atribut TAX pada transaksi dan tidak masuk dasar pajak. Mengubah produk hanya berlaku untuk transaksi berikutnya.</p>}
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>{report.transaction_count} transaksi unik · {report.line_count} baris penjualan/retur · dasar pajak {formatIDR(report.tax_base)}</span>
        <a className="rounded-md border border-border bg-card px-3 py-2" href={fileUrl(`/books/sales/csv?${params}`)}>Unduh CSV sesuai filter</a>
      </div>
      <div className="bk-panel overflow-x-auto"><table className="bk-table" data-testid="monthly-sales-table">
        <thead><tr><th>Tanggal / Nota</th><th>Barang</th><th>Pemilik</th><th>Kategori / TAX</th><th>Pembayaran</th><th>Qty</th><th>Sebelum potongan</th><th>Potongan</th><th>Bersih</th></tr></thead>
        <tbody>{report.rows.map((row, index) => <tr key={`${row.transaction_id}-${row.kind}-${index}`}>
          <td>{row.date}<small>{row.invoice_number}{row.kind === 'return' ? ' · Retur' : ''}</small></td>
          <td>{row.product_name}<small>{row.product_sku || '—'}</small></td><td>{ownerName(row.owner)}</td>
          <td>{row.category}<small>TAX {row.tax ?? 'belum ditandai'}</small></td><td>{PAYMENT_LABELS[row.payment_method]}</td><td>{row.qty}</td>
          <td>{formatIDR(row.gross)}</td><td>{formatIDR(row.discount)}</td><td>{formatIDR(row.net)}</td>
        </tr>)}</tbody>
      </table>{!report.rows.length && <p className="p-8 text-center text-sm text-muted-foreground">Tidak ada transaksi sesuai filter.</p>}</div>
      <div className="flex items-center justify-between"><span className="text-xs text-muted-foreground">Halaman {page} / {Math.max(1, Math.ceil(report.line_count / report.page_size))}</span><div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Sebelumnya</Button>
        <Button variant="outline" size="sm" disabled={page * report.page_size >= report.line_count} onClick={() => setPage(page + 1)}>Berikutnya</Button>
      </div></div>
      <div className="bk-panel overflow-x-auto"><table className="bk-table"><thead><tr><th>Pemilik</th><th>Kategori</th><th>TAX</th><th>Penjualan bersih</th></tr></thead><tbody>
        {report.groups.map(row => <tr key={`${row.owner}-${row.category}-${row.tax}`}><td>{ownerName(row.owner)}</td><td>{row.category}</td><td>{row.tax ?? 'Belum ditandai'}</td><td>{formatIDR(row.net)}</td></tr>)}
      </tbody></table></div>
    </>}
  </div>;
}
