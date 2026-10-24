import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';
import { createServer } from 'vite';

process.env.DISABLE_VISUAL_EDITS = 'true';
process.env.DISABLE_EMERGENT_OVERLAY = 'true';
const artifacts = resolve('../test_reports/revision-20261024');
const origin = 'http://127.0.0.1:3214';
const scenarioFilter = process.argv.find(argument => argument.startsWith('--scenario='))?.slice('--scenario='.length).toLowerCase();
const results = { passed: [], failed: [], clicks: [], consoleErrors: [], pageErrors: [], unknownApi: [], pdfs: [], contrast: [] };
await mkdir(artifacts, { recursive: true });
const vite = await createServer({ server: { host: '127.0.0.1', port: 3214, strictPort: true } });
let browser;

const products = [
  { id: 'p1', sku: 'TEST-TIRE', name: 'Ban Uji', type: 'barang', category: 'TIRE', stock: 20,
    selling_price: 850000, cost_price: 750000, service_fee: 0, brand: 'Test', size: '185/14', owner: 'ibu', tax: 1 },
  { id: 'p2', sku: 'TEST-SERVICE', name: 'Spooring', type: 'jasa', category: 'SERVICE', stock: 0,
    selling_price: 175000, cost_price: 0, service_fee: 0, brand: '', size: '', owner: 'ibu', tax: 0 },
];
const customers = [
  { id: 'c1', name: 'Andi' }, { id: 'c2', name: 'Budi' }, { id: 'c3', name: 'Citra' },
  ...Array.from({ length: 15 }, (_, i) => ({ id: `extra-${i}`, name: `Pelanggan ${String(i + 1).padStart(2, '0')}` })),
].map(customer => ({ phone: '', address: '', ...customer }));
const daily = {
  date: '2026-10-24', cash_sales: 5135000, non_cash_sales: 951000, receivable_payments: 500000,
  transfer_payments: 951000, montir_fee: 40000, expenses: 20000, net_cash: 4624000,
  modal_bian: 75000, laba_bian: 100000, final_cash: 4449000, parameters_saved: true,
  modal: 4000000, laba: 409000, spooring: 40000, oil_revenue: 0, oil_benefit: 0,
  receivable_profit: 200000,
  transfer_breakdown: { transfer_bca: 150000, transfer_bri: 100000, transfer_bni: 50000, edc: 600000, qris: 51000 },
};

function fixtureState(options = {}) {
  const debts = customers.map((customer, i) => {
    const amount = [2500000, 3000000, 5000000][i] ?? 100000 + i * 1000;
    const paid = [500000, 2000000, 500000][i] ?? 1000;
    return { id: `ar-${customer.id}`, transaction_id: `seed-${customer.id}`, invoice_number: `INV-${customer.id}`,
      customer_id: customer.id, customer_name: customer.name, amount, paid_amount: paid, remaining: amount - paid,
      status: 'partial', due_date: '2026-11-07', issued_date: '2026-10-24', payments: [], version: 1,
      days_overdue: 0, days_remaining: 14, due_label: 'Belum jatuh tempo (14 hari lagi)', aging_bucket: null };
  });
  return { debts, saved: new Map(), posts: [], paymentPosts: [], daily: structuredClone(daily), options, requests: [], expectedHttpErrors: 0 };
}

function makeTransaction(body, index) {
  const details = body.items.map((item, i) => {
    const product = products.find(row => row.id === item.product_id);
    const price = product.selling_price + item.credit_surcharge;
    return { id: `detail-${index}-${i}`, transaction_id: `tx-${index}`, product_id: product.id,
      product_sku: product.sku, product_name: product.name, product_type: product.type,
      product_brand: product.brand, product_size: product.size, owner: product.owner, category: product.category,
      qty: item.qty, price, base_price: product.selling_price, credit_surcharge: item.credit_surcharge,
      discount_per_unit: item.discount_per_unit, discount_amount: item.discount_per_unit * item.qty,
      subtotal: (price - item.discount_per_unit) * item.qty, cost_price: product.cost_price, service_fee: 0 };
  });
  const total = details.reduce((sum, row) => sum + row.subtotal, 0);
  const due = body.credit_term_days ? new Date(Date.UTC(2026, 9, 24 + body.credit_term_days)).toISOString().slice(0, 10) : null;
  return { id: `tx-${index}`, invoice_number: `INV-TEST-${String(index).padStart(4, '0')}`, date: '2026-10-24T03:00:00Z',
    date_key: '2026-10-24', payment_method: body.payment_method, status: 'completed', details,
    customer_id: body.customer_id, customer_name: customers.find(row => row.id === body.customer_id)?.name ?? null,
    customer_address: '', vehicle_plate: body.vehicle_plate, due_date: due, credit_term_days: body.credit_term_days,
    down_payment_amount: body.down_payment_amount, down_payment_method: body.down_payment_method,
    cash_received: body.cash_received, change_amount: body.cash_received === null ? null : body.cash_received - total,
    total_amount: total, discount_total: details.reduce((sum, row) => sum + row.discount_amount, 0),
    total_cost: 750000 * details.filter(row => row.product_id === 'p1').reduce((sum, row) => sum + row.qty, 0),
    service_fee: 0, total_profit: 100000, spreadsheet_profit: 100000, barang_amount: total, jasa_amount: 0 };
}

async function setup(options = {}) {
  const state = fixtureState(options);
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 }, serviceWorkers: 'block', colorScheme: 'light' });
  await context.addInitScript(() => {
    localStorage.setItem('theme', 'light');
    window.__printCalls = [];
    const recordPrint = target => {
      if (window.__failNextPrint) { window.__failNextPrint = false; throw new Error('Printer fixture unavailable'); }
      const doc = target.document;
      window.__printCalls.push({ title: doc.title, text: doc.body?.innerText ?? '', html: doc.documentElement.outerHTML });
      target.dispatchEvent(new target.Event('afterprint'));
    };
    window.print = () => recordPrint(window);
    const descriptor = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', { ...descriptor, get() {
      const target = descriptor.get.call(this);
      try { if (target) target.print = () => recordPrint(target); } catch { /* A cross-origin frame cannot be printed by the app. */ }
      return target;
    } });
  });
  await context.route(/\/api(?:\/|\?|$)/, async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^.*\/api/, '');
    const method = request.method();
    state.requests.push({ path, method });
    let data;
    let status = 200;
    if (options.delay?.[path]) await new Promise(resolveDelay => setTimeout(resolveDelay, options.delay[path]));
    if (options.errors?.[path]) {
      state.expectedHttpErrors += 1;
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Gangguan fixture uji' }) });
      return;
    }
    if (path === '/auth/me') data = { id: 'test-admin', username: 'test', name: 'Admin Uji', role: 'admin' };
    else if (path === '/system') data = { today: '2026-10-24', timezone: 'Asia/Jakarta' };
    else if (path === '/products') data = options.emptyProducts ? [] : products;
    else if (path === '/customers') data = options.emptyCustomers ? [] : customers;
    else if (path === '/suppliers' || path === '/payables') data = [];
    else if (path === '/receivables') data = state.debts;
    else if (path === '/receivables/summary/by-customer') data = options.emptySummary ? [] : state.debts.map(row => ({
      customer_id: row.customer_id, customer_name: row.customer_name, total_credit: row.amount,
      total_paid: row.paid_amount, outstanding: row.remaining, invoice_count: 1,
    }));
    else if (/^\/receivables\/[^/]+\/pay$/.test(path) && method === 'POST') {
      const body = request.postDataJSON();
      state.paymentPosts.push(body);
      const debt = state.debts.find(row => row.id === path.split('/')[2]);
      const profit = body.profit_amount ?? Math.min(200000, body.amount);
      debt.paid_amount += body.amount;
      debt.remaining -= body.amount;
      debt.status = debt.remaining === 0 ? 'paid' : 'partial';
      debt.payments.push({ ...body, id: `payment-${state.paymentPosts.length}`, profit_amount: profit, profit_is_manual: 'profit_amount' in body });
      data = debt;
    }
    else if (path === '/transactions' && method === 'POST') {
      const body = request.postDataJSON();
      state.posts.push(body);
      data = state.saved.get(body.request_id);
      if (!data) {
        data = makeTransaction(body, state.saved.size + 1);
        state.saved.set(body.request_id, data);
        if (options.loseAck) {
          options.loseAck = false;
          state.expectedHttpErrors += 1;
          await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Jawaban simpan terputus' }) });
          return;
        }
      }
      status = 201;
    } else if (path === '/transactions') data = [...state.saved.values()];
    else if (path.startsWith('/transactions/')) data = [...state.saved.values()].find(row => row.id === path.split('/').at(-1));
    else if (path === '/books/daily') data = { ...state.daily, date: url.searchParams.get('date') };
    else if (path.startsWith('/books/daily/parameters/') && method === 'PUT') {
      Object.assign(state.daily, request.postDataJSON());
      data = { ...state.daily };
    } else if (path === '/books/get-data') data = { rows: [], total: 0, full_total: 0, tax_base: 0, pph_final: 0, count: 0, page: 1, page_size: 25 };
    else if (path.endsWith('/csv')) {
      await route.fulfill({ contentType: 'text/csv', body: 'Tanggal,Total\n2026-10-24,5135000\n' });
      return;
    } else {
      results.unknownApi.push({ path, method });
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: `Unmocked fixture ${method} ${path}` }) });
      return;
    }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
  });
  const page = await context.newPage();
  page.on('pageerror', error => results.pageErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') results.consoleErrors.push(message.text()); });
  page.setDefaultTimeout(12000);
  return { page, context, state };
}

async function click(page, testid) {
  await page.getByTestId(testid).click();
  results.clicks.push({ route: new URL(page.url()).hash, control: testid });
}

async function screenshot(page, name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await settled(page);
  await page.screenshot({ path: resolve(artifacts, `${name}.png`), fullPage: true, animations: 'disabled', caret: 'hide' });
}

async function settled(page) {
  await page.evaluate(async () => {
    await new Promise(resolveFrame => requestAnimationFrame(() => requestAnimationFrame(resolveFrame)));
    await Promise.all(document.getAnimations().filter(animation => Number.isFinite(animation.effect?.getComputedTiming().endTime))
      .map(animation => animation.finished.catch(() => {})));
  });
}

async function contrast(page, selector, label) {
  await settled(page);
  const sample = await page.locator(selector).first().evaluate(element => {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const rgba = color => { ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1); return [...ctx.getImageData(0, 0, 1, 1).data].map((v, i) => i === 3 ? v / 255 : v); };
    const blend = (top, bottom) => top.slice(0, 3).map((channel, i) => channel * top[3] + bottom[i] * (1 - top[3]));
    let background = [255, 255, 255];
    let opacity = 1;
    const chain = [];
    for (let node = element; node; node = node.parentElement) chain.unshift(node);
    for (const node of chain) { const style = getComputedStyle(node); background = blend(rgba(style.backgroundColor), background); opacity *= Number(style.opacity); }
    const style = getComputedStyle(element);
    const foreground = blend(rgba(style.color), background);
    const luminance = color => color.map(channel => { const c = channel / 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; }).reduce((sum, c, i) => sum + c * [.2126, .7152, .0722][i], 0);
    const fg = luminance(foreground), bg = luminance(background);
    return { foreground: style.color, background, opacity, ratio: (Math.max(fg, bg) + .05) / (Math.min(fg, bg) + .05), text: element.textContent?.trim().slice(0, 60) };
  });
  results.contrast.push({ label, ...sample });
  assert.equal(sample.opacity, 1, `${label} unexpected opacity ${sample.opacity}`);
  assert(sample.ratio >= 4.5, `${label} contrast ${sample.ratio.toFixed(2)} below 4.5`);
}

async function run(name, body) {
  if (scenarioFilter && !name.toLowerCase().includes(scenarioFilter)) return;
  try {
    await body();
    results.passed.push(name);
    process.stdout.write(`PASS ${name}\n`);
  } catch (error) {
    results.failed.push({ name, message: error.stack });
    process.stdout.write(`FAIL ${name}: ${error.message}\n`);
  }
}

async function gotoPos(page) {
  await page.goto(`${origin}/#/pos`);
  await page.getByTestId('pos-product-card-test-tire').waitFor();
}

async function assertDisabled(locator, expected = true) { assert.equal(await locator.isDisabled(), expected); }
async function prints(page) { return page.evaluate(() => window.__printCalls); }

function inspectPdf(path) {
  return JSON.parse(execFileSync(resolve('../backend/venv/Scripts/python.exe'), ['-c',
    'import json,sys,math; from pypdf import PdfReader; r=PdfReader(sys.argv[1]); sizes=[]; texts=[p.extract_text(visitor_text=lambda t,c,m,f,s:sizes.append(float(s)*math.hypot(c[0],c[1])) if t.strip() else None) for p in r.pages]; print(json.dumps({"pages":len(r.pages),"width":float(r.pages[0].mediabox.width),"height":float(r.pages[0].mediabox.height),"text":"\\n".join(texts),"min_font_pt":min(sizes)}))',
    path], { encoding: 'utf8' }));
}

function renderPdf(path, output) {
  execFileSync(resolve('../backend/venv/Scripts/python.exe'), ['-c',
    'import sys; sys.path.insert(0,sys.argv[1]); import pypdfium2 as pdf; doc=pdf.PdfDocument(sys.argv[2]); doc[0].render(scale=1.6).to_pil().save(sys.argv[3])',
    resolve('../.cache/pdf-qa-tools'), path, output]);
}

try {
  await vite.listen();
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });

  await run('Cash single panel, quantities, discounts, payment methods, save then print, cancel and reprint', async () => {
    const { page, context, state } = await setup();
    try {
      await gotoPos(page);
      assert.equal(await page.getByTestId('payment-cash-btn').getAttribute('aria-pressed'), 'true');
      await click(page, 'pos-product-card-test-tire');
      await click(page, 'cart-increment-test-tire');
      await click(page, 'cart-decrement-test-tire');
      await click(page, 'cart-increment-test-tire');
      await page.getByTestId('item-discount-p1').fill('25000');
      await click(page, 'pos-tab-jasa');
      await click(page, 'pos-product-card-test-service');
      await click(page, 'cart-remove-test-service');
      await click(page, 'pos-product-card-test-service');
      await click(page, 'pos-tab-semua');
      assert.match(await page.getByTestId('cart-total').innerText(), /1\.825\.000/);
      assert.equal(await page.getByTestId('checkout-panel').count(), 1);
      assert.equal(await page.locator('[role="dialog"]').count(), 0);
      assert.equal(await page.getByTestId('checkout-customer-select').inputValue(), '');
      assert.equal(await page.getByTestId('checkout-vehicle-plate-input').inputValue(), '');
      await page.getByTestId('item-discount-p1').fill('850001');
      await assertDisabled(page.getByTestId('checkout-submit-button'));
      await page.getByTestId('item-discount-p1').fill('25000');
      for (const method of ['transfer_bca', 'transfer_bri', 'transfer_bni', 'edc', 'qris', 'cash']) {
        await page.getByTestId('checkout-payment-method').selectOption(method);
        results.clicks.push({ control: 'checkout-payment-method', value: method });
      }
      await page.getByTestId('checkout-cash-received').fill('1000');
      await assertDisabled(page.getByTestId('checkout-submit-button'));
      await page.getByRole('button', { name: 'Uang pas', exact: true }).click();
      await assertDisabled(page.getByTestId('checkout-submit-button'), false);
      await page.getByTestId('checkout-cash-received').fill('2000000');
      assert.match(await page.getByTestId('checkout-change').innerText(), /175\.000/);
      await screenshot(page, 'checkout-cash-desktop');
      await page.getByTestId('checkout-submit-button').evaluate(button => { button.click(); button.click(); });
      results.clicks.push({ control: 'checkout-submit-button', action: 'two immediate clicks' });
      await page.getByTestId('sales-note-dialog').waitFor();
      await page.waitForFunction(() => window.__printCalls.length === 1);
      assert.equal(state.saved.size, 1);
      assert.equal(state.posts.length, 1);
      assert.equal(state.posts[0].customer_id, null);
      assert.equal(state.posts[0].vehicle_plate, null);
      assert.equal(state.posts[0].items[0].qty, 2);
      assert.equal(state.posts[0].items[0].discount_per_unit, 25000);
      assert.match((await prints(page))[0].text, /INV-TEST-0001/);
      await click(page, 'close-receipt-btn');
      await page.getByText('INV-TEST-0001 sudah tersimpan.').waitFor();
      await click(page, 'reprint-last-transaction');
      await page.getByTestId('print-receipt-btn').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !document.querySelector('[data-testid="print-receipt-btn"]').disabled);
      assert.equal((await prints(page)).length, 1);
      await click(page, 'print-receipt-btn');
      await page.waitForFunction(() => window.__printCalls.length === 2);
      assert.equal(state.saved.size, 1);
      await page.keyboard.press('Escape');
      await page.getByTestId('sales-note-dialog').waitFor({ state: 'hidden' });
    } finally { await context.close(); }
  });

  await run('Tempo customer and tenor validation, optional plate, no DP and DP choices', async () => {
    const { page, context, state } = await setup();
    try {
      await gotoPos(page);
      await click(page, 'payment-credit-btn');
      await click(page, 'pos-product-card-test-tire');
      await assertDisabled(page.getByTestId('checkout-submit-button'));
      await page.getByTestId('checkout-credit-warning').waitFor();
      assert.equal(await page.getByTestId('checkout-term-days').getAttribute('type'), 'number');
      assert.equal(await page.locator('[data-testid="checkout-panel"] input[type="date"]').count(), 0);
      await page.getByTestId('checkout-customer-select').selectOption('c1');
      for (const value of ['0', '3651', '1.5']) {
        await page.getByTestId('checkout-term-days').fill(value);
        await assertDisabled(page.getByTestId('checkout-submit-button'));
      }
      await page.getByTestId('checkout-term-days').fill('40');
      await page.getByText('Jatuh tempo: 3 Desember 2026').waitFor();
      await page.getByTestId('surcharge-p1').fill('10000');
      await assertDisabled(page.getByTestId('checkout-payment-method'));
      assert.match(await page.getByTestId('checkout-remaining').innerText(), /860\.000/);
      await assertDisabled(page.getByTestId('checkout-submit-button'), false);
      await page.getByTestId('checkout-down-payment-option').selectOption('with');
      for (const value of ['', '0', '860000', '-1']) {
        await page.getByTestId('checkout-down-payment-amount').fill(value);
        await assertDisabled(page.getByTestId('checkout-submit-button'));
      }
      await page.getByTestId('checkout-down-payment-amount').fill('200000');
      await page.getByTestId('checkout-payment-method').selectOption('qris');
      await page.getByTestId('checkout-vehicle-plate-input').fill('b 1234 xy');
      await settled(page);
      assert.equal(await page.getByTestId('checkout-down-payment-amount').getAttribute('aria-invalid'), 'false');
      await assertDisabled(page.getByTestId('checkout-submit-button'), false);
      assert.match(await page.getByTestId('checkout-remaining').innerText(), /660\.000/);
      await screenshot(page, 'checkout-tempo-dp-desktop');
      await click(page, 'checkout-submit-button');
      await page.waitForFunction(() => window.__printCalls.length === 1);
      const body = state.posts[0];
      assert.equal(body.payment_method, 'credit');
      assert.equal(body.credit_term_days, 40);
      assert.equal(body.due_date, null);
      assert.equal(body.down_payment_amount, 200000);
      assert.equal(body.down_payment_method, 'qris');
      assert.equal(body.cash_received, null);
      assert.equal(body.vehicle_plate, 'B 1234 XY');
      const note = (await prints(page))[0];
      assert.match(note.text, /200\.000/);
      assert.match(note.text, /660\.000/);
      const notePage = await context.newPage();
      await notePage.setContent(note.html);
      await notePage.screenshot({ path: resolve(artifacts, 'tempo-dp-note-half.png'), fullPage: true });
      const notePath = resolve(artifacts, 'tempo-dp-note-half.pdf');
      await notePage.pdf({ path: notePath, width: '241.3mm', height: '139.7mm', preferCSSPageSize: false, printBackground: true, displayHeaderFooter: false, margin: { top: '0', right: '0', bottom: '0', left: '0' } });
      const notePages = Number(execFileSync(resolve('../backend/venv/Scripts/python.exe'), ['-c', 'import sys; from pypdf import PdfReader; print(len(PdfReader(sys.argv[1]).pages))', notePath], { encoding: 'utf8' }).trim());
      assert.equal(notePages, 1, 'DP sales note must fit one half sheet');
      results.pdfs.push({ name: 'tempo-dp-note-half', pages: notePages });
      await notePage.close();
      await click(page, 'close-receipt-btn');
      await click(page, 'pos-product-card-test-tire');
      await click(page, 'payment-credit-btn');
      await page.getByTestId('checkout-customer-select').selectOption('c2');
      await page.getByTestId('checkout-down-payment-option').selectOption('with');
      await page.getByTestId('checkout-down-payment-amount').fill('100000');
      await page.getByTestId('checkout-down-payment-option').selectOption('none');
      await click(page, 'checkout-submit-button');
      await page.waitForFunction(() => window.__printCalls.length === 2);
      assert.equal(state.posts[1].down_payment_amount, 0);
      assert.equal(state.posts[1].down_payment_method, null);
      assert.equal(state.posts[1].vehicle_plate, null);
    } finally { await context.close(); }
  });

  await run('Lost save acknowledgment retries same request id and retains a single saved transaction', async () => {
    const { page, context, state } = await setup({ loseAck: true });
    try {
      await gotoPos(page);
      await click(page, 'pos-product-card-test-tire');
      await click(page, 'checkout-submit-button');
      await page.getByTestId('checkout-save-error').waitFor();
      assert.equal((await prints(page)).length, 0);
      assert.equal(state.saved.size, 1);
      await page.getByTestId('cart-line-test-tire').waitFor();
      await click(page, 'checkout-submit-button');
      await page.waitForFunction(() => window.__printCalls.length === 1);
      assert.equal(state.posts.length, 2);
      assert.equal(state.posts[0].request_id, state.posts[1].request_id);
      assert.equal(state.saved.size, 1);
      await screenshot(page, 'checkout-retry-saved-note');
    } finally { await context.close(); }
  });

  await run('Printer failure keeps saved transaction and manual retry prints without resaving', async () => {
    const { page, context, state } = await setup();
    try {
      await gotoPos(page);
      await click(page, 'pos-product-card-test-tire');
      await page.evaluate(() => { window.__failNextPrint = true; });
      await click(page, 'checkout-submit-button');
      await page.getByTestId('sales-note-print-error').waitFor();
      assert.equal(state.saved.size, 1);
      assert.equal(state.posts.length, 1);
      assert.equal((await prints(page)).length, 0);
      await click(page, 'print-receipt-btn');
      await page.waitForFunction(() => window.__printCalls.length === 1);
      assert.equal(state.posts.length, 1);
      await page.keyboard.press('Escape');
      await page.getByTestId('sales-note-dialog').waitFor({ state: 'hidden' });
      await page.getByText('INV-TEST-0001 sudah tersimpan.').waitFor();
    } finally { await context.close(); }
  });

  await run('Customer recap sorts every option, searches, pages, opens invoices and clears customer filter', async () => {
    const { page, context } = await setup();
    try {
      await page.goto(`${origin}/#/piutang-hutang`);
      await click(page, 'receivables-view-customers');
      const rows = page.getByTestId('customer-receivable-row');
      await rows.first().waitFor();
      const expected = { 'outstanding-desc': 'Citra', 'outstanding-asc': 'Pelanggan 01', 'total_credit-desc': 'Citra', 'total_paid-desc': 'Budi', name: 'Andi' };
      for (const [sort, name] of Object.entries(expected)) {
        await page.getByTestId('customer-debt-sort').selectOption(sort);
        assert.match(await rows.first().innerText(), new RegExp(name));
        results.clicks.push({ control: 'customer-debt-sort', value: sort });
      }
      await page.getByTestId('customer-receivables').getByRole('button', { name: 'Berikutnya', exact: true }).click();
      assert.equal(await rows.count(), 3);
      await page.getByTestId('customer-receivables').getByRole('button', { name: 'Sebelumnya', exact: true }).click();
      await page.getByTestId('customer-debt-search').fill('  anDi  ');
      assert.equal(await rows.count(), 1);
      assert.match(await rows.first().innerText(), /2\.500\.000/);
      await rows.first().getByRole('button', { name: 'Lihat nota', exact: true }).click();
      await page.getByTestId('clear-customer-filter').waitFor();
      assert.equal(await page.locator('[data-testid^="debt-row-"]').count(), 1);
      await click(page, 'clear-customer-filter');
      assert.equal(await page.locator('[data-testid^="debt-row-"]').count(), 15);
      await click(page, 'receivables-view-customers');
      await page.getByTestId('customer-debt-search').fill('tidak-ditemukan');
      await page.getByTestId('empty-customer-receivables').waitFor();
      await page.getByTestId('customer-debt-search').fill('');
      await screenshot(page, 'customer-receivables-desktop');
    } finally { await context.close(); }
  });

  await run('Debt payment uses bounded optional profit, preserves automatic mode and refreshes customer recap', async () => {
    const { page, context, state } = await setup();
    try {
      await page.goto(`${origin}/#/piutang-hutang`);
      await click(page, 'pay-ar-c2');
      await click(page, 'payment-full-amount');
      assert.equal(await page.getByTestId('payment-amount').inputValue(), '1000000');
      await click(page, 'payment-cancel');
      assert.equal(state.paymentPosts.length, 0);
      await click(page, 'pay-ar-c1');
      await page.getByTestId('payment-amount').fill('500000');
      const profit = page.getByTestId('payment-profit');
      assert.equal(await profit.getAttribute('min'), '0');
      assert.equal(await profit.getAttribute('max'), '500000');
      assert.match(await page.getByTestId('payment-profit-help').innerText(), /maksimal sebesar pembayaran ini/);
      for (const invalid of ['-1', '500001']) {
        await profit.fill(invalid);
        assert.equal(await profit.evaluate(input => input.checkValidity()), false);
        await click(page, 'payment-submit');
        assert.equal(state.paymentPosts.length, 0);
      }
      await profit.fill('');
      await page.getByTestId('payment-method').selectOption('transfer_bca');
      await page.getByTestId('payment-note').fill('Cicilan uji isolated');
      await click(page, 'payment-submit');
      await page.getByTestId('payment-dialog').waitFor({ state: 'hidden' });
      assert.equal(state.paymentPosts.length, 1);
      assert.equal('profit_amount' in state.paymentPosts[0], false);
      assert.equal(state.paymentPosts[0].method, 'transfer_bca');
      assert.equal(state.debts[0].payments[0].profit_amount, 200000);
      await click(page, 'receivables-view-customers');
      await page.getByTestId('customer-debt-search').fill('Andi');
      const row = page.getByTestId('customer-receivable-row');
      assert.match(await row.innerText(), /1\.000\.000/);
      assert.match(await row.innerText(), /1\.500\.000/);
      await screenshot(page, 'customer-receivables-after-payment');
    } finally { await context.close(); }
  });

  await run('Daily report dedicated print document and one page at A4, Letter and half continuous form', async () => {
    const { page, context } = await setup();
    try {
      await page.goto(`${origin}/#/laporan-kas`);
      await click(page, 'books-tab-harian');
      await page.getByTestId('daily-report').waitFor();
      await page.getByTestId('daily-date-input').fill('2026-10-24');
      await page.getByTestId('daily-bian-modal').fill('75000');
      await page.getByTestId('daily-bian-profit').fill('100000');
      await click(page, 'daily-save-bian');
      await click(page, 'daily-print-button');
      await page.waitForFunction(() => window.__printCalls.length === 1);
      const captured = (await prints(page))[0];
      assert.match(captured.text, /5\.135\.000/);
      assert.match(captured.text, /500\.000/);
      assert.match(captured.text, /QRIS|Qris/);
      assert(!captured.text.includes('Cari barang'));
      await writeFile(resolve(artifacts, 'daily-report.html'), captured.html);
      const documentPage = await context.newPage();
      await documentPage.setContent(captured.html);
      await documentPage.emulateMedia({ media: 'print' });
      await documentPage.screenshot({ path: resolve(artifacts, 'daily-report-print.png'), fullPage: true });
      for (const [name, paper] of [['a4', { format: 'A4' }], ['letter', { format: 'Letter' }], ['continuous-half', { width: '241.3mm', height: '139.7mm' }]]) {
        const path = resolve(artifacts, `daily-report-${name}.pdf`);
        await documentPage.pdf({ path, ...paper, preferCSSPageSize: false, printBackground: true, displayHeaderFooter: false, margin: { top: '0', right: '0', bottom: '0', left: '0' } });
        const summary = inspectPdf(path);
        assert.equal(summary.pages, 1, `${name} must fit one sheet`);
        const dimensions = { a4: [595.28, 841.89], letter: [612, 792], 'continuous-half': [684, 396] }[name];
        assert(Math.abs(summary.width - dimensions[0]) < 1 && Math.abs(summary.height - dimensions[1]) < 1,
          `${name} actual page ${summary.width}x${summary.height}pt differs from expected ${dimensions.join('x')}pt`);
        assert.match(summary.text, /5\.135\.000/);
        assert.match(summary.text, /QRIS|Qris/);
        assert.match(summary.text, /Total nontunai/);
        assert(summary.min_font_pt >= 9.48, `${name} PDF font ${summary.min_font_pt}pt must retain 9.5pt native type`);
        renderPdf(path, resolve(artifacts, `daily-report-${name}-render.png`));
        results.pdfs.push({ name, pages: summary.pages, width: summary.width, height: summary.height, min_font_pt: summary.min_font_pt });
      }
      const otherReport = structuredClone(daily);
      otherReport.transfer_breakdown.transfer_other = 110000;
      otherReport.transfer_payments += 110000;
      otherReport.net_cash -= 110000;
      otherReport.final_cash -= 110000;
      otherReport.modal -= 110000;
      const otherHtml = await page.evaluate(async report => {
        const { buildDailyReportDocument } = await import('/src/lib/daily-report-print.ts');
        return buildDailyReportDocument(report);
      }, otherReport);
      await writeFile(resolve(artifacts, 'daily-report-other-transfers-half.html'), otherHtml);
      await documentPage.setContent(otherHtml);
      const nativeFont = await documentPage.locator('body,th,td,h1,h2,p').evaluateAll(elements => Math.min(...elements
        .filter(element => element.textContent.trim()).map(element => parseFloat(getComputedStyle(element).fontSize) * .75)));
      assert(nativeFont >= 9.49, `Native report font ${nativeFont}pt must remain at least 9.5pt`);
      const otherPath = resolve(artifacts, 'daily-report-other-transfers-half.pdf');
      await documentPage.pdf({ path: otherPath, width: '241.3mm', height: '139.7mm', preferCSSPageSize: false,
        printBackground: true, displayHeaderFooter: false, margin: { top: '0', right: '0', bottom: '0', left: '0' } });
      const otherPdf = inspectPdf(otherPath);
      assert.equal(otherPdf.pages, 1, 'Transfer lainnya row must fit one half sheet');
      assert(Math.abs(otherPdf.width - 684) < 1 && Math.abs(otherPdf.height - 396) < 1);
      assert.match(otherPdf.text, /Transfer lainnya/);
      assert.match(otherPdf.text, /110\.000/);
      assert.match(otherPdf.text, /1\.061\.000/);
      assert.match(otherPdf.text, /QRIS/);
      assert.match(otherPdf.text, /Total nontunai/);
      assert(otherPdf.min_font_pt >= 9.48, `Other-transfer PDF font ${otherPdf.min_font_pt}pt must retain native 9.5pt type`);
      renderPdf(otherPath, resolve(artifacts, 'daily-report-other-transfers-half-render.png'));
      results.pdfs.push({ name: 'other-transfers-half', pages: otherPdf.pages, width: otherPdf.width,
        height: otherPdf.height, min_font_pt: otherPdf.min_font_pt, native_font_pt: nativeFont });
      await documentPage.close();
      for (const theme of ['light', 'dark']) {
        if (theme === 'dark') await page.locator('[data-testid="theme-toggle"]:visible').first().click();
        for (const width of [375, 768, 1280]) {
          await page.setViewportSize({ width, height: 1000 });
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
          await screenshot(page, `daily-ui-${theme}-${width}`);
        }
      }
    } finally { await context.close(); }
  });

  await run('Light and dark layouts at 375, 768, 1280, keyboard modes and focus without page overflow', async () => {
    const { page, context } = await setup();
    try {
      await gotoPos(page);
      await click(page, 'pos-product-card-test-tire');
      for (const theme of ['light', 'dark']) {
        if (theme === 'dark') await page.locator('[data-testid="theme-toggle"]:visible').first().click();
        for (const width of [375, 768, 1280]) {
          await page.setViewportSize({ width, height: 1000 });
          await page.getByTestId('payment-credit-btn').focus();
          await page.keyboard.press('Enter');
          assert.equal(await page.getByTestId('payment-credit-btn').getAttribute('aria-pressed'), 'true');
          await page.getByTestId('checkout-customer-select').selectOption('c1');
          await page.getByTestId('checkout-down-payment-option').selectOption('with');
          await page.getByTestId('checkout-down-payment-amount').fill('100000');
          await settled(page);
          assert.equal(await page.getByTestId('checkout-down-payment-amount').getAttribute('aria-invalid'), 'false');
          await assertDisabled(page.getByTestId('checkout-submit-button'), false);
          if (width === 375) {
            await contrast(page, '[data-testid="checkout-panel"] label', `checkout label ${theme}`);
            await contrast(page, '[data-testid="checkout-panel"] input', `checkout input ${theme}`);
            await contrast(page, '[data-testid="checkout-submit-button"]', `Print button ${theme}`);
            await contrast(page, '[data-testid="checkout-mechanic-fee"]', `checkout card text ${theme}`);
          }
          const dimensions = await page.evaluate(() => ({ width: innerWidth, body: document.body.scrollWidth, root: document.documentElement.scrollWidth }));
          assert(dimensions.body <= dimensions.width + 1 && dimensions.root <= dimensions.width + 1, JSON.stringify(dimensions));
          await screenshot(page, `checkout-${theme}-${width}`);
          await page.keyboard.press('F2');
          assert.equal(await page.getByTestId('pos-search-input').evaluate(element => document.activeElement === element), true);
          await page.keyboard.press('F4');
          const focus = await page.getByTestId('checkout-panel').evaluate(element => ({ focused: document.activeElement === element, outline: getComputedStyle(element).outlineWidth }));
          assert(focus.focused);
          await page.getByTestId('payment-cash-btn').focus();
          await page.keyboard.press('Space');
          assert.equal(await page.getByTestId('payment-cash-btn').getAttribute('aria-pressed'), 'true');
        }
      }
      await page.goto(`${origin}/#/piutang-hutang`);
      await click(page, 'receivables-view-customers');
      await page.getByTestId('customer-receivable-row').first().waitFor();
      for (const theme of ['dark', 'light']) {
        if (theme === 'light') await page.locator('[data-testid="theme-toggle"]:visible').first().click();
        await contrast(page, '[data-testid="receivables-view-customers"]', `selected Per pelanggan ${theme}`);
        await contrast(page, '#customer-debt-search', `recap input ${theme}`);
        await contrast(page, '[data-testid="customer-receivables"] p', `recap card text ${theme}`);
        for (const width of [375, 768, 1280]) {
          await page.setViewportSize({ width, height: 1000 });
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
          await screenshot(page, `customer-receivables-${theme}-${width}`);
        }
      }
    } finally { await context.close(); }
  });

  await run('Loading, error retry and empty states for catalog, customer recap and daily report', async () => {
    const options = { delay: { '/products': 700, '/receivables/summary/by-customer': 700 }, errors: {} };
    const { page, context } = await setup(options);
    try {
      await page.goto(`${origin}/#/pos`);
      await page.getByTestId('loading-block').waitFor();
      await page.getByTestId('pos-product-card-test-tire').waitFor();
      await page.getByTestId('pos-search-input').fill('tidak-ada-produk');
      await page.getByText('Produk tidak ditemukan', { exact: true }).waitFor();
      await page.goto(`${origin}/#/piutang-hutang`);
      options.errors['/receivables/summary/by-customer'] = true;
      await click(page, 'receivables-view-customers');
      await page.getByTestId('customer-receivables').getByTestId('loading-block').waitFor();
      await page.getByTestId('customer-receivables').getByTestId('error-block').waitFor({ timeout: 22000 });
      delete options.errors['/receivables/summary/by-customer'];
      options.emptySummary = true;
      await page.getByTestId('customer-receivables').getByTestId('error-retry-button').click();
      await page.getByTestId('empty-customer-receivables').waitFor();
      options.errors['/books/daily'] = true;
      await page.goto(`${origin}/#/laporan-kas`);
      await click(page, 'books-tab-harian');
      await page.getByTestId('error-block').waitFor({ timeout: 22000 });
      await assertDisabled(page.getByTestId('daily-print-button'));
      delete options.errors['/books/daily'];
      await click(page, 'error-retry-button');
      await page.getByTestId('daily-report').waitFor();
      await assertDisabled(page.getByTestId('daily-print-button'), false);
    } finally { await context.close(); }
  });

  assert.deepEqual(results.pageErrors, []);
  assert.deepEqual(results.unknownApi, []);
  const unexpectedConsole = results.consoleErrors.filter(message => !/Failed to load resource: the server responded with a status of 503|favicon/i.test(message));
  assert.deepEqual(unexpectedConsole, []);
  await writeFile(resolve(artifacts, 'clickthrough.json'), JSON.stringify(results, null, 2));
  assert.equal(results.failed.length, 0, JSON.stringify(results.failed));
  process.stdout.write(`${results.passed.length} isolated browser scenarios passed; every API request was intercepted.\n`);
} finally {
  await writeFile(resolve(artifacts, 'clickthrough.json'), JSON.stringify(results, null, 2));
  await browser?.close();
  await vite.close();
}
