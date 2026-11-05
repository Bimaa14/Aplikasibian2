"""Source zero rows affect Get Data ranges without creating POS transactions.

All writes use the existing fixture's random, owned bian_safety_test_* database.
"""
from decimal import Decimal

import pytest

from lib.custom_report import get_data_report
from lib.sales import GET_DATA_ROW_LIMIT, archived_zero_sales, sales_report
from tests.test_financial_safety import isolated


def archived(identifier='archived-zero', row=2, **changes):
    event = dict(id=identifier, import_source='store_current', kind='cash_sale',
                 sheet='SELLING CASH', source_sheet='SELLING CASH', row=row, source_row=row,
                 date='2026-09-01', invoice='', customer='', name='Archived tire',
                 qty=0, amount=0, cash_subtotal=0, price=1000, base_price=1000,
                 category='TIRE', owner='bian', tax=1)
    event.update(changes)
    return event


async def test_zero_archive_is_get_data_row_and_tax_count_without_a_pos_invoice(isolated):
    database, _, _, _ = isolated
    await database.excel_events.insert_one(archived())

    ledger = await sales_report('2026-09', page_size=None)
    get_data = await get_data_report('2026-09', page_size=None)

    assert ledger['rows'] == [] and ledger['line_count'] == ledger['transaction_count'] == 0
    assert ledger['tax_eligible_line_count'] == 1
    assert ledger['tax_base'] == ledger['tax_amount'] == 0
    assert get_data['count'] == get_data['summarized_count'] == 1
    assert get_data['total'] == get_data['full_total'] == get_data['pph_final'] == 0
    row = get_data['rows'][0]
    assert row['invoice'] == '' and row['source_sheet'] == 'SELLING CASH' and row['source_row'] == 2
    assert row['amount_without_vat'] is row['vat_amount'] is None
    assert await database.transactions.count_documents({}) == 0
    assert await database.transaction_details.count_documents({}) == 0
    assert await database.excel_events.count_documents({}) == 1


@pytest.mark.parametrize('filters,expected', [
    ({'owner': 'bian'}, {'cash-bian', 'cash-oil'}),
    ({'owner': 'ibu'}, {'credit-ibu'}),
    ({'owner': 'unassigned'}, {'cash-unassigned'}),
    ({'category': 'TIRE'}, {'cash-bian', 'credit-ibu'}),
    ({'category': 'COMPLEMENTARY'}, {'cash-unassigned'}),
    ({'tax': '1'}, {'cash-bian', 'cash-oil'}),
    ({'tax': '0'}, {'credit-ibu'}),
    ({'tax': 'unassigned'}, {'cash-unassigned'}),
    ({'payment_method': 'credit'}, {'credit-ibu'}),
    ({'payment_method': 'cash'}, {'cash-bian', 'cash-oil', 'cash-unassigned'}),
    ({'payment_method': 'qris'}, set()),
    ({'owner': 'ibu', 'category': 'TIRE', 'tax': '0', 'payment_method': 'credit'}, {'credit-ibu'}),
])
async def test_zero_archive_honors_period_source_and_all_item_filters(isolated, filters, expected):
    database, _, _, _ = isolated
    events = [
        archived('cash-bian'),
        archived('credit-ibu', kind='credit_sale', sheet='SELLING CREDIT', source_sheet='SELLING CREDIT', owner='ibu', tax=0),
        archived('cash-unassigned', category='COMPLEMENTARY', owner=None, tax=None),
        archived('cash-oil', category='OIL'),
        archived('wrong-month', date='2026-08-31'),
        archived('next-month', date='2026-10-01'),
        archived('wrong-source', import_source='store'),
        archived('wrong-kind', kind='expense'),
        archived('not-zero-quantity', qty=1),
        archived('not-zero-amount', amount=1),
        archived('report-excluded', report_excluded=True),
    ]
    await database.excel_events.insert_many(events)

    result = await archived_zero_sales('2026-09', **filters)

    assert {event['id'] for event in result} == expected
    assert all('_id' not in event and 'transaction_id' not in event for event in result)
    assert all(event['payment_method'] == ('credit' if event['kind'] == 'credit_sale' else 'cash')
               for event in result)
    assert await database.transactions.count_documents({}) == 0


async def test_get_data_credit_zero_row_uses_source_category_without_master_tax(isolated):
    database, _, _, _ = isolated
    await database.excel_events.insert_many([
        archived('cash', tax=1),
        archived('credit', kind='credit_sale', sheet='SELLING CREDIT', source_sheet='SELLING CREDIT',
                 owner='ibu', tax=0, customer='Credit customer'),
        archived('credit-service', kind='credit_sale', sheet='SELLING CREDIT', source_sheet='SELLING CREDIT',
                 owner='ibu', tax=1, category='SERVICE'),
    ])

    report = await get_data_report('2026-09', owner='ibu', category='TIRE', tax='0',
                                   payment_method='credit', page_size=None)
    ledger = await sales_report('2026-09', owner='ibu', category='TIRE', tax='0', payment_method='credit')

    assert report['count'] == ledger['tax_eligible_line_count'] == 1
    assert report['rows'][0]['party'] == 'Credit customer'
    assert report['rows'][0]['payment_method'] == 'credit' and report['rows'][0]['invoice'] == ''
    assert report['total'] == 0 and ledger['transaction_count'] == ledger['line_count'] == 0
    assert (await get_data_report('2026-09', payment_method='qris'))['count'] == 0


async def test_zero_cash_row_occupies_996_cutoff_before_credit_without_changing_pos_counts(isolated):
    database, _, _, _ = isolated
    await database.excel_events.insert_one(archived(row=2))
    await database.transactions.insert_many([
        dict(id='cash-invoice', invoice_number='cash-invoice', source_invoice='', date_key='2026-09-01',
             status='completed', payment_method='cash'),
        dict(id='credit-invoice', invoice_number='credit-invoice', date_key='2026-09-01',
             status='completed', payment_method='credit'),
    ])
    cash_lines = [dict(
        id=f'cash-line-{index}', transaction_id='cash-invoice', product_name='Normal tire',
        product_id='product', qty=1, price=1000, subtotal=1000, cash_subtotal=1000,
        owner='bian', category='TIRE', tax=1, source_sheet='SELLING CASH', source_row=index + 3,
    ) for index in range(GET_DATA_ROW_LIMIT)]
    credit_line = dict(id='credit-line', transaction_id='credit-invoice', product_name='Credit tire',
                       product_id='product', qty=1, price=1200000, subtotal=1200000,
                       cash_subtotal=900000, owner='bian', category='TIRE', tax=0,
                       source_sheet='SELLING CREDIT', source_row=1)
    await database.transaction_details.insert_many(cash_lines + [credit_line])

    ledger = await sales_report('2026-09', page_size=None)
    report = await get_data_report('2026-09', page_size=None)

    expected_base = Decimal(GET_DATA_ROW_LIMIT - 1) * 1000
    assert ledger['tax_base'] == report['total'] == float(expected_base)
    assert ledger['full_tax_base'] == report['full_total'] == GET_DATA_ROW_LIMIT * 1000 + 900000
    assert ledger['tax_eligible_line_count'] == report['count'] == GET_DATA_ROW_LIMIT + 2
    assert report['summarized_count'] == GET_DATA_ROW_LIMIT
    assert ledger['tax_amount'] == report['pph_final'] == 4975
    assert report['rows'][0]['source_row'] == 2 and report['rows'][0]['amount'] == 0
    assert report['rows'][0]['invoice'] == ''
    assert report['rows'][-1]['payment_method'] == 'credit'
    assert report['rows'][-1]['source_row'] == 1
    assert ledger['transaction_count'] == 2 and ledger['line_count'] == GET_DATA_ROW_LIMIT + 1
    assert len(ledger['rows']) == GET_DATA_ROW_LIMIT + 1
    assert all(row['qty'] == 1 for row in ledger['rows'])
    assert await database.transactions.count_documents({}) == 2
    assert await database.transaction_details.count_documents({}) == GET_DATA_ROW_LIMIT + 1
