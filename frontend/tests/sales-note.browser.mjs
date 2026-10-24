// Run from frontend: npm install --no-save --package-lock=false playwright
// CHROME_PATH may override the locally installed browser. No production API is called.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';
import { createServer } from 'vite';

process.env.DISABLE_VISUAL_EDITS = 'true';
process.env.DISABLE_EMERGENT_OVERLAY = 'true';
const artifacts = resolve(`../test_reports/nota/excel-alignment-${Date.now()}`);
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
  assert.equal(mechanicFeeTotal([{ product: { name: 'SERVICE', service_fee: 0 }, qty: 3, price: 0.01, discount: 0 }], 0), 0.015);
  assert.equal(mechanicFeeTotal([{ product: { name: 'SERVICE', selling_price: 100000, service_fee: 0 }, qty: 2, price: 120000, discount: 10000 }], 0, true), 100000);
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
  await page.addInitScript(() => { window.print = () => {}; });
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
  const savedTransactions = [tx];
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
      data = savedTransactions;
      if (route.request().method() === 'POST') {
        submitted = route.request().postDataJSON();
        const price = 175000 + submitted.items[0].credit_surcharge;
        const qty = submitted.items[0].qty;
        const discount = submitted.items[0].discount_per_unit * qty;
        const total = price * qty - discount - submitted.discount_total;
        const dueDate = submitted.credit_term_days ? new Date(Date.parse('2026-09-29T12:00:00Z') + submitted.credit_term_days * 86400000).toISOString().slice(0, 10) : submitted.due_date;
        data = { ...tx, id: `checkout-${savedTransactions.length}`, invoice_number: `INV-TEST-${savedTransactions.length}`, payment_method: submitted.payment_method, due_date: dueDate, credit_term_days: submitted.credit_term_days,
          down_payment_amount: submitted.down_payment_amount, down_payment_method: submitted.down_payment_method, discount_total: discount + submitted.discount_total,
          total_amount: total, cash_received: submitted.cash_received, change_amount: submitted.cash_received == null ? null : submitted.cash_received - total,
          details: [{ ...tx.details[0], price, qty, discount_per_unit: submitted.items[0].discount_per_unit, discount_amount: discount, credit_surcharge: submitted.items[0].credit_surcharge, subtotal: total }] };
        savedTransactions.unshift(data);
      }
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
  });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:3101/#/transaksi');
  await page.getByTitle('Cetak Ulang Nota').click();
  const dialog = page.getByTestId('sales-note-dialog');
  await dialog.waitFor();
  const note = page.frameLocator('iframe[title="Pratinjau nota penjualan"]');
  await note.getByRole('heading', { name: 'Nota Penjualan' }).waitFor();
  await page.waitForFunction(() => !document.querySelector('[data-testid="print-receipt-btn"]').disabled);
  assert(await page.getByTestId('print-receipt-btn').isEnabled());
  assert((await note.locator('.totals').innerText()).includes('Rp100.000,00'));
  await page.evaluate(() => {
    const target = document.querySelector('iframe').contentWindow;
    target.print = () => {
      target.__printedNote = true;
      target.__printedCount = (target.__printedCount || 0) + 1;
      const rules = [...target.document.styleSheets].flatMap(sheet => [...sheet.cssRules]);
      target.__printedPageSize = rules.filter(rule => rule.cssText.startsWith('@page')).at(-1).style.getPropertyValue('size');
    };
  });
  await page.getByTestId('print-receipt-btn').click();
  await page.waitForFunction(() => document.querySelector('iframe').contentWindow.__printedCount === 1);
  assert(await page.evaluate(() => document.querySelector('iframe').contentWindow.__printedNote));
  assert.equal(await page.evaluate(() => document.querySelector('iframe').contentWindow.__printedPageSize), 'auto');
  await page.getByTestId('save-note-pdf-btn').click();
  await page.waitForFunction(() => document.querySelector('iframe').contentWindow.__printedCount === 2);
  assert.equal(await page.evaluate(() => document.querySelector('iframe').contentWindow.__printedPageSize), '241.3mm 139.7mm');
  await page.getByTestId('print-receipt-btn').click();
  await page.waitForFunction(() => document.querySelector('iframe').contentWindow.__printedCount === 3);
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
  await page.keyboard.press('Escape');
  await dialog.waitFor({ state: 'hidden' });
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto('http://127.0.0.1:3101/#/pos');
  await page.getByTestId('pos-product-card-b_0299').click();
  await page.getByTestId('cart-increment-b_0299').click();
  await page.getByTestId('checkout-panel').waitFor();
  await page.getByTestId('item-discount-p1').fill('175001');
  assert(await page.getByTestId('checkout-submit-button').isDisabled());
  await page.getByTestId('item-discount-p1').fill('5000');
  assert((await page.getByTestId('cart-total').innerText()).includes('340.000'));
  assert.equal(await page.getByTestId('checkout-discount').count(), 0);
  await page.getByTestId('checkout-cash-received').fill('100000');
  assert(await page.getByTestId('checkout-submit-button').isDisabled());
  await page.getByTestId('checkout-cash-received').fill('400000');
  assert((await page.getByTestId('checkout-change').innerText()).includes('60.000'));
  await page.getByTestId('checkout-submit-button').click();
  await page.getByTestId('sales-note-dialog').waitFor();
  assert.equal(submitted.cash_received, 400000);
  assert.equal(submitted.items[0].discount_per_unit, 5000);
  assert.equal(submitted.items[0].qty, 2);
  assert.equal(submitted.discount_total, 0);
  assert(submitted.request_id);
  assert((await note.locator('.totals').innerText()).includes('Rp60.000,00'));
  await page.getByTestId('close-receipt-btn').click();
  await page.getByTestId('pos-product-card-b_0299').click();
  await page.getByTestId('checkout-panel').waitFor();
  assert.equal(await page.getByTestId('item-discount-p1').inputValue(), '0');
  await page.getByTestId('checkout-payment-method').selectOption('edc');
  await page.getByTestId('item-discount-p1').fill('25000');
  assert((await page.getByTestId('cart-total').innerText()).includes('150.000'));
  assert.equal(await page.getByTestId('checkout-cash-received').inputValue(), '150000');
  await page.getByTestId('checkout-submit-button').click();
  await page.getByTestId('sales-note-dialog').waitFor();
  assert.equal(submitted.discount_total, 0);
  assert.equal(submitted.items[0].discount_per_unit, 25000);
  assert.equal(submitted.payment_method, 'edc');
  assert.equal(submitted.cash_received, 150000);
  assert((await note.locator('.totals').innerText()).includes('EDC'));
  await page.getByTestId('close-receipt-btn').click();
  for (const method of ['edc', 'transfer_bca', 'transfer_bri', 'transfer_bni', 'qris']) {
    await page.getByTestId('pos-product-card-b_0299').click();
    await page.getByTestId('checkout-panel').waitFor();
    await page.getByTestId('checkout-payment-method').selectOption(method);
    await page.getByTestId('item-discount-p1').fill('25000');
    const received = page.getByTestId('checkout-cash-received');
    assert.equal(await received.inputValue(), '150000');
    for (const invalid of ['', '149999', '1000000000001']) {
      await received.fill(invalid);
      assert(await page.getByTestId('checkout-submit-button').isDisabled(), `${method}: reject ${invalid}`);
      assert.equal(await received.getAttribute('aria-invalid'), 'true');
    }
    await page.getByRole('button', { name: 'Uang pas', exact: true }).click();
    assert.equal(await received.inputValue(), '150000');
    assert(await page.getByTestId('checkout-submit-button').isEnabled());
    await received.fill('200000');
    assert((await page.getByTestId('checkout-change').innerText()).includes('50.000'));
    if (method === 'transfer_bca') {
      for (const theme of ['light', 'dark']) {
        await page.evaluate(value => document.documentElement.classList.toggle('dark', value === 'dark'), theme);
        for (const width of [390, 768, 1280]) {
          await page.setViewportSize({ width, height: 1000 });
          const box = await page.getByTestId('checkout-panel').boundingBox();
          assert(box.x >= 0 && box.x + box.width <= width, `${theme}/${width}: checkout fits`);
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${theme}/${width}: no page overflow`);
          await received.focus();
          await page.keyboard.press('Tab');
          assert.equal(await page.getByRole('button', { name: 'Uang pas', exact: true }).evaluate(el => el === document.activeElement), true);
          if (width === 390) await page.screenshot({ path: resolve(artifacts, `pembayaran-transfer-${theme}-mobile.png`) });
        }
      }
      await page.evaluate(() => document.documentElement.classList.remove('dark'));
      await page.setViewportSize({ width: 1280, height: 1000 });
    }
    await page.getByTestId('checkout-submit-button').click();
    await page.getByTestId('sales-note-dialog').waitFor();
    assert.equal(submitted.payment_method, method);
    assert.equal(submitted.cash_received, 200000);
    assert((await note.locator('.totals').innerText()).includes('Rp200.000,00'));
    assert((await note.locator('.totals').innerText()).includes('Rp50.000,00'));
    const saved = savedTransactions[0];
    await page.getByTestId('close-receipt-btn').click();
    await page.goto('http://127.0.0.1:3101/#/transaksi');
    await page.getByTestId(`print-tx-btn-${saved.invoice_number.toLowerCase()}`).click();
    await page.getByTestId('sales-note-dialog').waitFor();
    assert((await note.locator('.totals').innerText()).includes('Rp200.000,00'), `${method}: reprint received amount`);
    assert((await note.locator('.totals').innerText()).includes('Rp50.000,00'), `${method}: reprint excess`);
    await page.getByTestId('close-receipt-btn').click();
    await page.goto('http://127.0.0.1:3101/#/pos');
  }
  await page.getByTestId('pos-product-card-b_0299').click();
  await page.getByTestId('payment-credit-btn').click();
  assert.equal(await page.getByTestId('checkout-cash-received').count(), 0);
  assert.equal(await page.getByTestId('item-discount-p1').count(), 0);
  assert(await page.getByTestId('checkout-payment-method').isDisabled());
  await page.getByTestId('surcharge-p1').fill('15000');
  assert((await page.getByTestId('cart-total').innerText()).includes('190.000'));
  await page.getByTestId('checkout-customer-select').selectOption('c1');
  await page.getByTestId('checkout-term-days').fill('40');
  await page.getByTestId('checkout-submit-button').click();
  await page.getByTestId('sales-note-dialog').waitFor();
  await note.getByRole('heading', { name: 'Nota Penjualan Tempo' }).waitFor();
  assert.equal(submitted.items[0].credit_surcharge, 15000);
  assert.equal(submitted.discount_total, 0);
  assert.equal(submitted.items[0].discount_per_unit, 0);
  assert.equal(submitted.credit_term_days, 40);
  assert.equal(submitted.due_date, null);
  assert.equal(submitted.down_payment_amount, 0);
  assert.equal(submitted.down_payment_method, null);
  assert.equal(submitted.cash_received, null);
  assert((await note.locator('.totals').innerText()).includes('Rp190.000,00'));
  assert((await note.locator('.recipient').innerText()).includes('08/11/2026 (40 hari)'));
  await page.getByLabel('Kertas', { exact: true }).selectOption('half');
  await page.waitForFunction(() => document.querySelector('iframe')?.contentDocument?.querySelector('style')?.textContent.includes('min-height:139.7mm'));
  const tempoHtml = await page.locator('iframe').getAttribute('srcdoc');
  const printPage = await browser.newPage();
  await printPage.setContent(tempoHtml);
  await printPage.pdf({ path: resolve(artifacts, 'nota-tempo.pdf'), preferCSSPageSize: true, displayHeaderFooter: false });
  await printPage.screenshot({ path: resolve(artifacts, 'nota-tempo.png'), fullPage: true });
  await printPage.close();
  await page.getByTestId('close-receipt-btn').click();
  await page.goto('http://127.0.0.1:3101/#/laporan-kas');
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
  assert.equal(reportParams.get('tax'), null);
  assert.equal(reportParams.get('all_tax'), 'true');
  assert.equal(reportParams.get('owner'), 'ibu');
  assert((await page.getByTestId('get-data-table').innerText()).includes('Distributor Uji'));
  await page.screenshot({ path: resolve(artifacts, 'get-data-pembelian.png'), fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS: escaped HTML, legacy/credit/returned notes, half/full/long PDF, native print and PDF controls, settings persistence, every immediate payment tender/excess and reprint, invalid-payment rejection, exact-payment reset, mobile/tablet/desktop in light/dark, keyboard input, per-unit discounts, cash-based SERVICE tempo fee.');
  console.log(`Artifacts: ${artifacts}`);
} finally {
  await browser?.close();
  await vite.close();
}
