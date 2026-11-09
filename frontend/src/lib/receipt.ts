// Kwitansi pembayaran piutang/hutang satu halaman (muat pada kertas 1/2 halaman maupun A4).
import { formatPaymentMethodDetail } from './payments';
import type { AccountsPayable, AccountsReceivable, DebtPayment } from './types';

type DebtRow = AccountsReceivable | AccountsPayable;

const satuan = ['', 'satu', 'dua', 'tiga', 'empat', 'lima', 'enam', 'tujuh', 'delapan', 'sembilan', 'sepuluh', 'sebelas'];

function terbilang(n: number): string {
  n = Math.floor(Math.abs(n));
  if (n < 12) return satuan[n];
  if (n < 20) return terbilang(n - 10) + ' belas';
  if (n < 100) return terbilang(Math.floor(n / 10)) + ' puluh' + (n % 10 ? ' ' + terbilang(n % 10) : '');
  if (n < 200) return 'seratus' + (n % 100 ? ' ' + terbilang(n % 100) : '');
  if (n < 1000) return terbilang(Math.floor(n / 100)) + ' ratus' + (n % 100 ? ' ' + terbilang(n % 100) : '');
  if (n < 2000) return 'seribu' + (n % 1000 ? ' ' + terbilang(n % 1000) : '');
  if (n < 1e6) return terbilang(Math.floor(n / 1000)) + ' ribu' + (n % 1000 ? ' ' + terbilang(n % 1000) : '');
  if (n < 1e9) return terbilang(Math.floor(n / 1e6)) + ' juta' + (n % 1e6 ? ' ' + terbilang(n % 1e6) : '');
  return terbilang(Math.floor(n / 1e9)) + ' miliar' + (n % 1e9 ? ' ' + terbilang(n % 1e9) : '');
}

const idr = (n: number) => 'Rp ' + Math.round(n).toLocaleString('id-ID');
const esc = (s: string) => (s || '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] as string));

export function buildReceiptHtml(opts: { kind: string; party: string; debt: DebtRow; payment: DebtPayment; cumulativePaid: number }): string {
  const { kind, party, debt, payment, cumulativePaid } = opts;
  const isRecv = kind === 'receivables';
  const remainingAfter = Math.max(0, debt.amount - cumulativePaid);
  const words = (terbilang(payment.amount) || 'nol').replace(/\s+/g, ' ').trim();
  const methodDetail = formatPaymentMethodDetail({
    method: payment.method,
    cash_amount: payment.cash_amount,
    transfer_amount: payment.transfer_amount,
    transfer_method: payment.transfer_method,
    formatMoney: idr,
  });
  return `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Kwitansi ${esc(debt.invoice_number)}</title>
  <style>
    @page { size: auto; margin: 4mm 8mm; }
    * { box-sizing: border-box; }
    html, body { font-family: 'Segoe UI', Arial, sans-serif; color: #111; background: #fff; margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { padding: 10px; }
    .k { max-width: 640px; margin: 0 auto; border: 1.5px solid #111; border-radius: 6px; padding: 10px 14px; break-inside: avoid; page-break-inside: avoid; page-break-after: avoid; break-after: avoid; }
    .top { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1.5px solid #111; padding-bottom: 6px; margin-bottom: 6px; }
    .brand { font-size: 16px; font-weight: 800; letter-spacing: .3px; }
    .brand small { display: block; font-weight: 500; font-size: 10px; color: #444; letter-spacing: .6px; }
    .tag { font-size: 10px; border: 1px solid #111; border-radius: 14px; padding: 2px 10px; font-weight: 700; text-transform: uppercase; }
    h1 { font-size: 13px; letter-spacing: 1.5px; text-align: center; margin: 2px 0 8px; }
    table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
    td { padding: 2.5px 4px; vertical-align: top; }
    td.l { color: #444; width: 145px; }
    .amt { margin: 8px 0; padding: 7px 10px; background: #f3f4f6; border-radius: 6px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 6px; }
    .amt .big { font-size: 18px; font-weight: 800; }
    .words { font-style: italic; text-transform: capitalize; font-size: 11px; color: #333; }
    .foot { display: flex; justify-content: space-between; align-items: flex-end; margin-top: 10px; font-size: 11px; }
    .sign { text-align: center; width: 180px; }
    .sign .line { margin-top: 24px; border-top: 1px solid #111; padding-top: 3px; }
    .note { font-size: 10px; color: #555; text-align: left; max-width: 340px; }
    @media print {
      html, body { height: auto; min-height: 0; max-height: 128mm; overflow: hidden; padding: 0; }
      .k { border-color: #000; }
    }
  </style></head><body>
  <div class="k">
    <div class="top">
      <div class="brand">Bengkel Perkasa Jaya<small>PERKASA JAYA · BAN &amp; SERVIS OTOMOTIF</small></div>
      <span class="tag">Kwitansi ${isRecv ? 'Piutang' : 'Hutang'}</span>
    </div>
    <h1>KWITANSI PEMBAYARAN</h1>
    <table>
      <tr><td class="l">No. Kwitansi</td><td>: ${esc(payment.id).slice(0, 8).toUpperCase()}</td></tr>
      <tr><td class="l">Tanggal</td><td>: ${esc(payment.payment_date)}</td></tr>
      <tr><td class="l">${isRecv ? 'Diterima dari' : 'Dibayarkan kepada'}</td><td>: <b>${esc(party) || '-'}</b></td></tr>
      <tr><td class="l">No. Invoice/Faktur</td><td>: ${esc(debt.invoice_number) || '-'}</td></tr>
      <tr><td class="l">Metode</td><td>: ${esc(methodDetail)}${payment.note ? ' · ' + esc(payment.note) : ''}</td></tr>
    </table>
    <div class="amt">
      <div class="big">${idr(payment.amount)}</div>
      <div class="words">Terbilang: ${words} rupiah</div>
    </div>
    <table>
      <tr><td class="l">Total tagihan</td><td>: ${idr(debt.amount)}</td></tr>
      <tr><td class="l">Total dibayar</td><td>: ${idr(cumulativePaid)}</td></tr>
      <tr><td class="l">Sisa tagihan</td><td>: <b>${idr(remainingAfter)}</b></td></tr>
    </table>
    <div class="foot">
      <div class="note">Kwitansi sah tanpa tanda tangan basah bila dicetak dari sistem.<br/>Simpan sebagai bukti pembayaran.</div>
      <div class="sign"><div>Hormat kami,</div><div class="line">Bengkel Perkasa Jaya</div></div>
    </div>
  </div>
  <script>window.onload=function(){window.print()}</script>
  </body></html>`;
}

export function printReceipt(opts: { kind: string; party: string; debt: DebtRow; payment: DebtPayment; cumulativePaid: number }) {
  const html = buildReceiptHtml(opts);
  const w = window.open('', '_blank', 'width=720,height=640');
  if (!w) return false;
  w.document.open();
  w.document.write(html);
  w.document.close();
  return true;
}
