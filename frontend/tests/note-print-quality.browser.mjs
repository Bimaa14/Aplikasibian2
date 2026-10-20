// Generated fixtures only; this check never calls the operational API or a physical printer.
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { mkdir, realpath, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { chromium } from 'playwright';
import { createServer } from 'vite';

process.env.DISABLE_VISUAL_EDITS = 'true';
process.env.DISABLE_EMERGENT_OVERLAY = 'true';
const artifacts = resolve(`../test_reports/nota/print-quality-${Date.now()}`);
const pythonRelativePath = process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python';
const python = process.env.PYTHON || ['../backend/venv', '../backend/.venv', '../.venv']
  .map(directory => resolve(directory, pythonRelativePath)).find(existsSync)
  || (process.platform === 'win32' ? 'python' : 'python3');
const windowsChrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const chrome = process.env.CHROME_PATH || (process.platform === 'win32' && existsSync(windowsChrome) ? windowsChrome : undefined);
const port = Number(process.env.NOTE_TEST_PORT || 3103);
await mkdir(artifacts, { recursive: true });
const dependencyDirectory = await realpath(resolve('node_modules'));
const vite = await createServer({ server: { host: '127.0.0.1', port, strictPort: true,
  fs: { allow: [process.cwd(), dependencyDirectory] } } });
let browser;

function inspectPdf(path) {
  return JSON.parse(execFileSync(python, ['-c',
    `import json,sys
from pypdf import PdfReader
r=PdfReader(sys.argv[1])
fonts=set()
images=0
for page in r.pages:
    resources=page['/Resources']
    for font in resources.get('/Font',{}).values():
        fonts.add(str(font.get_object().get('/BaseFont','')))
    for item in resources.get('/XObject',{}).values():
        images+=item.get_object().get('/Subtype')=='/Image'
print(json.dumps({'pages':len(r.pages),'width':float(r.pages[0].mediabox.width),'height':float(r.pages[0].mediabox.height),'text':' '.join(p.extract_text() for p in r.pages),'fonts':sorted(fonts),'images':images}))`,
    path], { encoding: 'utf8' }));
}

try {
  await vite.listen();
  const { buildSalesNoteDocument, DEFAULT_NOTE_SETTINGS } = await vite.ssrLoadModule('/src/lib/sales-note.ts');
  browser = await chromium.launch({ executablePath: chrome, headless: true });
  const page = await browser.newPage({ viewport: { width: 1000, height: 1200 } });
  const tx = {
    invoice_number: 'INV-PRINT-UJI', date_key: '2026-10-07', status: 'completed', customer_name: 'Pelanggan Uji',
    customer_address: 'Alamat pelanggan untuk uji', due_date: '2026-10-10', total_amount: 410000,
    cash_received: 500000, change_amount: 90000, discount_total: 25000,
    details: [
      { product_sku: 'B_0299', product_name: 'Spooring', price: 175000, qty: 1, subtotal: 150000 },
      { product_sku: 'B_0305', product_name: 'Baut Camber', price: 250000, qty: 1, subtotal: 250000 },
      { product_sku: 'B_0306', product_name: 'Balancing', price: 5000, qty: 2, subtotal: 10000 },
    ],
  };

  for (const payment_method of ['cash', 'transfer_bca', 'credit']) {
    for (const paper of ['half', 'full']) {
      for (const inset of [0, 0.25]) {
        const html = buildSalesNoteDocument({ ...tx, payment_method }, { ...DEFAULT_NOTE_SETTINGS, paper });
        await page.setContent(html);
        await page.evaluate(() => document.fonts.ready);
        const typography = await page.locator('tbody td.number').first().evaluate(element => {
          const body = getComputedStyle(document.body);
          const text = getComputedStyle(element);
          return { weight: text.fontWeight, size: parseFloat(text.fontSize), stroke: text.webkitTextStrokeWidth,
            transform: body.transform, filter: text.filter, shadow: text.textShadow };
        });
        assert.equal(typography.weight, '400');
        assert(typography.size >= 13.3, JSON.stringify(typography));
        assert.equal(typography.stroke, '0px');
        assert.equal(typography.transform, 'none');
        assert.equal(typography.filter, 'none');
        assert.equal(typography.shadow, 'none');
        if (payment_method !== 'credit') {
          const bank = page.getByRole('region', { name: 'Rekening pembayaran' });
          assert.deepEqual(await bank.locator('p').allTextContents(), ['Bank BCA', '3761155405', 'A.N Wati Wulandari']);
          const bankBounds = await bank.boundingBox();
          const tableBounds = await page.locator('table').boundingBox();
          const totalsBounds = await page.locator('.totals').boundingBox();
          assert(Math.abs(bankBounds.x - tableBounds.x) < 1, 'The account must align with the left edge of the note');
          assert(bankBounds.y >= tableBounds.y + tableBounds.height, 'The account must stay below the items');
          assert(bankBounds.x < totalsBounds.x, 'The account must stay on the left of the totals');
          assert(bankBounds.y + bankBounds.height <= (paper === 'half' ? 528 : 1056) - 22, 'The account must fit above the bottom margin');
        }
        if (inset) await page.addStyleTag({ content: `@page { margin: ${inset / 2}in; }` });
        const path = resolve(artifacts, `${payment_method}-${paper}-${inset}.pdf`);
        await page.pdf({ path, preferCSSPageSize: true, displayHeaderFooter: false });
        const result = inspectPdf(path);
        assert.equal(result.pages, 1, `${payment_method} ${paper} inset=${inset}`);
        assert(Math.abs(result.width - 684) < 1);
        assert(Math.abs(result.height - (paper === 'half' ? 396 : 792)) < 1);
        assert(result.fonts.length > 0, 'The PDF must contain native text fonts');
        assert.equal(result.images, 0, 'Receipt text must not be rasterized');
        if (payment_method !== 'credit') {
          assert.equal((result.text.match(/3761155405/g) || []).length, 1, 'Print the bank account once');
          assert(result.text.includes('Bank BCA') && result.text.includes('A.N Wati Wulandari'));
        }
        for (const item of tx.details) assert(result.text.includes(item.product_name));
        assert(result.text.includes('410.000,00'));
        if (payment_method !== 'credit') {
          assert(result.text.includes('500.000,00') && result.text.includes('90.000,00'));
          assert(result.text.includes(payment_method === 'cash' ? 'Kembalian' : 'Kelebihan pembayaran'));
        } else assert(!result.text.includes('Jumlah diterima'));
        if (paper === 'half' && !inset) {
          await page.screenshot({ path: resolve(artifacts, `${payment_method}-half.png`), clip: { x: 0, y: 0, width: 913, height: 528 } });
          await writeFile(resolve(artifacts, `${payment_method}-half.html`), html);
        }
      }
    }
  }

  for (const payment_method of ['cash', 'edc', 'transfer_bca', 'transfer_bri', 'transfer_bni', 'qris']) {
    const html = buildSalesNoteDocument({ ...tx, payment_method, cash_received: null, change_amount: null }, DEFAULT_NOTE_SETTINGS);
    await page.setContent(html);
    const totals = await page.locator('.totals').innerText();
    assert.equal((totals.match(/410\.000,00/g) || []).length, 1, 'Legacy receipts must not invent received amounts');
    assert.equal((totals.match(/Tidak tercatat/g) || []).length, 2);
  }

  for (const payment_method of ['cash', 'credit']) {
    const details = Array.from({ length: 50 }, (_, index) => ({ ...tx.details[0], product_name: `ITEM-${index + 1} Nama barang panjang untuk uji cetak lengkap` }));
    await page.setContent(buildSalesNoteDocument({ ...tx, payment_method, details }, DEFAULT_NOTE_SETTINGS));
    const path = resolve(artifacts, `${payment_method}-long.pdf`);
    await page.pdf({ path, preferCSSPageSize: true, displayHeaderFooter: false });
    const result = inspectPdf(path);
    for (let item = 1; item <= 50; item++) assert(result.text.includes(`ITEM-${item} `), `Missing ${payment_method} item ${item}`);
    assert(result.text.includes(payment_method === 'cash' ? 'Total Transaksi' : 'Total tagihan'));
    if (payment_method === 'cash') assert.equal((result.text.match(/3761155405/g) || []).length, 1, 'Long notes must retain one bank account footer');
    assert.equal(result.images, 0);
  }

  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let data = [];
    if (path === '/api/auth/me') data = { id: 'printer-test', name: 'Kasir Uji', username: 'printer-test', role: 'admin' };
    if (path === '/api/system') data = { today: '2026-10-07', timezone: 'Asia/Jakarta' };
    if (path === '/api/transactions') data = [{ ...tx, id: 'printer-fixture', date: '2026-10-07T03:00:00Z', payment_method: 'cash', due_date: null }];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.goto(`http://127.0.0.1:${port}/#/transaksi`);
  const reprint = page.getByTitle('Cetak Ulang Nota');
  const print = page.getByTestId('print-receipt-btn');
  const ready = () => page.waitForFunction(() => document.querySelector('[data-testid="print-receipt-btn"]')?.disabled === false);
  await reprint.click();
  await ready();
  await page.evaluate(() => {
    window.__printCalls = 0;
    const target = document.querySelector('iframe').contentWindow;
    target.print = () => { window.__printCalls += 1; };
    Object.defineProperty(target.document.fonts, 'ready', { value: new Promise(resolve => { window.__releasePrintFonts = resolve; }) });
  });
  await print.click();
  await page.waitForFunction(() => document.querySelector('[data-testid="print-receipt-btn"]')?.disabled === true);
  await page.getByTestId('close-receipt-btn').click();
  await page.getByTestId('sales-note-dialog').waitFor({ state: 'hidden' });
  await page.evaluate(() => window.__releasePrintFonts());
  await reprint.click();
  await ready();
  assert.equal(await page.evaluate(() => window.__printCalls), 0, 'A closed note must not open a stale print dialog');

  // Delayed animation frames exercise the bounded timer fallback during close/reopen.
  await page.evaluate(async () => {
    window.__originalRaf = window.requestAnimationFrame;
    window.requestAnimationFrame = callback => window.__originalRaf(() => {
      window.setTimeout(() => callback(performance.now()), 200);
    });
    document.querySelector('iframe').contentWindow.print = () => { window.__printCalls += 1; };
    document.querySelector('[data-testid="print-receipt-btn"]').click();
    await Promise.resolve();
    document.querySelector('[data-testid="close-receipt-btn"]').click();
  });
  await page.getByTestId('sales-note-dialog').waitFor({ state: 'hidden' });
  await reprint.click();
  await ready();
  await page.evaluate(() => { document.querySelector('iframe').contentWindow.print = () => { window.__printCalls += 1; }; });
  await print.click();
  await page.waitForFunction(() => window.__printCalls === 1);
  await ready();
  await page.evaluate(() => { window.requestAnimationFrame = window.__originalRaf; });
  await page.getByTestId('close-receipt-btn').click();
  assert.deepEqual(errors, []);

  console.log('PASS: regular native text without stroke/filter/scaling, 10pt+ prices, exact BCA account at bottom left, cash/transfer/credit half/full single-page PDFs including reduced print area, actual received/excess amounts, unknown legacy fields, complete 50-item pagination, close/reopen cancellation and delayed-frame timeout recovery. Physical printing was not tested.');
  console.log(`Artifacts: ${artifacts}`);
} finally {
  await browser?.close();
  await vite.close();
}
