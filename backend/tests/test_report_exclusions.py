"""Report baseline exclusions preserve history and recognize future additions.

All database reads use in-memory fakes; these tests never contact the app database.
"""
from copy import deepcopy
from datetime import datetime, timezone
import re
from types import SimpleNamespace

import pytest

from lib import reporting
from lib.excel_rules import store_report
from routers import dashboard, excel_reports, reports


def matches(document, query):
    for key, expected in query.items():
        if key == '$or':
            if not any(matches(document, part) for part in expected):
                return False
            continue
        value = document.get(key)
        if isinstance(expected, dict):
            for operator, operand in expected.items():
                if operator == '$exists' and (key in document) != operand:
                    return False
                if operator == '$ne' and value == operand:
                    return False
                if operator == '$in' and value not in operand:
                    return False
                if operator == '$type' and operand == 'string' and not isinstance(value, str):
                    return False
                if operator == '$gte' and (value is None or value < operand):
                    return False
                if operator == '$lt' and (value is None or value >= operand):
                    return False
                if operator == '$lte' and (value is None or value > operand):
                    return False
                if operator == '$regex' and (not isinstance(value, str) or re.search(operand, value) is None):
                    return False
        elif value != expected:
            return False
    return True


class Cursor:
    def __init__(self, documents):
        self.documents = deepcopy(documents)

    async def to_list(self, length):
        return deepcopy(self.documents if length is None else self.documents[:length])

    def sort(self, key, direction):
        self.documents.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self

    def __aiter__(self):
        async def iterate():
            for document in self.documents:
                yield deepcopy(document)
        return iterate()


class Collection:
    def __init__(self, documents=()):
        self.documents = deepcopy(list(documents))

    def find(self, query, projection=None):
        return Cursor([d for d in self.documents if matches(d, query)])


@pytest.fixture
def memory_db(monkeypatch):
    database = SimpleNamespace(**{name: Collection() for name in (
        'excel_events', 'transfer_history', 'transactions', 'transaction_details',
        'accounts_receivable', 'accounts_payable', 'expenses', 'products',
        'purchase_history', 'stock_in',
    )})
    for module in (dashboard, excel_reports, reports, reporting):
        monkeypatch.setattr(module, 'db', database)
    monkeypatch.setattr(excel_reports, 'dataset', lambda _: {'events': [], 'transfers': []})
    monkeypatch.setattr(excel_reports, 'reference_sale_rows', lambda: {'digest': 'baseline', 'rows': {}})
    return database


def add_invoice(database, identifier, method='cash', **metadata):
    transaction = dict(id=identifier, date_key='2026-09-30', invoice_number=identifier,
                       date=datetime(2026, 9, 30, tzinfo=timezone.utc),
                       payment_method=method, total_amount=10000, total_cost=5000, total_profit=5000,
                       service_fee=0, barang_amount=10000, jasa_amount=0, status='completed', **metadata)
    detail = dict(id=identifier + '-line', transaction_id=identifier, product_id='item',
                  product_name='Tyre', product_type='barang', category='TIRE',
                  qty=1, price=10000, subtotal=10000, cost_price=5000, service_fee=0,
                  spreadsheet_profit=5000)
    database.transactions.documents.append(transaction)
    database.transaction_details.documents.append(detail)
    return transaction


@pytest.mark.parametrize('method', ['cash', 'credit', 'qris', 'transfer_bca'])
@pytest.mark.parametrize('include_imported', [True, False])
async def test_excluded_invoices_and_returns_stay_in_history_but_future_sales_count(memory_db, method, include_imported):
    add_invoice(memory_db, 'excluded', method, report_excluded=True, return_date='2026-10-01')
    add_invoice(memory_db, 'future', method)
    add_invoice(memory_db, 'explicitly-included', method, report_excluded=False)
    baseline = dict(date='2026-09-29', kind='cash_sale', amount=20000,
                    profit=8000, fee=0, category='TIRE', import_source='store_current',
                    sheet='SELLING CASH', row=2)
    memory_db.excel_events.documents.append(baseline)
    before = deepcopy(vars(memory_db))

    events = await excel_reports.live_events(include_imported)

    assert not any(e.get('transaction_id') == 'excluded' for e in events)
    assert {e['transaction_id'] for e in events if e.get('transaction_id')} == {'future', 'explicitly-included'}
    assert sum(e['kind'] == 'transfer' for e in events) == (2 if method not in ('cash', 'credit') else 0)
    assert baseline in events if include_imported else baseline not in events
    assert all(before[name].documents == collection.documents for name, collection in vars(memory_db).items())


async def test_payment_and_expense_exclusions_preserve_imported_rows_and_future_receipts(memory_db):
    memory_db.excel_events.documents.extend([
        dict(date='2026-09-01', kind='expense', amount=100, category='Operasional'),
        dict(date='2026-09-01', kind='supplier_payment', amount=1000),
    ])
    memory_db.transfer_history.documents.append(dict(date='2026-09-01', amount=150))
    memory_db.accounts_receivable.documents.append(dict(id='receivable', payments=[
        dict(id='excluded-ar', payment_date='2026-09-30', amount=6000, profit_amount=3000,
             method='qris', report_excluded=True),
        dict(id='future-ar', payment_date='2026-09-30', amount=2000, profit_amount=600, method='qris'),
        dict(id='included-ar', payment_date='2026-09-30', amount=1000, profit_amount=0,
             method='transfer_bca', report_excluded=False),
    ]))
    memory_db.accounts_payable.documents.append(dict(id='payable', payments=[
        dict(id='excluded-ap', payment_date='2026-09-30', amount=4000, report_excluded=True),
        dict(id='future-ap', payment_date='2026-09-30', amount=500),
    ]))
    memory_db.expenses.documents.extend([
        dict(date='2026-09-30', amount=300, category='Operasional', report_excluded=True),
        dict(date='2026-09-30', amount=200, category='Operasional'),
        dict(date='2026-09-30', amount=50, category='Operasional', report_excluded=False),
        dict(date='2026-09-01', amount=100, category='Operasional', import_source='store_current'),
    ])
    before = {name: deepcopy(c.documents) for name, c in vars(memory_db).items()}

    events = await excel_reports.live_events()
    result = store_report(events, '2026-09')

    assert not any(e.get('payment_id', '').startswith('excluded') for e in events)
    assert result['pendapatan'] == 3000
    assert result['laba'] == 600
    assert result['supplier'] == 1500
    assert result['pengeluaran'] == 350
    assert sum(e['amount'] for e in events if e['kind'] == 'transfer') == 3150
    assert before == {name: c.documents for name, c in vars(memory_db).items()}


def returned_receivable(refund_amount):
    return dict(id='returned-debt', return_date='2026-10-01', refund_amount=refund_amount, payments=[
        dict(id='excluded', payment_date='2026-09-30', amount=6000, profit_amount=3000,
             method='qris', report_excluded=True),
        dict(id='included', payment_date='2026-09-30', amount=4000, profit_amount=1000, method='qris'),
    ])


@pytest.mark.parametrize('recorded_refund,reported_refund', [
    (10000, 4000), (9000, 3000), (3000, 0), (20000, 4000), (float('inf'), 0), (float('nan'), 0),
])
async def test_refund_does_not_reverse_excluded_receipts_or_exceed_counted_amount(memory_db, recorded_refund, reported_refund):
    memory_db.accounts_receivable.documents.append(returned_receivable(recorded_refund))

    events = await excel_reports.live_events()
    returns = [e for e in events if e.get('is_return')]
    refund = [e for e in returns if e['kind'] == 'credit_payment']
    transfer = [e for e in returns if e['kind'] == 'transfer']

    assert sum(e['amount'] for e in refund) == -reported_refund
    assert sum(e['amount'] for e in transfer) == -reported_refund
    assert sum(e['profit'] for e in refund) == (-1000 if reported_refund else 0)
    assert store_report(events, '2026-09')['laba'] == 1000
    assert not any(e.get('payment_id') == 'excluded' for e in events)


async def test_fully_excluded_payments_have_no_receipt_transfer_or_refund(memory_db):
    debt = returned_receivable(10000)
    debt['payments'][1]['report_excluded'] = True
    memory_db.accounts_receivable.documents.append(debt)

    assert await excel_reports.live_events() == []
    assert len(memory_db.accounts_receivable.documents[0]['payments']) == 2


async def test_unmarked_refunds_keep_existing_full_receipt_and_profit_reversal(memory_db):
    debt = returned_receivable(10000)
    debt['payments'][0].pop('report_excluded')
    memory_db.accounts_receivable.documents.append(debt)

    events = await excel_reports.live_events()
    september = store_report(events, '2026-09')
    october = store_report(events, '2026-10')

    assert september['pendapatan'] == 10000 and september['laba'] == 4000
    assert october['pendapatan'] == -10000 and october['laba'] == -4000
    assert sum(e['amount'] for e in events if e['kind'] == 'transfer') == 0


async def test_future_payment_on_excluded_invoice_is_recognized_independently(memory_db):
    add_invoice(memory_db, 'baseline-credit', 'credit', report_excluded=True)
    memory_db.accounts_receivable.documents.append(dict(
        id='debt', transaction_id='baseline-credit', issued_date='2026-09-30', payments=[
            dict(id='future-payment', payment_date='2026-10-01', amount=2500, profit_amount=5000),
        ],
    ))

    events = await excel_reports.live_events()

    assert not any(e['kind'] == 'credit_sale' for e in events)
    assert store_report(events, '2026-09')['pendapatan'] == 0
    assert store_report(events, '2026-10')['pendapatan'] == 2500
    assert store_report(events, '2026-10')['laba'] == 5000


async def test_imported_return_is_retained_unless_invoice_explicitly_excluded(memory_db):
    add_invoice(memory_db, 'imported', import_source='store', return_date='2026-10-01')
    add_invoice(memory_db, 'excluded-imported', import_source='store', return_date='2026-10-01', report_excluded=True)
    baseline = dict(date='2026-09-30', kind='cash_sale', amount=10000, profit=5000, fee=0, category='TIRE')
    memory_db.excel_events.documents.append(baseline)

    events = await excel_reports.live_events()

    assert baseline in events
    returns = [e for e in events if e.get('is_return')]
    assert len(returns) == 1 and returns[0]['transaction_id'] == 'imported'
    assert store_report(events, '2026-10')['pendapatan'] == -10000


async def test_monthly_display_counts_exclude_archived_sales_and_returns(memory_db):
    add_invoice(memory_db, 'excluded', report_excluded=True, return_date='2026-10-01')
    add_invoice(memory_db, 'visible', return_date='2026-10-01')
    memory_db.products.documents.append(dict(id='item', sku='item'))

    september = await reports._build_report('2026-09')
    october = await reports._build_report('2026-10')

    assert september.transaction_count == 1 and september.returned_count == 0
    assert september.revenue_total == 10000
    assert october.transaction_count == 0 and october.returned_count == 1
    assert october.returned_amount == 10000 and october.revenue_total == -10000


async def test_dashboard_excludes_report_history_but_retains_inventory_balances_and_recent_invoices(memory_db, monkeypatch):
    monkeypatch.setattr(dashboard, 'today_iso', lambda: '2026-09-30')
    add_invoice(memory_db, 'excluded', report_excluded=True)
    add_invoice(memory_db, 'visible')
    memory_db.products.documents.append(dict(id='item', name='Tyre', sku='item', type='barang',
                                             active=True, stock=2, cost_price=5000, selling_price=10000))
    memory_db.expenses.documents.extend([
        dict(date='2026-09-30', amount=300, category='Operasional', report_excluded=True),
        dict(date='2026-09-30', amount=100, category='Operasional'),
    ])
    for name, amount, paid in [('accounts_receivable', 9000, 2000), ('accounts_payable', 20000, 5000)]:
        getattr(memory_db, name).documents.append(dict(
            id=name, status='partial', amount=amount, paid_amount=paid, due_date='2026-12-01', payments=[
                dict(id='archived-payment', payment_date='2026-09-30', amount=paid,
                     profit_amount=500, report_excluded=True),
            ],
        ))
    before = {name: deepcopy(c.documents) for name, c in vars(memory_db).items()}

    result = await dashboard.dashboard(2026)

    assert result.transaction_count == 1
    assert result.total_revenue == result.today_revenue == 10000
    assert result.gross_profit == result.total_cost == 5000
    assert result.expenses_total == 100 and result.net_profit == 4900
    assert result.tire_qty_out == 1
    assert result.revenue_by_day[-1].revenue == 10000 and result.revenue_by_day[-1].profit == 5000
    assert result.receivables_outstanding == 7000 and result.payables_outstanding == 15000
    assert len(result.low_stock) == 1 and result.low_stock[0].stock == 2
    assert {t.id for t in result.recent_transactions} == {'excluded', 'visible'}
    assert all('report_excluded' not in t.model_dump() for t in result.recent_transactions)
    assert before == {name: c.documents for name, c in vars(memory_db).items()}
