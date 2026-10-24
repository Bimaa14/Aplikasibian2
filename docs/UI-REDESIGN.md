# Perkasa Jaya UI revision

Completed locally on 5 October 2026. This revision is not published to Railway.

## Direction and scope

Antislop mode: during, explicitly selected by the owner for this session.

Design Read declared before implementation: a workshop ledger with a midnight navy rail, the existing amber Dunlop identity, a cool paper workspace, and structured financial typography. ENERGY 2, RHYTHM 2, MOTION 1.

The existing login, navigation, dashboard, POS, transactions, vehicle history, customer/product/supplier/stock pages, debt and expense screens, reports, import inspection, stock reference, and Laravel reference screen share the revised foundations. No backend, database migration, new external service, or production credential was changed.

One-line purposes:

- Navy separates navigation from the working ledger; amber marks the current destination and payment action.
- Outfit gives headings the weight of the existing workshop identity; IBM Plex Sans keeps dense forms readable; JetBrains Mono aligns financial figures.
- Flat panels group records; totals receive emphasis instead of giving every panel the same visual weight.
- Eight-pixel panels and smaller controls retain a practical ledger shape rather than capsules.
- Existing product, car, receipt, wallet, and spreadsheet icons identify their actual destinations and actions.
- The supplied logo and storefront photograph establish the real shop identity; no replacement logo or invented imagery was generated.
- Shadows are reserved for modal elevation. Gradients are limited to chart area fills identifying series, not page decoration.
- Short color feedback communicates hover/press state. Continuous, entrance, and layout animation are removed or disabled; reduced motion is respected.
- Mobile cards stack where full Rupiah amounts would otherwise break; dense tables scroll inside their own container.
- Stock before/after arrows communicate an actual inventory transition.

## Recorded verification

Testing used a separate local MongoDB copy, not the Atlas demo database. A disposable local user and identifiable UI test product/transaction/expense were used. No production return, deletion, import commit, payment, or migration was performed.

- TypeScript and the final Vite production build pass. Oxlint and `git diff --check` pass. Vite retains its existing warning about the main bundle exceeding 500 KB.
- All 42 `queryFn`/`mutationFn` implementations in 24 changed TSX files match the pre-revision commit structurally. Financial query URLs, mutation payloads, and report calculations are preserved.
- `receipt.ts`, `sales-note.ts`, `credit-note.ts`, `SalesNoteModal.tsx`, and `note-logo.png` have no diff against the pre-revision commit. The real sales-note iframe was opened from checkout and transaction reprint. Physical printer output was not run.
- Login: empty input validation, wrong-password error, show/hide password, successful local login, and both themes.
- Navigation: all 15 existing destinations opened; mobile menu opens, navigation closes it, and Escape closes modal dialogs. Laravel reference route correctly shows its empty-bundle state with this local backend.
- Dashboard: year change, POS navigation, light/dark rendering, and the skip link. Enter on the skip link focuses `main-content` without changing the hash route. Enter toggles the theme.
- POS: product search and category tabs; out-of-stock controls disabled; add/increase/decrease/remove/clear cart controls; payment dialog; insufficient cash and excessive discount guards; customer selector and credit fields; exact-cash control; isolated cash checkout and sales-note preview. Mobile cart jump reaches the checkout panel.
- Product form: search, owner/category/TAX filters, empty search state, add/edit dialogs, item type changes, creation and edit of the disposable UI product, and opening deletion confirmation without deleting real records.
- Customer and supplier dialogs open and dismiss. Transaction detail and return dialogs open; return confirmation remains disabled until its acknowledgement is checked; cancelling leaves the transaction intact.
- Debt: receivable/payable tabs, age buckets, status filters, supplier modal, required-field validation, payment history layout, and native disabled payment guards during server-date loading/failure. Save of an empty payable form is blocked by native validity checks.
- Expense form: empty and negative amount controls disabled; Enter on the valid submit button saves an isolated test expense and refreshes its table.
- Reports: September selection, CSV and PDF downloads, all five cash/report tabs, daily CSV download, Excel source switch, keyboard month change, formula disclosure controls, parameter dialog, loading/error/recovery, and dynamic workbook filename.
- Import inspection: issues checkbox toggles, pagination changes from page 1 to 2 and back, sources/groups retain their existing handlers and confirmation guard. No import commit is executed.
- Breakpoints: dashboard, POS, and monthly report checked at 320, 390, 768, 1024, and 1440 pixels. All other navigation destinations checked at 390 pixels. Document width stays within the viewport. Dense data tables retain scoped horizontal scrolling. Repeated row controls are sampled through their shared action handlers.
- Payment modal at 320 pixels: client and scroll width both 270 pixels, inside its 280-pixel dialog; full content remains reachable by vertical scroll.
- Shared controls and checkbox label hit areas are at least 44 pixels. Dashboard currency values remain whole at 390 pixels after switching the narrow metric strip to one column.

Local screenshots and geometry logs are retained under `Aplikasibian2-main/.cache/ui-redesign/`: `dashboard-light.png`, `dashboard-dark.png`, `dashboard-mobile.png`, `report-desktop.png`, `report-dark.png`, `payment-mobile.png`, `mobile-qa.json`, and `breakpoint-qa.json`.

Measured contrast with the installed skill checker: body text 14.42:1; light muted text 5.39:1; light primary 11.55:1; dark muted text 7.27:1; amber payment action 9.11:1; amber notice text 7.35:1; rail labels 9.28:1; dark input boundary 4.81:1; light input boundary 3.56:1 (non-text threshold); light success text 5.83:1; success total on light amber 4.92:1.

## Delivery Gate

Hard Gate:

- R02 PASS: revised page text, shell, and document title contain no em dashes.
- R03 PASS: the recorded breakpoint matrix has no page-level horizontal overflow; mobile amounts stay whole and dense tables scroll locally.
- R17 PASS: dashboard/report numbers come from existing API data; no promotional statistics added.
- R18 PASS: no testimonials or invented people added.
- R23 PASS: the existing shop logo/photo and navigation are reused; no fabricated visual assets.
- R24 PASS: all existing navigation routes were opened and matched their headings.
- R25 PASS: measured shared text/semantic colors exceed AA; input boundaries exceed the non-text threshold in both themes.
- R26 PASS: visible controls retain real handlers/targets; exports disable when their required data is unavailable.
- R27 PASS: loading, empty, and retryable error blocks remain; supplier/server-date failures now explain disabled payment.
- R28 PASS: no FAQ is introduced.
- R32 PASS: real buttons/labels, visible focus, Enter activation, native form validity, skip-link focus, and Escape dismissal are verified.
- R33 PASS: UI edits were authored in TSX/CSS source, not patched by generated string-replacement scripts.
- R34 PASS: light/dark dashboard, report, login, and mobile foundations are rendered and inspected.
- R35 PASS: final build/lint and recorded navigation/control checks above are complete; repeated data-row controls use the same audited handlers. Physical printing and irreversible production writes remain outside this UI check.
- R36 PASS: no invented security/performance/compliance claims; unsupported Laravel parity claim removed.
- R37 PASS: direction and explicit dials were declared before implementation.
- R38 PASS: real source data and assets are used; local UI fixtures remain confined to the test database.

Purpose Gate:

- R01 PASS: navy/amber reflect the workshop identity; chart fills distinguish existing financial series.
- R04 PASS: icons identify the actual domain actions listed above.
- R06 PASS: heading/body/numeric fonts have explicit roles; no decorative oversized terminal typography.
- R07 PASS: no decorative grid, blueprint, or dot background.
- R08 PASS: arrows remain only for actual stock transitions, not general button decoration.
- R09 PASS: badges identify actual record status, category, owner, or SKU; no marketing capsules.
- R10 PASS: no glassmorphism.
- R12 PASS: modal shadow identifies elevation; regular panels are flat.
- R13 PASS: no glow decoration; the previous glow utility is disabled.
- R14 PASS: dashboard focal metric, inventory strip, financial ledger, and catalog/cart have distinct hierarchies.
- R19 PASS: hover/press feedback fits MOTION 1; automatic pulses and entrances are removed or disabled.
- R22 PASS: existing storefront photograph replaces generic illustration.

Liveliness:

- Dials PASS: ENERGY 2 / RHYTHM 2 / MOTION 1 are explicit.
- Dial consistency PASS: restrained motion, focused amber, and differentiated ledger/catalog compositions match the declared dials.
- Focal points PASS: the main total, current report, selected record, or checkout action leads each screen.
- Structural whitespace PASS: headings, toolbars, records, and summaries have consistent spacing groups.
- Accent PASS: amber marks navigation and checkout emphasis; semantic red/green remains reserved for record meaning.
- Identity motif PASS: the supplied shop mark, navy rail, amber selection, and aligned Rupiah figures repeat throughout.
- Design Read PASS: recorded before source edits.

Craftsmanship and locks:

- C1 PASS: major visual choices have a written purpose above.
- C2 PASS: existing routes, filters, forms, dialogs, downloads, and guards retain real behavior.
- C3 PASS: screens are composed around actual workshop records and financial workflows.
- C4 PASS: keyboard, loading/error/empty, themes, narrow dialogs, and the breakpoint matrix are checked.
- C5 PASS: source data and real assets are retained; no fabricated product claims.
- R05 PASS: no marketing hero, pricing template, testimonial grid, or generic section filler.
- R11 PASS: panel/control/status radii differ; no universal pills.
- R15 PASS: action labels describe saving, paying, filtering, viewing, printing, or downloading.
- R16 PASS: no AI marketing buzzwords added.
- R20 PASS: real workshop assets and ledger emphasis preserve Perkasa Jaya identity.
- R21 PASS: light is the default; the real theme control preserves user preference.
- R29 PASS: navy/paper plus amber define the core palette; red/green/blue communicate domain status.
- R30 PASS: the layout follows the shop's actual operational hierarchy rather than copying a named product.
- R31 PASS: palette, fonts, layout, spacing, panels, image use, and motion all have one-line purposes above.
