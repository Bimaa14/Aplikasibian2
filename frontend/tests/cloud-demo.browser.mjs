// Run from frontend: node tests/cloud-demo.browser.mjs.
// Uses the backend venv and local Mongo only, with a generated disposable database.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes, randomUUID } from 'node:crypto';
import { once } from 'node:events';
import { mkdir, writeFile } from 'node:fs/promises';
import { createServer } from 'node:net';
import { resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';
import { build } from 'vite';

process.env.DISABLE_VISUAL_EDITS = 'true';
process.env.DISABLE_EMERGENT_OVERLAY = 'true';
process.env.VITE_BACKEND_URL = '';
const backend = resolve('../backend');
const python = resolve(backend, process.platform === 'win32' ? 'venv/Scripts/python.exe' : 'venv/bin/python');
const database = `bian_demo_smoke_${randomUUID().replaceAll('-', '')}`;
const artifacts = resolve(`../test_reports/deployment/cloud-demo-${Date.now()}`);
const dist = resolve(artifacts, 'dist');
const origin = 'http://127.0.0.1:3128';
const setupKey = randomBytes(32).toString('hex');
const password = `Demo-${randomBytes(16).toString('hex')}`;
const productName = 'Ban demo uji';
let child, browser;
let backendLog = '';
const result = { database, origin, realApi: true, dotenvDisabled: true, importedBusinessData: false };

// The local venv may use an older dotenv without PYTHON_DOTENV_DISABLED support.
// Patch the loader before importing server modules; never read backend/.env.
const launchPython = [
  'import dotenv',
  'dotenv.load_dotenv = lambda *args, **kwargs: False',
  'import uvicorn',
  "uvicorn.run('server:app', host='127.0.0.1', port=3128, workers=1, log_level='warning')",
].join('\n');
const databasePython = [
  'import re, sys',
  'from pymongo import MongoClient',
  'name, action = sys.argv[1:]',
  "assert re.fullmatch(r'bian_demo_smoke_[0-9a-f]{32}', name), 'Unsafe database name'",
  "client = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)",
  "client.admin.command('ping')",
  "if action == 'check': assert name not in client.list_database_names(), 'Database already exists'",
  "elif action == 'drop': client.drop_database(name); assert name not in client.list_database_names()",
  "else: raise ValueError('Unexpected action')",
  'client.close()',
].join('\n');
function localDatabase(action) {
  assert.match(database, /^bian_demo_smoke_[0-9a-f]{32}$/);
  const command = spawnSync(python, ['-c', databasePython, database, action], { encoding: 'utf8', windowsHide: true });
  assert.equal(command.status, 0, command.stderr || command.error?.message || `Local Mongo ${action} failed`);
}
async function login(page) {
  await page.getByTestId('login-username-input').fill('demo-admin');
  await page.getByTestId('login-password-input').fill(password);
  await Promise.all([
    page.waitForURL(`${origin}/#/`),
    page.getByTestId('login-submit-button').click(),
  ]);
  await page.getByTestId('logout-button').waitFor();
}

await mkdir(artifacts, { recursive: true });
localDatabase('check');
// Refuse an occupied port before any setup/write request can reach another server.
const portProbe = createServer();
await new Promise((resolve, reject) => {
  portProbe.once('error', reject);
  portProbe.listen(3128, '127.0.0.1', resolve);
});
await new Promise(resolve => portProbe.close(resolve));
try {
  await build({ base: '/', logLevel: 'warn', build: { outDir: dist, emptyOutDir: true } });
  child = spawn(python, ['-c', launchPython], {
    cwd: backend,
    windowsHide: true,
    env: {
      ...process.env, PYTHON_DOTENV_DISABLED: '1', PYTHONUNBUFFERED: '1',
      MONGO_URL: 'mongodb://127.0.0.1:27017', DB_NAME: database, APP_TZ: 'Asia/Jakarta',
      FRONTEND_DIST: dist, CLOUD_SINGLE_WRITER: 'true', COOKIE_SECURE: 'false', COOKIE_SAMESITE: 'lax',
      CORS_ORIGINS: origin, RENDER_EXTERNAL_URL: '', WORKBOOK_DIR: resolve('../imports/workbooks'),
      DEMO_SETUP_KEY: setupKey,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.on('data', data => { backendLog += data.toString(); });
  child.stderr.on('data', data => { backendLog += data.toString(); });
  let childError;
  child.on('error', error => { childError = error; });
  let healthy = false;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (childError || child.exitCode !== null) throw childError || new Error(`Backend exited: ${backendLog}`);
    try {
      const response = await fetch(`${origin}/healthz`, { signal: AbortSignal.timeout(500) });
      healthy = response.ok && (await response.json()).status === 'ok';
      if (healthy) break;
    } catch { /* Wait for Uvicorn and Mongo startup. */ }
    await delay(250);
  }
  assert(healthy, `Backend did not become healthy: ${backendLog}`);
  result.health = true;
  const index = await fetch(`${origin}/`);
  assert.equal(index.status, 200);
  assert.match(await index.text(), /<div id="root"><\/div>/);
  const image = await fetch(`${origin}/storefront-login.jpg`);
  assert.equal(image.status, 200);
  assert.match(image.headers.get('content-type'), /image\/jpeg/);
  result.sameOriginStatic = true;

  browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  });
  const context = await browser.newContext({ viewport: { width: 1366, height: 1000 } });
  const errors = [], externalRequests = [];
  await context.route('**/*', async route => {
    if (new URL(route.request().url()).origin !== origin) {
      externalRequests.push(route.request().url());
      return route.abort();
    }
    return route.continue(); // Real backend/static requests only; no mock responses.
  });
  const setup = await context.request.post(`${origin}/api/setup-demo`, { form: { secret: setupKey, password } });
  assert.equal(setup.status(), 200);
  assert.match(await setup.text(), /Akun demo admin berhasil dibuat/);
  assert.equal((await context.cookies()).length, 0, 'Setup must not log in automatically');
  assert.equal((await context.request.get(`${origin}/api/setup-demo`)).status(), 404);
  assert.equal((await context.request.post(`${origin}/api/setup-demo`, { form: { secret: setupKey, password } })).status(), 404);
  result.setupAdmin = true;
  result.setupDisabledAfterCreation = true;
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${origin}/#/login`);
  await page.getByTestId('login-form').waitFor();
  await login(page);
  const cookie = (await context.cookies()).find(item => item.name === 'bengkel_session');
  assert(cookie?.httpOnly && cookie.sameSite === 'Lax' && !cookie.secure);
  result.realUiLoginCookie = true;

  const created = await context.request.post(`${origin}/api/products`, { data: {
    type: 'barang', sku: 'DEMO-SMOKE', name: productName, category: 'TIRE', tax: 0,
    owner: 'bian', stock: 3, cost_price: 60000, selling_price: 100000, service_fee: 0,
    brand: 'Demo', size: '175/65 14',
  } });
  assert.equal(created.status(), 201, await created.text());
  const product = await created.json();
  await page.goto(`${origin}/#/pos`);
  await page.getByTestId('pos-product-card-demo-smoke').click();
  await page.getByTestId('cart-increment-demo-smoke').click();
  await page.getByTestId('checkout-panel').waitFor();
  await page.getByTestId(`item-discount-${product.id}`).fill('5000');
  await page.getByTestId('checkout-cash-received').fill('200000');
  const submitted = page.waitForResponse(response =>
    new URL(response.url()).pathname === '/api/transactions' && response.request().method() === 'POST');
  await page.getByTestId('checkout-submit-button').click();
  const transactionResponse = await submitted;
  assert.equal(transactionResponse.status(), 201, await transactionResponse.text());
  const transaction = await transactionResponse.json();
  assert.equal(transaction.total_amount, 190000);
  assert.equal(transaction.cash_received, 200000);
  assert.equal(transaction.change_amount, 10000);
  assert.equal(transaction.details[0].qty, 2);
  await page.getByTestId('sales-note-dialog').waitFor();
  const note = page.frameLocator('iframe[title="Pratinjau nota penjualan"]');
  await note.getByText(productName, { exact: false }).waitFor();
  assert((await note.locator('body').innerText()).includes(transaction.invoice_number));
  await page.screenshot({ path: resolve(artifacts, 'nota-real-checkout.png') });
  result.checkoutAndNota = { total: transaction.total_amount, change: transaction.change_amount, quantity: 2 };
  await page.getByTestId('close-receipt-btn').click();

  const systemResponse = await context.request.get(`${origin}/api/system`);
  assert.equal(systemResponse.status(), 200);
  const system = await systemResponse.json();
  const pdf = await context.request.get(`${origin}/api/reports/monthly/pdf?month=${system.today.slice(0, 7)}`);
  assert.equal(pdf.status(), 200, await pdf.text());
  assert.match(pdf.headers()['content-type'], /application\/pdf/);
  const pdfBytes = await pdf.body();
  assert.equal(pdfBytes.subarray(0, 5).toString(), '%PDF-');
  await writeFile(resolve(artifacts, 'monthly-report.pdf'), pdfBytes);
  result.monthlyPdf = true;

  await page.reload();
  await page.getByTestId('logout-button').waitFor();
  const stock = await context.request.get(`${origin}/api/products/${product.id}`);
  assert.equal(stock.status(), 200);
  assert.equal((await stock.json()).stock, 1);
  await page.goto(`${origin}/#/transaksi`);
  await page.getByTestId(`print-tx-btn-${transaction.invoice_number.toLowerCase()}`).click();
  await note.getByText(productName, { exact: false }).waitFor();
  assert((await note.locator('body').innerText()).includes(transaction.invoice_number));
  await page.getByTestId('close-receipt-btn').click();
  result.reloadAndReprint = true;
  await Promise.all([
    page.waitForURL(`${origin}/#/login`),
    page.getByTestId('logout-button').click(),
  ]);
  await page.getByTestId('login-form').waitFor();
  assert.equal((await context.request.get(`${origin}/api/auth/me`)).status(), 401);
  assert(!(await context.cookies()).some(item => item.name === 'bengkel_session'));
  result.logout = true;
  await login(page);
  await page.reload();
  await page.getByTestId('logout-button').waitFor();
  const saved = await context.request.get(`${origin}/api/transactions/${transaction.id}`);
  assert.equal(saved.status(), 200);
  assert.equal((await saved.json()).total_amount, 190000);
  result.reloginDataPersisted = true;
  assert.deepEqual(errors, []);
  assert.deepEqual(externalRequests, []);
} finally {
  if (browser) await browser.close();
  if (child) {
    if (child.exitCode === null && child.signalCode === null) {
      const exited = once(child, 'exit');
      child.kill('SIGTERM');
      await Promise.race([exited, delay(10000, undefined, { ref: false }).then(() => { throw new Error('Backend has not exited; refusing database cleanup'); })]);
    }
    assert(child.exitCode !== null || child.signalCode !== null, 'Backend is still running; refusing database cleanup');
  }
  // Windows termination can leave its cloud lock document, so drop only this generated
  // test database after the writer has stopped. The local OS lock closes with the child.
  localDatabase('drop');
  result.temporaryDatabaseDropped = true;
  await writeFile(resolve(artifacts, 'backend.log'), backendLog);
  await writeFile(resolve(artifacts, 'results.json'), `${JSON.stringify(result, null, 2)}\n`);
}
console.log('PASS: real same-origin static/backend/Mongo, demo setup, UI cookie login, checkout/nota, PDF, reload/reprint, logout and relogin; temporary database dropped.');
console.log(`Artifacts: ${artifacts}`);
