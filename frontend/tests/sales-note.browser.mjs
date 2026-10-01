// Run from frontend: npm install --no-save --package-lock=false playwright
// CHROME_PATH may override the locally installed browser. No production API is called.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';
import { createServer } from 'vite';

process.env.DISABLE_VISUAL_EDITS = 'true';
process.env.DISABLE_EMERGENT_OVERLAY = 'true';
const artifacts = resolve('../test_reports/nota');
await mkdir(artifacts, { recursive: true });
const vite = await createServer({ server: { host: '127.0.0.1', port: 3101, strictPort: true } });
let browser;
try {
  await vite.listen();
  const { buildSalesNoteDocument, DEFAULT_NOTE_SETTINGS } = await vite.ssrLoadModule('/src/lib/sales-note.ts');
  const { mechanicFeeTotal } = await vite.ssrLoadModule('/src/lib/pos-pricing.ts');
  assert.equal(mechanicFeeTotal([
    { product: { name: ' Service ', service_fee: 999 }, qty: 1, price: 150000, discount: 30000 },
    { product: { name: 'SPOORING', service_fee: 10000 }, qty: 1, price: 150000, discount: 30000 },
  ], 10000), 67500);
  assert.equal(mechanicFeeTotal([{ product: { name: 'SERVICE', service_fee: 0 }, qty: 3, price: 0.01, discount: 0 }], 0), 0.02);
  const tx = {
    id: 'note-test', invoice_number: 'INV-260929-0001', date: '2026-09-29T03:00:00Z', date_key: '2026-09-29',
    payment_method: 'cash', status: 'completed', total_amount: 400000, cash_received: 500000, change_amount: 100000,
    customer_name: 'Pelanggan Contoh', vehicle_plate: 'D 1234 AB', due_date: null,
    details: [
      { id: 'd1', product_id: 'p1', product_sku: 'B_0299', product_name: 'Spooring', price: 175000, qty: 1, subtotal: 150000 },
      { id: 'd2', product_id: 'p2', product_sku: 'B_0305', product_name: 'Baut Camber', price: 250000, qty: 1, subtotal: 250000 },
    ],
  };
  const html = buildSalesNoteDocument(tx, DEFAULT_NOTE_SETTINGS);
  assert(html.includes('size: 241.3mm 139.7mm;'));
  assert(html.includes('Rp25.000,00') && html.includes('Rp100.000,00'));
  const hostile = buildSalesNoteDocument({ ...tx, customer_name: '<img src=x onerror=alert(1)>' }, DEFAULT_NOTE_SETTINGS);
  assert(!hostile.includes('<img src=x'));
  assert(!html.includes('<img'));
  assert(hostile.includes('&lt;img'));
  const old = buildSalesNoteDocument({ ...tx, cash_received: null, change_amount: null }, DEFAULT_NOTE_SETTINGS);
  assert(old.includes('tidak tercatat'));
  const credit = buildSalesNoteDocument({ ...tx, payment_method: 'credit', due_date: '2026-10-10' }, DEFAULT_NOTE_SETTINGS);
  assert(credit.includes('10/10/2026') && !credit.includes('Kembalian :'));
  const returned = buildSalesNoteDocument({ ...tx, status: 'returned' }, DEFAULT_NOTE_SETTINGS);
  assert(returned.includes('NOTA DIBATALKAN'));
  browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  await page.setContent(html);
  assert.equal(await page.locator('.store-logo').count(), 0);
  await page.screenshot({ path: resolve(artifacts, 'nota-contoh.png'), clip: { x: 0, y: 0, width: 913, height: 529 } });
  await page.pdf({ path: resolve(artifacts, 'nota-setengah.pdf'), preferCSSPageSize: true, displayHeaderFooter: false });
  await writeFile(resolve(artifacts, 'nota-contoh.html'), html);
  await page.setContent(buildSalesNoteDocument(tx, { ...DEFAULT_NOTE_SETTINGS, paper: 'full' }));
  await page.pdf({ path: resolve(artifacts, 'nota-penuh.pdf'), preferCSSPageSize: true, displayHeaderFooter: false });
  const long = { ...tx, details: Array.from({ length: 50 }, (_, i) => ({ ...tx.details[0], id: `line-${i}`, product_name: `BARANG-${i + 1} Nama barang panjang untuk memastikan baris tetap terbaca seluruhnya`, subtotal: 150000 })) };
  long.total_amount = 7500000;
  long.cash_received = 8000000;
  long.change_amount = 500000;
  await page.setContent(buildSalesNoteDocument(long, DEFAULT_NOTE_SETTINGS));
  await page.pdf({ path: resolve(artifacts, 'nota-banyak-barang.pdf'), preferCSSPageSize: true, displayHeaderFooter: false });

  let submitted;
  let reportParams;
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let data = [];
    if (path === '/api/auth/me') data = { id: 'test', name: 'Kasir Uji', username: 'test', role: 'admin' };
    if (path === '/api/system') data = { today: '2026-09-29', timezone: 'Asia/Jakarta' };
    if (path === '/api/customers') data = [{ id: 'c1', name: 'Pelanggan Uji', phone: '', address: '' }];
    if (path === '/api/products') data = [{ id: 'p1', type: 'barang', sku: 'B_0299', name: 'Spooring', stock: 10, selling_price: 175000, cost_price: 0, service_fee: 0, brand: '', size: '', owner: 'bian', category: 'TIRE' }];
    if (path === '/api/books/daily') data = { date: '2026-09-29', cash_sales: 0, non_cash_sales: 0, receivable_payments: 0, transfer_payments: 0, montir_fee: 0, expenses: 0, net_cash: 0, months_available: [] };
    if (path === '/api/books/get-data') {
      reportParams = new URL(route.request().url()).searchParams;
      data = { total: 10000, tax_base: 10000, pph_final: reportParams.get('report') === 'purchases' ? null : 50, count: 1, page: 1, page_size: 25, notice: 'PPN kosong sesuai sumber', filename: 'Store.xlsx',
        rows: [{ date: '2026-09-01', invoice_date: '2026-08-31', item: 'Ban Uji', invoice: 'FAKTUR-1', amount: 10000, amount_without_vat: null, vat_amount: null, party: 'Distributor Uji', source_sheet: 'PURCHASE', source_row: 2 }] };
    }
    if (path === '/api/books/sales') {
      reportParams = new URL(route.request().url()).searchParams;
      data = { gross: 175000, discount: 25000, net: 150000, tax_base: 150000, tax_amount: 750, unassigned_tax_net: 0, transaction_count: 1, line_count: 1, page: 1, page_size: 25, groups: [],
        rows: [{ transaction_id: 'test', invoice_number: 'INV-TEST', date: '2026-09-29', kind: 'sale', payment_method: 'edc', owner: 'bian', category: 'TIRE', tax: 1, product_name: 'Ban Uji', product_sku: 'B001', qty: 1, gross: 175000, discount: 25000, net: 150000 }] };
    }
    if (path === '/api/transactions') {
      data = [tx];
      if (route.request().method() === 'POST') {
        submitted = route.request().postDataJSON();
        const price = 175000 + submitted.items[0].credit_surcharge;
        const total = price - submitted.items[0].discount_amount - submitted.discount_total;
        data = { ...tx, payment_method: submitted.payment_method, due_date: submitted.due_date, discount_total: submitted.discount_total,
          total_amount: total, cash_received: submitted.cash_received, change_amount: submitted.cash_received == null ? null : submitted.cash_received - total,
          details: [{ ...tx.details[0], price, credit_surcharge: submitted.items[0].credit_surcharge, subtotal: total }] };
      }
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:3101/transaksi');
  await page.getByTitle('Cetak Ulang Nota').click();
  const dialog = page.getByTestId('sales-note-dialog');
  await dialog.waitFor();
  const note = page.frameLocator('iframe[title="Pratinjau nota penjualan"]');
  await note.getByRole('heading', { name: 'Nota Penjualan' }).waitFor();
  assert(await page.getByTestId('print-receipt-btn').isEnabled());
  assert((await note.locator('.totals').innerText()).includes('Rp100.000,00'));
  await page.evaluate(() => {
    const target = document.querySelector('iframe').contentWindow;
    target.print = () => {
      target.__printedNote = true;
      const rules = [...target.document.styleSheets].flatMap(sheet => [...sheet.cssRules]);
      target.__printedPageSize = rules.filter(rule => rule.cssText.startsWith('@page')).at(-1).style.getPropertyValue('size');
    };
  });
  await page.getByTestId('print-receipt-btn').click();
  assert(await page.evaluate(() => document.querySelector('iframe').contentWindow.__printedNote));
  assert.equal(await page.evaluate(() => document.querySelector('iframe').contentWindow.__printedPageSize), 'auto');
  await page.getByTestId('save-note-pdf-btn').click();
  assert.equal(await page.evaluate(() => document.querySelector('iframe').contentWindow.__printedPageSize), '241.3mm 139.7mm');
  await page.getByTestId('print-receipt-btn').click();
  assert.equal(await page.evaluate(() => document.querySelector('iframe').contentWindow.__printedPageSize), 'auto');
  await page.getByRole('button', { name: 'Identitas toko' }).click();
  await page.getByLabel('Telepon / HP').fill('Telepon toko contoh');
  await note.getByText('Telepon toko contoh').waitFor();
  await page.getByRole('button', { name: 'Identitas toko' }).click();
  await page.screenshot({ path: resolve(artifacts, 'nota-dialog.png') });
  await page.getByLabel('Kertas', { exact: true }).selectOption('full');
  await page.waitForFunction(() => document.querySelector('iframe')?.contentDocument?.querySelector('style')?.textContent.includes('279.4mm'));
  await page.getByTestId('close-receipt-btn').click();
  await page.reload();
  await page.getByTitle('Cetak Ulang Nota').click();
  assert.equal(await page.getByLabel('Kertas', { exact: true }).inputValue(), 'full');
  await note.getByText('Telepon toko contoh').waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  const geometry = await dialog.boundingBox();
  assert(geometry.x >= 0 && geometry.x + geometry.width <= 390, JSON.stringify(geometry));
  await page.screenshot({ path: resolve(artifacts, 'nota-mobile.png') });
  assert(await page.getByTestId('print-receipt-btn').isVisible());
  await page.getByTestId('close-receipt-btn').click();
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto('http://127.0.0.1:3101/pos');
  await page.getByTestId('pos-product-card-b_0299').click();
  await page.getByTestId('cart-checkout-button').click();
  await page.getByTestId('item-discount-p1').fill('175001');
  assert(await page.getByTestId('checkout-submit-button').isDisabled());
  await page.getByTestId('item-discount-p1').fill('5000');
  assert((await page.getByTestId('checkout-net-total').innerText()).includes('170.000'));
  await page.getByTestId('checkout-cash-received').fill('100000');
  assert(await page.getByTestId('checkout-submit-button').isDisabled());
  await page.getByTestId('checkout-cash-received').fill('200000');
  assert((await page.getByTestId('checkout-change').innerText()).includes('30.000'));
  await page.getByTestId('checkout-submit-button').click();
  await page.getByTestId('sales-note-dialog').waitFor();
  assert.equal(submitted.cash_received, 200000);
  assert.equal(submitted.items[0].discount_amount, 5000);
  assert(submitted.request_id);
  assert((await note.locator('.totals').innerText()).includes('Rp30.000,00'));
  await page.getByTestId('close-receipt-btn').click();
  await page.getByTestId('pos-product-card-b_0299').click();
  await page.getByTestId('cart-checkout-button').click();
  assert.equal(await page.getByTestId('item-discount-p1').inputValue(), '0');
  await page.getByTestId('checkout-payment-method').selectOption('edc');
  await page.getByTestId('checkout-discount').fill('25000');
  assert((await page.getByTestId('checkout-net-total').innerText()).includes('150.000'));
  assert.equal(await page.getByTestId('checkout-cash-received').count(), 0);
  await page.getByTestId('checkout-submit-button').click();
  await page.getByTestId('sales-note-dialog').waitFor();
  assert.equal(submitted.discount_total, 25000);
  assert.equal(submitted.payment_method, 'edc');
  assert.equal(submitted.cash_received, null);
  assert((await note.locator('.totals').innerText()).includes('EDC'));
  await page.getByTestId('close-receipt-btn').click();
  await page.getByTestId('pos-product-card-b_0299').click();
  await page.getByTestId('cart-checkout-button').click();
  await page.getByTestId('checkout-payment-method').selectOption('credit');
  await page.getByLabel('Tambahan tempo Spooring').fill('15000');
  await page.getByTestId('checkout-discount').fill('10000');
  assert((await page.getByTestId('checkout-net-total').innerText()).includes('180.000'));
  await page.getByTestId('checkout-customer-select').click();
  await page.getByRole('option', { name: 'Pelanggan Uji' }).click();
  await page.getByTestId('checkout-due-date-input').fill('2099-10-10');
  await page.getByTestId('checkout-submit-button').click();
  await page.getByTestId('sales-note-dialog').waitFor();
  await note.getByRole('heading', { name: 'Nota Penjualan Tempo' }).waitFor();
  assert.equal(submitted.items[0].credit_surcharge, 15000);
  assert.equal(submitted.discount_total, 10000);
  assert((await note.locator('.totals').innerText()).includes('Rp180.000,00'));
  await page.getByLabel('Kertas', { exact: true }).selectOption('half');
  await page.waitForFunction(() => document.querySelector('iframe')?.contentDocument?.querySelector('style')?.textContent.includes('min-height:139.7mm'));
  const tempoHtml = await page.locator('iframe').getAttribute('srcdoc');
  const printPage = await browser.newPage();
  await printPage.setContent(tempoHtml);
  await printPage.pdf({ path: resolve(artifacts, 'nota-tempo.pdf'), preferCSSPageSize: true, displayHeaderFooter: false });
  await printPage.screenshot({ path: resolve(artifacts, 'nota-tempo.png'), fullPage: true });
  await printPage.close();
  await page.getByTestId('close-receipt-btn').click();
  await page.goto('http://127.0.0.1:3101/laporan-kas');
  await page.getByRole('button', { name: 'Transaksi Bulanan' }).click();
  await page.getByTestId('monthly-sales-table').waitFor();
  await page.getByLabel('Bulan laporan').fill('2026-09');
  await page.getByLabel('Pemilik laporan').selectOption('bian');
  await page.getByLabel('Kategori laporan').selectOption('TIRE');
  await page.getByLabel('TAX laporan').selectOption('1');
  await page.getByLabel('Pembayaran laporan').selectOption('edc');
  await page.getByTestId('monthly-sales-table').waitFor();
  assert.equal(reportParams.get('month'), '2026-09');
  assert.equal(reportParams.get('owner'), 'bian');
  assert.equal(reportParams.get('category'), 'TIRE');
  assert.equal(reportParams.get('tax'), '1');
  assert.equal(reportParams.get('payment_method'), 'edc');
  const csvUrl = new URL(await page.getByRole('link', { name: 'Unduh CSV sesuai filter' }).getAttribute('href'), page.url());
  assert.equal(csvUrl.searchParams.get('tax'), '1');
  assert.equal(csvUrl.searchParams.get('owner'), 'bian');
  await page.screenshot({ path: resolve(artifacts, 'laporan-filter.png'), fullPage: true });
  await page.getByTestId('books-tab-get-data').click();
  await page.getByTestId('get-data-table').waitFor();
  await page.getByLabel('Jenis report').selectOption('purchases');
  await page.getByLabel('Bulan Get Data').fill('2026-08');
  await page.getByLabel('Pemilik Get Data').selectOption('ibu');
  await page.getByLabel('Sumber Get Data').selectOption('preview');
  await page.getByTestId('get-data-submit').click();
  await page.getByTestId('get-data-table').waitFor();
  assert.equal(reportParams.get('report'), 'purchases');
  assert.equal(reportParams.get('month'), '2026-08');
  assert.equal(reportParams.get('tax'), '1');
  assert.equal(reportParams.get('owner'), 'ibu');
  assert((await page.getByTestId('get-data-table').innerText()).includes('Distributor Uji'));
  await page.screenshot({ path: resolve(artifacts, 'get-data-pembelian.png'), fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS: escaped HTML, legacy/credit/returned notes, half/full/long PDF, reprint, settings persistence, mobile, POS tender/change, EDC invoice discount, custom tempo price and credit note.');
  console.log(`Artifacts: ${artifacts}`);
} finally {
  await browser?.close();
  await vite.close();
}
