// Run from frontend. Uses only generated notes, never the operational API.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { chromium } from 'playwright';
import { createServer } from 'vite';

process.env.DISABLE_VISUAL_EDITS = 'true';
process.env.DISABLE_EMERGENT_OVERLAY = 'true';
const artifacts = resolve('../test_reports/nota/pagination');
await mkdir(artifacts, { recursive: true });
const vite = await createServer({ server: { host: '127.0.0.1', port: 3102, strictPort: true } });
let browser;
try {
  await vite.listen();
  const { buildSalesNoteDocument, DEFAULT_NOTE_SETTINGS } = await vite.ssrLoadModule('/src/lib/sales-note.ts');
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const page = await browser.newPage();
  const tx = {
    invoice_number: 'INV-PRINT-001', date_key: '2026-09-30', status: 'completed',
    customer_name: 'Pelanggan Uji', customer_address: 'Jalan Raya Majalaya',
    due_date: '2026-10-10', total_amount: 350000, cash_received: 400000, change_amount: 50000,
    details: [{ product_sku: 'B001', product_name: 'Ban Mobil', product_size: '185/65 R15', product_brand: 'GT Radial', price: 175000, qty: 2, subtotal: 350000 }],
  };
  for (const payment_method of ['cash', 'credit']) {
    for (const paper of ['half', 'full']) {
      for (const inset of [0, 0.25]) {
        await page.setContent(buildSalesNoteDocument({ ...tx, payment_method }, { ...DEFAULT_NOTE_SETTINGS, paper }));
        const path = resolve(artifacts, `${payment_method}-${paper}-${inset}.pdf`);
        // Let the document select its paper size, like Save as PDF. Do not supply
        // width/height here: that would hide a missing CSS page size.
        if (inset) await page.addStyleTag({ content: `@page { margin: ${inset / 2}in; }` });
        await page.pdf({ path, preferCSSPageSize: true, displayHeaderFooter: false });
        const result = JSON.parse(execFileSync(resolve('../backend/venv/Scripts/python.exe'), ['-c',
          'import json,sys; from pypdf import PdfReader; r=PdfReader(sys.argv[1]); print(json.dumps({"pages":len(r.pages),"width":float(r.pages[0].mediabox.width),"height":float(r.pages[0].mediabox.height),"text":" ".join(p.extract_text() for p in r.pages)}))', path], { encoding: 'utf8' }));
        assert.equal(result.pages, 1, `${payment_method} ${paper} inset=${inset}: should fit on one page`);
        assert(Math.abs(result.width - 9.5 * 72) < 1, `Wrong PDF width: ${result.width}`);
        assert(Math.abs(result.height - (paper === 'half' ? 5.5 : 11) * 72) < 1, `Wrong PDF height: ${result.height}`);
        assert(result.text.includes('350.000'), 'Total must remain visible');
      }
    }
    const details = Array.from({ length: 50 }, (_, i) => ({ ...tx.details[0], product_name: `ITEM-${i + 1} Nama barang panjang untuk uji cetak lengkap` }));
    await page.setContent(buildSalesNoteDocument({ ...tx, payment_method, details }, DEFAULT_NOTE_SETTINGS));
    const path = resolve(artifacts, `${payment_method}-long.pdf`);
    await page.pdf({ path, preferCSSPageSize: true, displayHeaderFooter: false });
    const text = execFileSync(resolve('../backend/venv/Scripts/python.exe'), ['-c',
      'import sys; from pypdf import PdfReader; print(" ".join(p.extract_text() for p in PdfReader(sys.argv[1]).pages))', path], { encoding: 'utf8' });
    for (let i = 1; i <= 50; i++) assert(text.includes(`ITEM-${i} `), `Missing item ${i}`);
    assert(text.includes(payment_method === 'cash' ? 'Total Transaksi' : 'Total tagihan'), 'Missing final total');
  }
  console.log('PASS: cash/credit half/full notes fit one page, including reduced printable area; all 50 items and totals survive pagination.');
} finally {
  await browser?.close();
  await vite.close();
}
