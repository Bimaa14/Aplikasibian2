// Kwitansi pembayaran piutang/hutang yang bisa dicetak (buka jendela baru + print).
import type { AccountsPayable, AccountsReceivable, DebtPayment } from '@/lib/types';

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

export function printReceipt(opts: { kind: string; party: string; debt: DebtRow; payment: DebtPayment; cumulativePaid: number }) {
  const { kind, party, debt, payment, cumulativePaid } = opts;
  const isRecv = kind === 'receivables';
  const remainingAfter = Math.max(0, debt.amount - cumulativePaid);
  const words = (terbilang(payment.amount) || 'nol').replace(/\s+/g, ' ').trim();
  const html = `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Kwitansi ${esc(debt.invoice_number)}</title>
  <style>
    *{box-sizing:border-box} body{font-family:'Segoe UI',Arial,sans-serif;color:#111;margin:0;padding:24px}
    .k{max-width:640px;margin:0 auto;border:2px solid #111;border-radius:10px;padding:22px 26px}
    .top{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #111;padding-bottom:12px;margin-bottom:16px}
    .brand{font-size:22px;font-weight:800;letter-spacing:.5px}
    .brand small{display:block;font-weight:500;font-size:11px;color:#555;letter-spacing:1px}
    .tag{font-size:11px;border:1px solid #111;border-radius:20px;padding:3px 12px;font-weight:700;text-transform:uppercase}
    h1{font-size:15px;letter-spacing:2px;text-align:center;margin:4px 0 18px}
    table{width:100%;border-collapse:collapse;font-size:13px}
    td{padding:6px 4px;vertical-align:top}
    td.l{color:#555;width:150px}
    .amt{margin:16px 0;padding:12px 14px;background:#f3f4f6;border-radius:8px}
    .amt .big{font-size:24px;font-weight:800}
    .words{font-style:italic;text-transform:capitalize;font-size:12px;color:#333;margin-top:4px}
    .foot{display:flex;justify-content:space-between;margin-top:26px;font-size:12px}
    .sign{text-align:center;width:200px}
    .sign .line{margin-top:52px;border-top:1px solid #111;padding-top:4px}
    .note{margin-top:14px;font-size:11px;color:#666;text-align:center}
    @media print{body{padding:0}.k{border-color:#000}}
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
      <tr><td class="l">Metode</td><td>: ${payment.method === 'transfer' ? 'Transfer' : 'Tunai'}${payment.note ? ' · ' + esc(payment.note) : ''}</td></tr>
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
  const w = window.open('', '_blank', 'width=720,height=800');
  if (!w) return false;
  w.document.open();
  w.document.write(html);
  w.document.close();
  return true;
}
