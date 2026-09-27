#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================
## user_problem_statement: Lanjutkan aplikasi BengKasir (POS bengkel Perkasa Jaya). Pakai aplikasi kasir yang ada, samakan pembukuan PERSIS dengan spreadsheet (Store Information System sheet REPORT + 09 Laporan September sheet Laba-Rugi). Impor produk/stok/transaksi/piutang/hutang dengan pratinjau sebelum simpan. (Windows XP offline dibahas nanti.)

## backend:
##   - task: "Fix backend startup crash (Mongo index name conflict id_unique vs id_1)"
##     implemented: true
##     working: true
##     file: "backend/server.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##         -working: true
##         -agent: "main"
##         -comment: "server.py created id index with default name id_1 while ensure_indexes already made id_unique on same collections -> IndexOptionsConflict crashed startup. Fixed to name='id_unique' + try/except. Backend now boots, login works."
##   - task: "Excel reports reconcile exactly with both spreadsheets"
##     implemented: true
##     working: true
##     file: "backend/lib/excel_rules.py, backend/routers/excel_reports.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##         -working: true
##         -agent: "main"
##         -comment: "Store REPORT 12 months + September Laba-Rugi all diffs 0.0 via preview origin and lib checks."
##   - task: "Import piutang/hutang from September workbook with preview then commit"
##     implemented: true
##     working: true
##     file: "backend/lib/workbooks.py, backend/routers/imports.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##         -working: true
##         -agent: "main"
##         -comment: "Relaxed September Piutang/Hutang parser: blank SISA = fully unpaid. Committed 24 receivables (Rp65,844,000) + 39 payables (Rp829,751,449), matching sheet totals B21/B23. Aging computed."

## frontend:
##   - task: "Login, dashboard, POS, Excel report page, Import page, Piutang/Hutang page render with real data"
##     implemented: true
##     working: "NA"
##     file: "frontend/src/pages/*"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##         -working: "NA"
##         -agent: "main"
##         -comment: "Needs frontend verification after backend restore."

## metadata:
##   created_by: "main_agent"
##   version: "2.0"
##   test_sequence: 1
##   run_ui: true

## test_plan:
##   current_focus:
##     - "Excel reports reconcile exactly with both spreadsheets"
##     - "Import piutang/hutang from September workbook with preview then commit"
##     - "POS checkout cash/credit, retur->void, partial payment"
##   stuck_tasks: []
##   test_all: false
##   test_priority: "high_first"

## agent_communication:
##     -agent: "main"
##     -message: "Fixed startup crash. Imported piutang/hutang. Please verify backend (login, excel reconcile both origins, receivables/payables lists sum to 65844000/829751449, POS checkout cash+credit, credit return sets receivable void, partial installment payment) and frontend (login as admin, dashboard, Laporan Excel shows 'Cocok dengan Excel', Impor page, Piutang & Hutang page lists imported debts with aging). Admin creds in /app/memory/test_credentials.md."

## === Iteration 3: product+history import, negative-stock clamp, printable Kwitansi ===
## backend:
##   - task: "Import products (store) with negative/fractional stock clamped to 0 + empty category defaulted"
##     implemented: true
##     working: true
##     file: "backend/lib/workbooks.py, backend/routers/imports.py"
##     needs_retesting: true
##     status_history:
##         -working: true
##         -agent: "main"
##         -comment: "Products preview now 468 ready / 5 blocked (5 = genuine duplicate names). Committed 468 products. Negative stock rows carry a non-blocking note 'Stok sheet X diset 0'."
##   - task: "Import historical transactions (store) into ledger; fast bulk_write; drop qty0/amount0 noise line"
##     implemented: true
##     working: true
##     file: "backend/routers/imports.py"
##     needs_retesting: true
##     status_history:
##         -working: true
##         -agent: "main"
##         -comment: "History preview 7505 ready / 0 blocked (was 1 blocked). Committed 7505 transactions in ~3s via bulk_write (preloaded product name->id map). Live excel report now matches preview/spreadsheet 0.0 for 2026-03/05/07/08."
## frontend:
##   - task: "Printable Kwitansi (payment receipt) per installment in Piutang/Hutang history"
##     implemented: true
##     working: "NA"
##     file: "frontend/src/lib/receipt.ts, frontend/src/pages/DebtPage.tsx"
##     needs_retesting: true
##     status_history:
##         -working: "NA"
##         -agent: "main"
##         -comment: "Print button (data-testid=print-receipt-<paymentId>) appears per payment in payment-history dialog; opens print window with terbilang. Needs a debt WITH payments to appear."
##   - task: "Import page shows non-blocking notes (sky text) for clamped rows"
##     implemented: true
##     working: "NA"
##     file: "frontend/src/pages/ImportPage.tsx"
##     needs_retesting: true

## agent_communication:
##     -agent: "main"
##     -message: "Iteration 3: imported 468 products + 7505 historical transactions; live report now complete for past months. Added printable Kwitansi. Please verify (backend) product/history import idempotency and live reports reconcile 0.0 for several 2026 months, plus no dup on recommit; (frontend) create a fresh test scenario: create a test product+customer, do a CREDIT POS checkout to make a receivable, record a PARTIAL payment, open Piutang history, confirm print-receipt button renders and clicking opens a Kwitansi window/page containing 'KWITANSI PEMBAYARAN'. Do NOT add test payments onto the imported real piutang (XL-RE-*). Admin creds in /app/memory/test_credentials.md."



## agent_communication:
##     -agent: "main"
##     -message: "FEATURE (owner Bian/Ibu, 2026-06): Added product ownership attribute. Product/ProductCreate/ProductUpdate now have owner ('bian'|'ibu'); ProductCreate defaults 'bian', existing imported products stay owner=None (untouched, per user). GET /api/products supports ?owner=bian|ibu filter. TransactionDetail carries owner copied from product at checkout (transaction follows product owner). Frontend ProductsPage: owner select in create/edit dialog (data-testid product-form-owner-select), Pemilik badge column (product-owner-<sku>), and Semua/Bian/Ibu filter (product-owner-filter). types.ts updated. Verified via curl: create owner=ibu OK, filter returns it, existing products read fine, delete OK. Reports pajak/harian/bulanan are DEFERRED pending client answer. Please verify frontend+backend: (1) admin creates a new product choosing 'Barang Ibu (Mamah Bian)' -> appears with Ibu badge, (2) owner filter Semua/Bian/Ibu narrows the table, (3) editing a product changes its owner, (4) POS checkout of an owner-tagged product stores owner on the transaction detail line (GET /api/transactions/{id}). Clean up any test products/transactions you create."

## agent_communication:
##     -agent: "main"
##     -message: "RESTORATION (2026-06): Pod arrived as empty CRA template; user's real app lives at github.com/Bimaa14/Aplikasibian2 (React+TS/Vite + FastAPI). Migrated repo working tree into /app (kept /app/.git, /app/.emergent, created backend/.env + frontend/.env). Removed leftover CRA config (postcss.config.js/craco.config.js/tailwind.config.js/jsconfig.json/plugins) and old .jsx ui components that broke the Vite build. Installed deps (dropped unused emergentintegrations+litellm which conflicted). Seeded accounts (admin/kasir, see test_credentials.md). Re-imported data via /api/imports: 468 products, 7505 transactions, 24 receivables (Rp65.844.000), 39 payables (Rp829.751.449), + September Laba-Rugi + stock snapshot reference. All Excel reconcile diffs 0.0 (curl-verified). Backend /api/dashboard, /api/transactions, /api/excel/stock-snapshot all return correct data via curl. NEED FRONTEND E2E: could not confirm browser login via the screenshot automation tool (its context seems not to persist the httpOnly 'bengkel_session' cookie across navigations); curl login+me works 200. Please verify: (1) login admin/kasir renders dashboard, (2) dashboard shows aging card + KPI totals, (3) transactions page lists data, (4) Piutang & Hutang page, (5) Snapshot Stok (Ref) page loads comparison table."
