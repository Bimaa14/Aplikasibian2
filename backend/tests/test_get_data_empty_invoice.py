"""Blank source invoices must remain blank in Apps Script compatible exports."""
import pytest

from lib import custom_report


@pytest.mark.parametrize('invoice', ['', 'SOURCE-42', None])
async def test_live_get_data_preserves_explicit_source_invoice(monkeypatch, invoice):
    async def report(*args, **kwargs):
        return {'rows': [dict(date='2026-02-02', product_name='Example tire',
                             invoice_number='XL-generated', source_invoice=invoice,
                             payment_method='credit', category='TIRE', cash_subtotal=100,
                             qty=1, source_sheet='SELLING CREDIT', source_row=686)]}
    monkeypatch.setattr(custom_report, 'sales_report', report)
    async def empty_archive(*args, **kwargs):
        return []
    monkeypatch.setattr(custom_report, 'archived_zero_sales', empty_archive)
    result = await custom_report.get_data_report('2026-02', page_size=None)
    assert result['rows'][0]['invoice'] == (invoice if invoice is not None else 'XL-generated')
    assert result['total'] == 100
