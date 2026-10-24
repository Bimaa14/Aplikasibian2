import { formatDate, formatIDR } from './format';

export type DailyPrintReport = {
  date: string;
  cash_sales: number;
  receivable_payments: number;
  receivable_profit?: number;
  transfer_payments: number;
  transfer_breakdown?: Record<string, number>;
  montir_fee: number;
  expenses: number;
  net_cash: number;
  modal_bian: number;
  laba_bian: number;
  final_cash: number;
  modal: number;
  laba: number;
  spooring: number;
  oil_revenue: number;
  oil_benefit: number;
};

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
const money = (amount: number) => escapeHtml(formatIDR(amount));

export function buildDailyReportDocument(report: DailyPrintReport): string {
  const row = (label: string, amount: number, strong = false) => `<tr${strong ? ' class="total"' : ''}><th scope="row">${escapeHtml(label)}</th><td>${money(amount)}</td></tr>`;
  const methods: Record<string, string> = { transfer_bca: 'BCA', transfer_bri: 'BRI', transfer_danamon: 'DANAMON', transfer_bni: 'BNI', edc: 'EDC', qris: 'QRIS' };
  const transfers = report.transfer_breakdown ?? {};
  const knownTotal = Object.keys(methods).reduce((sum, method) => sum + (transfers[method] ?? 0), 0);
  const otherTotal = Math.round((report.transfer_payments - knownTotal) * 100) / 100;
  return `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Laporan Harian ${escapeHtml(report.date)}</title><style>
    @page { size: auto; margin: 8mm; }
    * { box-sizing: border-box; text-shadow: none; -webkit-text-stroke-width: 0; }
    html, body { margin: 0; padding: 0; color: #111; background: #fff; font-family: Arial, sans-serif; font-size: 9.5pt; line-height: 1.15; font-synthesis: none; }
    .report { width: 100%; margin: 0 auto; break-inside: avoid; }
    header { display: flex; justify-content: space-between; align-items: flex-end; gap: 4mm; padding-bottom: 2mm; border-bottom: 1.5pt solid #111; }
    h1 { margin: 0 0 1mm; font-size: 14pt; } header p { margin: 0; } .date { text-align: right; white-space: nowrap; }
    .columns { display: grid; grid-template-columns: minmax(0, 1.18fr) minmax(0, 1fr); gap: 4mm; margin-top: 2.5mm; }
    h2 { margin: 0; padding: 1mm 1.5mm; font-size: 9.5pt; border: 1pt solid #111; border-bottom: 0; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 2mm; font-variant-numeric: tabular-nums; }
    th, td { border: .5pt solid #666; padding: .8mm 1.5mm; vertical-align: top; font-weight: 400; }
    th { text-align: left; overflow-wrap: anywhere; } td { width: 46%; text-align: right; white-space: nowrap; }
    .total th, .total td { font-weight: 700; border-top: 1pt solid #111; }
    @media print { .report { break-inside: avoid; } }
  </style></head><body><article class="report" aria-label="Laporan harian ringkas">
    <header><div><h1>Perkasa Jaya</h1><p>Laporan kas harian</p></div><p class="date">${escapeHtml(formatDate(report.date))}</p></header>
    <div class="columns"><section><h2>Perhitungan kas</h2><table><tbody>
      ${row('Penjualan langsung tanpa oli', report.cash_sales)}
      ${row('Pembayaran piutang', report.receivable_payments)}
      ${row('Jumlah penerimaan', report.cash_sales + report.receivable_payments, true)}
      ${row('Transfer / EDC / QRIS', -report.transfer_payments)}
      ${row('Pengeluaran kasir', -report.expenses)}
      ${row('Komisi montir', -report.montir_fee)}
      ${row('Kas bersih sebelum Bian', report.net_cash, true)}
      ${row('Modal Bian', -report.modal_bian)}
      ${row('Laba Bian', -report.laba_bian)}
      ${row('Kas bersih akhir', report.final_cash, true)}
    </tbody></table></section><section><h2>Rincian modal dan laba</h2><table><tbody>
      ${row('Modal toko', report.modal)}
      ${row('Laba toko', report.laba)}
      ${row('Termasuk laba piutang', report.receivable_profit ?? 0)}
      ${row('Spooring / Service', report.spooring)}
      ${row('Pendapatan oli', report.oil_revenue)}
      ${row('Laba oli', report.oil_benefit)}
    </tbody></table><h2>Rincian nontunai</h2><table><tbody>
      ${Object.entries(methods).map(([method, label]) => row(label, transfers[method] ?? 0)).join('')}
      ${otherTotal !== 0 ? row('Transfer lainnya', otherTotal) : ''}
      ${row('Total nontunai', report.transfer_payments, true)}
    </tbody></table></section></div>
  </article></body></html>`;
}

export async function printDailyReport(report: DailyPrintReport): Promise<void> {
  document.querySelectorAll('iframe[data-daily-report-print]').forEach(frame => frame.remove());
  const frame = document.createElement('iframe');
  frame.dataset.dailyReportPrint = 'true';
  frame.title = 'Cetak laporan kas harian';
  frame.setAttribute('aria-hidden', 'true');
  frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:800px;height:1000px;border:0';
  await new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => { frame.remove(); reject(new Error('Laporan belum siap dicetak. Coba cetak kembali.')); }, 15000);
    frame.onload = async () => {
      try {
        if (!frame.contentWindow || !frame.contentDocument) throw new Error('Dokumen cetak tidak dapat dibuka.');
        await frame.contentDocument.fonts.ready;
        window.clearTimeout(timeout);
        frame.contentWindow.addEventListener('afterprint', () => frame.remove(), { once: true });
        frame.contentWindow.focus();
        frame.contentWindow.print();
        resolve();
      } catch (error) { window.clearTimeout(timeout); frame.remove(); reject(error); }
    };
    frame.srcdoc = buildDailyReportDocument(report);
    document.body.append(frame);
  });
}
