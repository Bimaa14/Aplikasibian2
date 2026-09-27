"""Laporan bulanan laba-rugi + ekspor CSV dan PDF (pembukuan bengkel)."""

import csv
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from lib.auth import require_user
from lib.db import db
from lib.dates import today_iso
from models.report import ExpenseByCategory, MonthlyReport, TopProduct

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_user)])

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


async def _available_months() -> List[str]:
    keys = await db.transactions.distinct("date_key")
    expense_dates = await db.expenses.distinct("date")
    months = {str(k)[:7] for k in keys if k} | {str(d)[:7] for d in expense_dates if d}
    months.add(today_iso()[:7])
    return sorted(months, reverse=True)


async def _build_report(month: str) -> MonthlyReport:
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(status_code=400, detail="Format bulan harus YYYY-MM")
    prefix = {"$regex": f"^{month}"}

    txs = await db.transactions.find({"date_key": prefix}, {"_id": 0}).to_list(10000)
    completed = [t for t in txs if t.get("status") == "completed"]
    returned = [t for t in txs if t.get("status") == "returned"]

    revenue_total = sum(t.get("total_amount", 0) for t in completed)
    barang_revenue = sum(t.get("barang_amount", 0) for t in completed)
    jasa_revenue = sum(t.get("jasa_amount", 0) for t in completed)
    cost_of_goods = sum(t.get("total_cost", 0) for t in completed)
    service_fee_total = sum(t.get("service_fee", 0) for t in completed)
    total_profit = sum(t.get("total_profit", 0) for t in completed)

    expenses = await db.expenses.find({"date": prefix}, {"_id": 0}).to_list(5000)
    expenses_total = sum(e.get("amount", 0) for e in expenses)
    by_cat: dict = {}
    for e in expenses:
        by_cat[e.get("category", "Lainnya")] = by_cat.get(e.get("category", "Lainnya"), 0) + e.get("amount", 0)

    receivables = await db.accounts_receivable.find({}, {"_id": 0}).to_list(5000)
    tx_by_id = {t["id"]: t for t in txs}
    new_receivables = sum(r["amount"] for r in receivables if r.get("transaction_id") in tx_by_id)
    receivables_paid = sum(
        r["amount"] for r in receivables
        if r.get("transaction_id") in tx_by_id and r.get("status") == "paid"
    )

    stock_ins = await db.stock_in.find({"date_key": prefix}, {"_id": 0}).to_list(2000)
    stock_in_total = sum(s.get("total_amount", 0) for s in stock_ins)

    # produk terlaris bulan ini
    details = await db.transaction_details.find(
        {"transaction_id": {"$in": [t["id"] for t in completed]}}, {"_id": 0}
    ).to_list(20000)
    agg: dict = {}
    for d in details:
        key = d.get("product_id")
        row = agg.setdefault(key, {"name": d.get("product_name", "-"), "sku": "", "qty": 0, "revenue": 0.0})
        row["qty"] += d.get("qty", 0)
        row["revenue"] += d.get("subtotal", 0)
    if agg:
        prods = await db.products.find({"id": {"$in": list(agg)}}, {"_id": 0, "id": 1, "sku": 1}).to_list(2000)
        sku_by_id = {p["id"]: p.get("sku", "") for p in prods}
        for pid, row in agg.items():
            row["sku"] = sku_by_id.get(pid, "")
    top = sorted(agg.values(), key=lambda r: r["revenue"], reverse=True)[:5]

    return MonthlyReport(
        month=month,
        month_label=_month_label(month),
        revenue_total=revenue_total,
        barang_revenue=barang_revenue,
        jasa_revenue=jasa_revenue,
        cost_of_goods=cost_of_goods,
        gross_profit_barang=barang_revenue - cost_of_goods,
        service_fee_total=service_fee_total,
        expenses_total=expenses_total,
        expenses_by_category=[
            ExpenseByCategory(category=c, amount=a) for c, a in sorted(by_cat.items(), key=lambda kv: -kv[1])
        ],
        net_profit=total_profit - expenses_total,
        transaction_count=len(completed),
        returned_count=len(returned),
        returned_amount=sum(t.get("total_amount", 0) for t in returned),
        new_receivables=new_receivables,
        receivables_paid=receivables_paid,
        stock_in_total=stock_in_total,
        top_products=[TopProduct(**t) for t in top],
        available_months=await _available_months(),
    )


@router.get("/monthly", response_model=MonthlyReport)
async def monthly_report(month: Optional[str] = None):
    return await _build_report(month or today_iso()[:7])


@router.get("/monthly/csv")
async def monthly_report_csv(month: Optional[str] = None):
    r = await _build_report(month or today_iso()[:7])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Laporan Laba-Rugi Bengkel", r.month_label])
    w.writerow([])
    w.writerow(["Keterangan", "Jumlah (Rp)"])
    w.writerow(["Pendapatan Barang", round(r.barang_revenue)])
    w.writerow(["Pendapatan Jasa", round(r.jasa_revenue)])
    w.writerow(["TOTAL PENDAPATAN", round(r.revenue_total)])
    w.writerow(["Modal Barang Terjual (HPP)", round(r.cost_of_goods)])
    w.writerow(["LABA KOTOR (BARANG)", round(r.gross_profit_barang)])
    w.writerow(["Komisi Montir", round(r.service_fee_total)])
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
    w.writerow(["Piutang Sudah Lunas", round(r.receivables_paid)])
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
        Paragraph("Laporan Laba-Rugi — Bengkel Maju Jaya", h1),
        Paragraph(f"Periode: {r.month_label} &nbsp;•&nbsp; Ban &amp; Servis Otomotif", sub),
        Spacer(1, 6),
        Paragraph("Pendapatan &amp; Laba", h2),
        money_table(
            [
                ["Keterangan", "Jumlah"],
                ["Pendapatan Barang (ban, oli, sparepart)", _rupiah(r.barang_revenue)],
                ["Pendapatan Jasa Servis", _rupiah(r.jasa_revenue)],
                ["Total Pendapatan", _rupiah(r.revenue_total)],
                ["Modal Barang Terjual (HPP)", "-" + _rupiah(r.cost_of_goods)],
                ["Laba Kotor (Barang)", _rupiah(r.gross_profit_barang)],
                ["Komisi Montir (dari jasa)", "-" + _rupiah(r.service_fee_total)],
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
        money_table([["Keterangan", "Jumlah"], ["Laba Bersih (setelah komisi montir & pengeluaran)", _rupiah(r.net_profit)]], highlight_rows=(1,)),
        Paragraph("Ringkasan Aktivitas", h2),
        money_table(
            [
                ["Keterangan", "Nilai"],
                ["Jumlah Transaksi Selesai", str(r.transaction_count)],
                ["Transaksi Retur", f"{r.returned_count} ({_rupiah(r.returned_amount)})"],
                ["Piutang Baru (tempo)", _rupiah(r.new_receivables)],
                ["Piutang Sudah Lunas", _rupiah(r.receivables_paid)],
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
