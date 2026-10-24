"""Daily H6:H9 detail follows DAILY REPORT cash/expense recognition."""
import pytest
from routers import books


@pytest.mark.asyncio
async def test_daily_breakdown_and_csv(monkeypatch):
    events = [
        dict(date="2026-09-25", kind="cash_sale", amount=100000, profit=25000, fee=5000, category="TIRE"),
        dict(date="2026-09-25", kind="cash_sale", amount=40000, profit=10000, fee=0, category="OIL", method="qris"),
        dict(date="2026-09-25", kind="cash_sale", amount=20000, profit=10000, fee=10000, category="SERVICE"),
        dict(date="2026-09-25", kind="credit_payment", amount=10000, profit=2000),
        dict(date="2026-09-25", kind="expense", amount=3000),
        dict(date="2026-09-26", kind="cash_sale", amount=999, profit=999, category="OIL"),
    ]

    async def live_events():
        return events

    async def daily_inputs(day):
        return dict(modal_bian=0, laba_bian=0, parameters_saved=False)

    monkeypatch.setattr(books, "live_events", live_events)
    monkeypatch.setattr(books, '_daily_inputs', daily_inputs)
    report = await books._daily_data("2026-09-25")
    assert report["modal"] == 78000
    assert report["laba"] == 24000
    assert report["spooring"] == 10000
    assert report["oil_revenue"] == 40000
    assert report["oil_benefit"] == 10000
    assert report["net_cash"] == 112000
    response = await books.daily_csv("2026-09-25")
    csv = "".join([chunk async for chunk in response.body_iterator])
    assert "Modal,78000" in csv
    assert "Pendapatan oli,40000" in csv
    assert "Benefit oli,10000" in csv


@pytest.mark.asyncio
async def test_empty_daily_breakdown(monkeypatch):
    async def live_events():
        return []

    async def daily_inputs(day):
        return dict(modal_bian=0, laba_bian=0, parameters_saved=False)

    monkeypatch.setattr(books, "live_events", live_events)
    monkeypatch.setattr(books, '_daily_inputs', daily_inputs)
    report = await books._daily_data("2026-09-25")
    assert all(report[key] == 0 for key in ("modal", "laba", "spooring", "oil_revenue", "oil_benefit", "net_cash"))
