from unittest.mock import AsyncMock

from lib.reporting import daily_report
from routers import books


async def test_daily_print_details_match_cash_report_and_receipt_dates(monkeypatch):
    day = '2026-10-24'
    events = [
        dict(date=day, kind='cash_sale', amount=100000, profit=20000, fee=0, category='TIRE'),
        dict(date=day, kind='credit_payment', amount=500000, profit=200000),
        dict(date=day, kind='credit_payment', amount=50000, profit=0),
        dict(date=day, kind='transfer', amount=100000, method='transfer_bca'),
        dict(date=day, kind='transfer', amount=50000, bank='BCA'),
        dict(date=day, kind='transfer', amount=70000, method='qris'),
        dict(date=day, kind='transfer', amount=10000),
        dict(date='2026-10-23', kind='credit_payment', amount=300000, profit=150000),
        dict(date='2026-10-23', kind='transfer', amount=300000, method='edc'),
    ]
    monkeypatch.setattr(books, 'live_events', AsyncMock(return_value=events))
    monkeypatch.setattr(books, '_daily_inputs', AsyncMock(return_value={
        'modal_bian': 10000, 'laba_bian': 5000, 'parameters_saved': True,
    }))
    result = await books._daily_data(day)
    assert result['receivable_profit'] == 200000
    assert result['receivable_payments'] == 550000
    assert result['transfer_breakdown'] == {'transfer_bca': 150000, 'qris': 70000, 'other': 10000}
    assert sum(result['transfer_breakdown'].values()) == result['transfer_payments']
    assert result['parameters_saved'] is True
    for key, value in daily_report(events, day, 10000, 5000).items():
        assert result[key] == value


async def test_daily_print_details_include_refunds_without_recognizing_profit_twice(monkeypatch):
    day = '2026-10-24'
    events = [
        dict(date=day, kind='credit_payment', amount=50000, profit=50000),
        dict(date=day, kind='credit_payment', amount=-20000, profit=-10000, is_return=True),
        dict(date=day, kind='transfer', amount=50000, method='edc'),
        dict(date=day, kind='transfer', amount=-20000, method='edc', is_return=True),
        dict(date=day, kind='transfer', amount=25000, bank='DANAMON'),
    ]
    monkeypatch.setattr(books, 'live_events', AsyncMock(return_value=events))
    monkeypatch.setattr(books, '_daily_inputs', AsyncMock(return_value={
        'modal_bian': 0, 'laba_bian': 0, 'parameters_saved': False,
    }))
    result = await books._daily_data(day)
    assert result['receivable_profit'] == result['laba'] == 40000
    assert result['receivable_payments'] == 30000
    assert result['transfer_breakdown'] == {'edc': 30000, 'transfer_danamon': 25000}
    assert sum(result['transfer_breakdown'].values()) == result['transfer_payments'] == 55000
