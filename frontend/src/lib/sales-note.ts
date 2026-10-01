import { buildCreditNote } from './credit-note';
import type { Transaction } from "./types";
import { PAYMENT_LABELS } from './payments';

export type NotePaper = "half" | "full";
export interface NoteSettings {
  name: string;
  address: string;
  phone: string;
  footer: string;
  paper: NotePaper;
}

export const DEFAULT_NOTE_SETTINGS: NoteSettings = {
  name: "Perkasa Jaya Ban",
  address: "Jalan Raya Laswi No. 1 Majalaya",
  phone: "",
  footer: "Barang yang sudah dibeli tidak dapat dikembalikan.",
  paper: "half",
};
export const NOTE_SETTINGS_KEY = "perkasa-jaya.sales-note.v1";

export function loadNoteSettings(): NoteSettings {
  try {
    const value = JSON.parse(localStorage.getItem(NOTE_SETTINGS_KEY) || "null");
    if (!value || typeof value !== "object") return { ...DEFAULT_NOTE_SETTINGS };
    return {
      name: typeof value.name === "string" ? value.name.slice(0, 80) : DEFAULT_NOTE_SETTINGS.name,
      address: typeof value.address === "string" ? value.address.slice(0, 160) : DEFAULT_NOTE_SETTINGS.address,
      phone: typeof value.phone === "string" ? value.phone.slice(0, 100) : "",
      footer: typeof value.footer === "string" ? value.footer.slice(0, 180) : DEFAULT_NOTE_SETTINGS.footer,
      paper: value.paper === "full" ? "full" : "half",
    };
  } catch {
    return { ...DEFAULT_NOTE_SETTINGS };
  }
}

const escape = (value: string | number | null | undefined) => String(value ?? "").replace(
  /[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]!,
);
const currency = new Intl.NumberFormat("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? "—" : `Rp${currency.format(value)}`;

function noteDate(value: string) {
  const date = new Date(`${value.slice(0, 10)}T12:00:00`);
  return Number.isNaN(date.getTime()) ? escape(value) : date.toLocaleDateString("id-ID", {
    weekday: "long", day: "2-digit", month: "long", year: "numeric",
  });
}

/** A standalone, offline document shared by the preview and the printer. All data is escaped. */
export function buildSalesNoteDocument(transaction: Transaction, settings: NoteSettings): string {
  if (transaction.payment_method === "credit") return buildCreditNote(transaction, settings);
  const credit = false;
  const width = "241.3mm";
  const height = settings.paper === "full" ? "279.4mm" : "139.7mm";
  // Reserve room for the credit/discount footer and the extra price annotation.
  const footerRows = credit ? 3 : (transaction.discount_total ?? 0) > 0 ? 1 : 0;
  // Keep the writing area tall like the continuous-paper reference, even for one item.
  const blankRows = Math.max(0, (settings.paper === "full" ? 40 : 16) - transaction.details.length - footerRows);
  const rows = transaction.details.map((line, index) => {
    // The stored subtotal is authoritative, including historical imported transactions.
    const discount = Math.max(0, Math.round((line.price * line.qty - line.subtotal) * 100) / 100);
    return `<tr class="item-row"><td class="center">${index + 1}</td>
      <td>${escape(line.product_sku || "—")}</td><td>${escape(line.product_name)}${credit && line.credit_surcharge ? `<br><small>Tambahan tempo/unit ${money(line.credit_surcharge)}</small>` : ''}</td>
      <td class="number">${money(line.price)}</td><td class="number">${money(discount)}</td>
      <td class="center">${escape(line.qty)}</td><td class="number">${money(line.subtotal)}</td></tr>`;
  }).join("");
  const returned = transaction.status === "returned";
  return `<!doctype html><html lang="id"><head><meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nota ${escape(transaction.invoice_number)}</title>
  <style>
    /* Use the selected form for PDF output as well as the preview. */
    @page { size: ${width} ${height}; margin: 0; }
    * { box-sizing: border-box; }
    html { color-scheme: light; background: #fff; }
    body { margin: 0; padding: 6mm 12mm; width: ${width}; min-height: ${height}; color: #000; background: #fff;
      font: 700 10pt/1.12 "Times New Roman", Times, serif; -webkit-text-stroke: .3pt #000;
      -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    thead { display: table-header-group; break-inside: avoid; }
    tr { break-inside: avoid; page-break-inside: avoid; }
    .heading { border: 0; padding: 0 0 2mm; font-weight: 700; break-inside: avoid; }
    h1 { margin: 0 0 1.5mm; text-align: center; font-size: 12pt; font-weight: bold; }
    .header-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8mm; align-items: end; }
    .meta { text-align: left; }
    .meta p, .store p { margin: 0 0 .7mm; overflow-wrap: anywhere; }
    .meta .secondary { font-size: 9pt; }
    .store { text-align: center; font-weight: bold; }
    .store-name { font-size: 11pt; }
    .status { margin: 0 0 2mm; border: 1pt solid #000; padding: 1mm; text-align: center; font-weight: bold; }
    .columns th { border: 1.1pt solid #000; padding: 1.5mm 1mm; font-size: 10pt; font-weight: 700; }
    tbody td { border-left: 1.1pt solid #000; border-right: 1.1pt solid #000; padding: .9mm 1mm; vertical-align: top; overflow-wrap: anywhere; font-weight: 700; }
    tbody tr:last-child td { border-bottom: 1.1pt solid #000; }
    .item-row { height: 4.5mm; }
    .number { text-align: left; font-variant-numeric: tabular-nums; font-size: 9pt; }
    .center { text-align: center; }
    .blank td { height: ${blankRows * 4.5}mm; padding: 0; }
    .bottom { display: grid; grid-template-columns: 1fr 79mm; gap: 5mm; padding-top: 1.5mm;
      break-inside: avoid; page-break-inside: avoid; font-weight: bold; }
    .policy { margin: 0; font-size: 9pt; overflow-wrap: anywhere; }
    .totals { margin: 0; font-size: 9pt; }
    .totals div { display: flex; flex-wrap: wrap; gap: 1mm; margin-bottom: .6mm; }
    .totals dt, .totals dd { margin: 0; }
    .totals dd { overflow-wrap: anywhere; }
    .footnote { margin: 2mm 0 0; font-size: 10pt; font-weight: 700; }
    @media print {
      html { height: auto; }
      /* The driver's printable height can be shorter than the physical form.
         Let content determine height so a short note cannot spill a blank page. */
      body { width: ${width}; max-width: 100%; height: auto; min-height: 0; padding: 6mm 12mm; overflow: visible; }
    }
  </style></head><body>
  <header class="heading">
      <h1>${credit ? 'Nota Penjualan Tempo' : 'Nota Penjualan'}</h1>
      ${returned ? '<p class="status">TRANSAKSI DIRETUR — NOTA DIBATALKAN</p>' : ""}
      <div class="header-grid"><div class="meta">
        <p><b>Nomor Transaksi : ${escape(transaction.invoice_number)}</b></p>
        <p>${escape(PAYMENT_LABELS[transaction.payment_method])}</p>
        <p>${noteDate(transaction.date_key)}</p>
        ${transaction.customer_name && transaction.customer_name !== 'Umum' || transaction.vehicle_plate ? `<p class="secondary">Pelanggan : ${escape(transaction.customer_name || "Umum")}${transaction.vehicle_plate ? ` · Nopol : ${escape(transaction.vehicle_plate)}` : ""}</p>` : ''}
      </div><div class="store"><p class="store-name">${escape(settings.name)}</p>
        ${settings.address ? `<p>${escape(settings.address)}</p>` : ""}
        ${settings.phone ? `<p>${escape(settings.phone)}</p>` : ""}
      </div></div>
  </header>
  <table aria-label="Rincian nota penjualan">
    <colgroup><col style="width:4%"><col style="width:10%"><col style="width:29%"><col style="width:16%"><col style="width:13%"><col style="width:5%"><col style="width:23%"></colgroup>
    <thead>
    <tr class="columns"><th>No</th><th>Kode</th><th>Nama Barang</th><th>Harga</th><th>Potongan</th><th>Jml</th><th>Total</th></tr></thead>
    <tbody>${rows}${blankRows ? `<tr class="blank" aria-hidden="true">${"<td></td>".repeat(7)}</tr>` : ""}</tbody>
  </table>
  <div class="bottom"><div><p class="policy">${escape(settings.footer)}</p>
    ${returned ? '<p class="footnote">Nota ini merupakan salinan transaksi yang telah diretur.</p>' : ""}
    ${transaction.payment_method === 'cash' && transaction.cash_received == null ? '<p class="footnote">Nominal uang diterima dan kembalian tidak tercatat.</p>' : ""}
    ${(transaction.discount_total ?? 0) > 0 ? '<p class="footnote">Potongan tercantum pada tiap baris. Total sudah setelah potongan.</p>' : ''}
    ${credit ? '<p class="footnote">Nota tempo adalah tagihan saat transaksi, bukan bukti pelunasan. Cicilan dicatat melalui kwitansi pembayaran.</p>' : ''}
  </div><dl class="totals">
    ${(transaction.discount_total ?? 0) > 0 ? `<div><dt>Potongan nota :</dt><dd>${money(transaction.discount_total)}</dd></div>` : ''}
    <div><dt>Total Transaksi :</dt><dd>${money(transaction.total_amount)}</dd></div>
    ${credit ? `<div><dt>Pembayaran :</dt><dd>Tempo</dd></div><div><dt>Jatuh Tempo :</dt><dd>${escape(transaction.due_date?.split("-").reverse().join("/") || "—")}</dd></div>`
      : transaction.payment_method === 'cash' ? `<div><dt>Bayar :</dt><dd>${money(transaction.cash_received)}</dd></div><div><dt>Kembalian :</dt><dd>${money(transaction.change_amount)}</dd></div>`
      : `<div><dt>Pembayaran :</dt><dd>${escape(PAYMENT_LABELS[transaction.payment_method])}</dd></div><div><dt>Terbayar :</dt><dd>${money(transaction.total_amount)}</dd></div>`}
  </dl></div>
  </body></html>`;
}
