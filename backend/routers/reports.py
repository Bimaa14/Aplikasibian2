"""REPORT spreadsheet + ekspor CSV dan PDF, dari ledger bertanggal."""

import csv
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from lib.auth import require_admin
from lib.db import db
from lib.dates import today_iso
from lib.excel_rules import store_report
from lib.reporting import live_purchases
from lib.sales import month_bounds
from routers.excel_reports import live_events
from models.report import ExpenseByCategory, MonthlyReport, TopProduct

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_admin)])

BULAN_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _month_label(month: str) -> str:
    try:
        y, m = month.split("-")
        return f"{BULAN_ID[int(m) - 1]} {y}"
    except (ValueError, IndexError):
        return month


def _rupiah(value: float) -> str:
    return "Rp " + f"{int(round(value)):,}".replace(",", ".")


async def _available_months(events=None) -> List[str]:
    events = await live_events() if events is None else events
    months = {e['date'][:7] for e in events if e.get('date')}
    months.add(today_iso()[:7])
    return sorted(months, reverse=True)


async def _build_report(month: str) -> MonthlyReport:
    bounds = month_bounds(month)
    events = await live_events()
    period = [e for e in events if e.get('date', '')[:7] == month]
    result = store_report(events, month)
    txs = await db.transactions.find({'$or': [{'date_key': bounds}, {'return_date': bounds}],
                                      'status': {'$in': ['completed', 'returned']}}, {'_id': 0}).to_list(None)
    sold = [t for t in txs if t.get('date_key', '')[:7] == month]
    returned = [t for t in txs if (t.get('return_date') or '')[:7] == month]
    service_fee_total = sum(e.get('fee', 0) for e in period if e['kind'] in ('cash_sale', 'credit_sale'))
    by_cat: dict = {}
    for e in period:
        if e['kind'] != 'expense':
            continue
        by_cat[e.get("category", "Lainnya")] = by_cat.get(e.get("category", "Lainnya"), 0) + e.get("amount", 0)
    new_receivables = sum(e['amount'] for e in period if e['kind'] == 'credit_sale')
    receivables_paid = sum(e['amount'] for e in period if e['kind'] == 'credit_payment')
    purchases = await live_purchases()
    stock_in_total = sum(p.get('amount', 0) for p in purchases if p.get('date', '')[:7] == month)

    # produk terlaris bulan ini
    agg: dict = {}
    for e in period:
        if e['kind'] not in ('cash_sale', 'credit_sale'):
            continue
        key = e.get('product_id') or e.get('name') or '-'
        row = agg.setdefault(key, {'name': e.get('name') or '-', 'sku': '', 'qty': 0, 'revenue': 0.0})
        row['qty'] += e.get('qty', 0)
        row['revenue'] += e.get('amount', 0)
    if agg:
        prods = await db.products.find({"id": {"$in": list(agg)}}, {"_id": 0, "id": 1, "sku": 1}).to_list(2000)
        sku_by_id = {p["id"]: p.get("sku", "") for p in prods}
        for pid, row in agg.items():
            row["sku"] = sku_by_id.get(pid, "")
    top = sorted((row for row in agg.values() if row['qty'] > 0), key=lambda r: r["revenue"], reverse=True)[:5]

    return MonthlyReport(
        month=month,
        month_label=_month_label(month),
        revenue_total=result['pendapatan'],
        barang_revenue=result['pendapatan'] - result['spooring'],
        jasa_revenue=result['spooring'],
        cost_of_goods=result['modal'],
        gross_profit_barang=result['laba'],
        service_fee_total=service_fee_total,
        expenses_total=result['pengeluaran'],
        expenses_by_category=[
            ExpenseByCategory(category=c, amount=a) for c, a in sorted(by_cat.items(), key=lambda kv: -kv[1])
        ],
        net_profit=result['nett_laba'],
        supplier_payments=result['supplier'],
        capital_balance=result['total_modal'],
        spooring_net=result['nett_spooring'],
        oil_revenue=sum(e['amount'] for e in period if e['kind'] == 'cash_sale' and (e.get('category') or '').upper() == 'OIL'),
        transaction_count=len(sold),
        returned_count=len(returned),
        returned_amount=sum(t.get("total_amount", 0) for t in returned),
        new_receivables=new_receivables,
        receivables_paid=receivables_paid,
        stock_in_total=stock_in_total,
        top_products=[TopProduct(**t) for t in top],
        available_months=await _available_months(events),
    )


@router.get("/monthly", response_model=MonthlyReport)
async def monthly_report(month: Optional[str] = None):
    return await _build_report(month or today_iso()[:7])


@router.get("/monthly/csv")
async def monthly_report_csv(month: Optional[str] = None):
    r = await _build_report(month or today_iso()[:7])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Laporan REPORT Spreadsheet", r.month_label])
    w.writerow([])
    w.writerow(["Keterangan", "Jumlah (Rp)"])
    w.writerow(["Pendapatan selain spooring", round(r.barang_revenue)])
    w.writerow(["Laba spooring", round(r.jasa_revenue)])
    w.writerow(["TOTAL PENDAPATAN", round(r.revenue_total)])
    w.writerow(["Modal REPORT", round(r.cost_of_goods)])
    w.writerow(["LABA REPORT (tanpa oli/spooring)", round(r.gross_profit_barang)])
    w.writerow(["Komisi montir (sudah dihitung)", round(r.service_fee_total)])
    w.writerow(["Pembayaran distributor", round(r.supplier_payments)])
    w.writerow(["Saldo modal setelah distributor", round(r.capital_balance)])
    w.writerow(["Spooring bersih", round(r.spooring_net)])
    w.writerow(["Penjualan oli tunai (terpisah)", round(r.oil_revenue)])
    w.writerow([])
    w.writerow(["Pengeluaran per Kategori", ""])
    for e in r.expenses_by_category:
        w.writerow([e.category, round(e.amount)])
    w.writerow(["TOTAL PENGELUARAN", round(r.expenses_total)])
    w.writerow([])
    w.writerow(["LABA BERSIH", round(r.net_profit)])
    w.writerow([])
    w.writerow(["Jumlah Transaksi", r.transaction_count])
    w.writerow(["Transaksi Retur", r.returned_count])
    w.writerow(["Nilai Retur", round(r.returned_amount)])
    w.writerow(["Piutang Baru", round(r.new_receivables)])
    w.writerow(["Pembayaran piutang bersih termasuk pembalikan retur", round(r.receivables_paid, 2)])
    w.writerow(["Nilai Barang Masuk", round(r.stock_in_total)])
    w.writerow([])
    w.writerow(["Produk Terlaris", "Qty", "Pendapatan (Rp)"])
    for p in r.top_products:
        w.writerow([f"{p.name} ({p.sku})", p.qty, round(p.revenue)])

    buf.seek(0)
    filename = f"laporan-bengkel-{r.month}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly/pdf")
async def monthly_report_pdf(month: Optional[str] = None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    r = await _build_report(month or today_iso()[:7])
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, title=f"Laporan Bengkel {r.month_label}",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1x", parent=styles["Heading1"], fontSize=16, spaceAfter=2)
    sub = ParagraphStyle("subx", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#555555"))
    h2 = ParagraphStyle("h2x", parent=styles["Heading2"], fontSize=11, spaceBefore=7, spaceAfter=3)

    def money_table(rows, highlight_rows=()):
        t = Table(rows, colWidths=[110 * mm, 44 * mm], hAlign="LEFT")
        style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]
        for idx in highlight_rows:
            style += [
                ("FONTNAME", (0, idx), (-1, idx), "Helvetica-Bold"),
                ("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#FEF3C7")),
            ]
        t.setStyle(TableStyle(style))
        return t

    story = [
        Paragraph("Laporan REPORT — Perkasa Jaya", h1),
        Paragraph(f"Periode: {r.month_label} &nbsp;•&nbsp; Ban &amp; Servis Otomotif", sub),
        Spacer(1, 6),
        Paragraph("Pendapatan &amp; Laba", h2),
        money_table(
            [
                ["Keterangan", "Jumlah"],
                ["Pendapatan selain spooring", _rupiah(r.barang_revenue)],
                ["Laba Spooring", _rupiah(r.jasa_revenue)],
                ["Total Pendapatan", _rupiah(r.revenue_total)],
                ["Modal REPORT", _rupiah(r.cost_of_goods)],
                ["Laba REPORT (tanpa oli/spooring)", _rupiah(r.gross_profit_barang)],
                ["Komisi montir (sudah dihitung)", _rupiah(r.service_fee_total)],
                ["Pembayaran distributor", _rupiah(r.supplier_payments)],
                ["Saldo modal setelah distributor", _rupiah(r.capital_balance)],
                ["Spooring bersih", _rupiah(r.spooring_net)],
                ["Penjualan oli tunai (terpisah)", _rupiah(r.oil_revenue)],
            ],
            highlight_rows=(3, 5),
        ),
        Paragraph("Pengeluaran Operasional", h2),
        money_table(
            [["Kategori", "Jumlah"]]
            + ([[e.category, _rupiah(e.amount)] for e in r.expenses_by_category] or [["(tidak ada)", _rupiah(0)]])
            + [["Total Pengeluaran", _rupiah(r.expenses_total)]],
            highlight_rows=(len(r.expenses_by_category) + 1 if r.expenses_by_category else 2,),
        ),
        Paragraph("Laba Bersih", h2),
        money_table([["Keterangan", "Jumlah"], ["Laba REPORT setelah pengeluaran", _rupiah(r.net_profit)]], highlight_rows=(1,)),
        Paragraph("Ringkasan Aktivitas", h2),
        money_table(
            [
                ["Keterangan", "Nilai"],
                ["Jumlah Nota Penjualan", str(r.transaction_count)],
                ["Transaksi Retur", f"{r.returned_count} ({_rupiah(r.returned_amount)})"],
                ["Piutang Baru (tempo)", _rupiah(r.new_receivables)],
                ["Pembayaran piutang bersih", _rupiah(r.receivables_paid)],
                ["Nilai Barang Masuk dari Distributor", _rupiah(r.stock_in_total)],
            ]
        ),
    ]

    if r.top_products:
        top_rows = [["Produk / Jasa Terlaris", "Qty", "Pendapatan"]] + [
            [f"{p.name} ({p.sku})" if p.sku else p.name, str(p.qty), _rupiah(p.revenue)] for p in r.top_products
        ]
        t = Table(top_rows, colWidths=[104 * mm, 18 * mm, 32 * mm], hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        story += [Paragraph("Produk Terlaris", h2), t]

    story += [Spacer(1, 8), Paragraph("Dicetak otomatis oleh BengKasir — POS &amp; Mini ERP Bengkel", sub)]
    doc.build(story)
    buf.seek(0)
    filename = f"laporan-bengkel-{r.month}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
