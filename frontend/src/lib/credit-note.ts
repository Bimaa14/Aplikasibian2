import type { Transaction } from './types';
import type { NoteSettings } from './sales-note';

const esc = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
const money = (value: number) => new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 2 }).format(value).replace(/\s/g, '');

/** Credit form based on the customer's printed book; independent of the cash note. */
export function buildCreditNote(transaction: Transaction, settings: NoteSettings) {
  const width = '241.3mm';
  const height = settings.paper === 'full' ? '279.4mm' : '139.7mm';
  const rows = transaction.details.map(line => `<tr><td class="center">${esc(line.qty)}</td><td>${esc(line.product_size || line.product_name)}${line.product_size ? `<small>${esc(line.product_name)}</small>` : ''}</td><td>${esc(line.product_brand || '—')}</td><td class="number">${money(line.price)}</td><td class="number">${money(line.subtotal)}</td></tr>`).join('');
  const blanks = Math.max(0, (settings.paper === 'full' ? 20 : 3) - transaction.details.length);
  const discount = transaction.discount_total ?? 0;
  return `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Nota Tempo ${esc(transaction.invoice_number)}</title><style>
    @page { size: ${width} ${height}; margin: 0; }
    * { box-sizing: border-box; } html { color-scheme: light; background: white; }
    body { width:${width}; min-height:${height}; margin:0; padding:6mm 18mm; color:#000; background:white; font:700 11pt/1.16 Arial,sans-serif; -webkit-text-stroke:.3pt #000; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
    header { display:grid; grid-template-columns: 1.55fr 1fr; gap:7mm; margin-bottom:2mm; }
    h1 { font-size:18pt; margin:0 0 1mm; text-transform:uppercase; letter-spacing:.3mm; }
    .store { text-align:center; } .store p { margin:.4mm 0; } .recipient p { margin:.6mm 0; overflow-wrap:anywhere; }
    .recipient { padding-top:2mm; } h2 { font-size:11pt; margin:1mm 0; }
    table { width:100%; border-collapse:collapse; table-layout:fixed; } th { font-weight:700; font-size:10pt; border-top:4px double; border-bottom:4px double; }
    th,td { border-left:1.4px solid; border-right:1.4px solid; padding:1.3mm; overflow-wrap:anywhere; } td { border-bottom:1.4px solid; vertical-align:top; font-weight:700; }
    th:first-child,td:first-child { border-left:0; } th:last-child,td:last-child { border-right:0; }
    tr { break-inside:avoid; } thead { display:table-header-group; } small { display:block; font-size:8pt; margin-top:1mm; }
    .center { text-align:center; } .number { text-align:right; font-variant-numeric:tabular-nums; } .blank td { height:7mm; }
    .bottom { break-inside:avoid; padding-top:2mm; } .summary { display:flex; justify-content:space-between; gap:8mm; align-items:start; }
    .totals { min-width:75mm; } .totals div { display:flex; justify-content:space-between; gap:4mm; margin-bottom:1mm; } .totals dt,.totals dd { margin:0; }
    .signatures { display:grid; grid-template-columns:1fr 1fr; gap:30mm; text-align:center; margin-top:3mm; align-items:start; }
    .signature { padding-top:10mm; }
    .notice { font-size:8pt; max-width:110mm; margin:0; } .void { border:2px solid; padding:1mm; text-align:center; margin-bottom:2mm; }
    @media print { html { height:auto; } body { width:auto; height:auto; min-height:0; padding:6mm 18mm; overflow:visible; } }
  </style></head><body>
  ${transaction.status === 'returned' ? '<p class="void">TRANSAKSI DIRETUR — NOTA DIBATALKAN</p>' : ''}
  <header><div class="store"><h1>${esc(settings.name)}</h1><p>SEDIA BAN BARU DAN VULKANISIR</p><p>SPOORING, BALANCE, NITROGEN, OLI<br>DAN SERVICE KAKI-KAKI</p><p>${esc(settings.address)}</p>${settings.phone ? `<p>${esc(settings.phone)}</p>` : ''}</div>
  <div class="recipient"><p>Majalaya, ${esc(transaction.date_key.split('-').reverse().join('/'))}</p><p>Kepada Yth. ${esc(transaction.customer_name || '—')}</p>${transaction.customer_address ? `<p>${esc(transaction.customer_address)}</p>` : ''}<h2>Nota Penjualan Tempo</h2><p>No. ${esc(transaction.invoice_number)}</p><p>Jatuh tempo: ${esc(transaction.due_date?.split('-').reverse().join('/') || '—')}</p></div></header>
  <table aria-label="Rincian nota tempo"><colgroup><col style="width:12%"><col style="width:32%"><col style="width:18%"><col style="width:18%"><col style="width:20%"></colgroup><thead><tr><th>BANYAKNYA</th><th>UKURAN</th><th>MERK</th><th>SATUAN</th><th>TOTAL</th></tr></thead><tbody>${rows}${'<tr class="blank"><td></td><td></td><td></td><td></td><td></td></tr>'.repeat(blanks)}</tbody></table>
  <section class="bottom"><div class="summary"><p class="notice">Harga satuan sudah termasuk tambahan tempo. ${discount > 0 ? 'Total sudah setelah potongan item dan nota. ' : ''}Nota ini mencatat tagihan awal. Pembayaran dicatat pada kwitansi terpisah.</p><dl class="totals">${discount > 0 ? `<div><dt>Potongan nota</dt><dd>${money(discount)}</dd></div>` : ''}<div><dt><b>Total tagihan</b></dt><dd><b>${money(transaction.total_amount)}</b></dd></div></dl></div>
  <div class="signatures"><div>Tanda Terima,<div class="signature">( ................................ )</div></div><div>Hormat Kami,<div class="signature">( ................................ )</div></div></div></section>
  </body></html>`;
}
