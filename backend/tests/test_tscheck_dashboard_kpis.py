"""Dashboard KPI: five financial KPIs populate and overdue receivables/payables surface with correct shape."""


def test_dashboard_kpis_present_and_overdue_seed_rows_surface(admin_client):
    r = admin_client.get("/dashboard")
    assert r.status_code == 200, r.text[:200]
    stats = r.json()

    for key in (
        "total_revenue",
        "gross_profit",
        "net_profit",
        "receivables_outstanding",
        "payables_outstanding",
        "receivables_overdue",
        "payables_overdue",
        "overdue_receivables",
        "overdue_payables",
        "low_stock",
    ):
        assert key in stats, f"missing dashboard field {key}"

    assert stats["total_revenue"] > 0
    assert stats["receivables_outstanding"] > 0
    assert stats["payables_outstanding"] > 0

    # Seed fact: overdue receivable INV-260918-0001 (Trans Logistik) and overdue payable GT/PO/2601
    rx_invoices = [x["invoice_number"] for x in stats["overdue_receivables"]]
    px_invoices = [x["invoice_number"] for x in stats["overdue_payables"]]
    assert "INV-260918-0001" in rx_invoices, f"expected seeded overdue receivable, got {rx_invoices}"
    assert "GT/PO/2601" in px_invoices, f"expected seeded overdue payable, got {px_invoices}"

    # low stock seed: SPR-001 and BAN-003 should be present among low_stock skus
    low_stock_skus = [p["sku"] for p in stats["low_stock"]]
    assert "SPR-001" in low_stock_skus, f"expected SPR-001 in low stock, got {low_stock_skus}"
