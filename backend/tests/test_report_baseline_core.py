"""A baseline must match source history while retaining operational BSON data."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from tools.cloud_copy_core import document_fingerprint
from tools.report_baseline_core import build_report_baseline, documents, stable


def collection(rows):
    return {"documents": rows, "options": {}, "indexes": {"_id_": {"key": [("_id", 1)], "v": 2}}}


def source():
    return {"name": "source", "collections": {
        "products": collection([{"_id": ObjectId(), "id": "p", "name": "Tire", "sku": "sku", "stock": 7}]),
        "customers": collection([{"_id": "c", "id": "c", "name": "Customer"}]),
        "users": collection([{"_id": "user", "id": "user", "password_hash": "private", "extra": Decimal128("1.25")}]),
        "transactions": collection([{"_id": ObjectId(), "id": "native", "total_amount": 123, "date_key": "2026-09-30"}]),
        "transaction_details": collection([{"_id": "native-detail", "id": "nd", "transaction_id": "native", "custom": b"original"}]),
        "accounts_payable": collection([{"_id": "ap", "id": "ap", "remaining": 5, "version": 2,
                                         "payments": [{"id": "payment", "amount": 10, "payment_date": "2026-09-01"}]}]),
        "accounts_receivable": collection([{"_id": "ar", "id": "ar", "remaining": 5, "payments": []}]),
        "expenses": collection([{"_id": "expense", "id": "expense", "amount": 4}]),
    }}


def event(row=2, amount=100, qty=1):
    return {"sheet": "SELLING CASH", "row": row, "date": "2026-09-01", "kind": "cash_sale",
            "invoice": "invoice", "customer": "", "name": "Tire", "qty": qty, "price": 120,
            "amount": amount, "fee": 5, "cost": 50, "profit": 37, "category": "TIRE",
            "base_price": 120, "cash_subtotal": amount, "credit_surcharge": 0,
            "discount_amount": 120 * qty - amount, "owner": "bian", "tax": 1, "tax_source": "SELLING CASH.P"}


def raw():
    return {"source": "store_current", "digest": "new-digest", "filename": "new.xlsx",
            "events": [event()], "products": [], "purchases": [], "transfers": [], "source_rows": [],
            "checks": [{"month": "2026-09", "differences": {"pendapatan": 0}}]}


def test_baseline_does_not_modify_source_or_inventory_and_preserves_native_records():
    original, workbook = source(), raw()
    pristine = deepcopy(original)
    result, summary = build_report_baseline(original, workbook)
    assert original == pristine
    for name in ("products", "customers", "users"):
        assert document_fingerprint(documents(result, name)) == document_fingerprint(documents(original, name))
    assert documents(result, "transaction_details")[0] == documents(original, "transaction_details")[0]
    native = next(row for row in documents(result, "transactions") if row["id"] == "native")
    assert native["report_excluded"] is True
    assert {key: value for key, value in native.items() if not key.startswith("report_")} == documents(original, "transactions")[0]
    payable = documents(result, "accounts_payable")[0]
    assert payable["remaining"] == 5 and payable["version"] == 2
    assert payable["payments"][0]["report_excluded"] is True
    assert summary["excluded_native_transactions"] == summary["excluded_payments"] == 1
    assert documents(result, "transaction_details")[1]["spreadsheet_profit"] == 37
    assert documents(result, "transaction_details")[1]["subtotal"] == 100


def test_moved_source_lines_keep_identifiers_and_cached_overrides_without_row_matching():
    original, workbook = source(), raw()
    initial, _ = build_report_baseline(original, workbook)
    old_tx = next(row for row in documents(initial, "transactions") if row.get("import_source"))
    old_detail = next(row for row in documents(initial, "transaction_details") if row.get("import_source"))
    changed = deepcopy(workbook)
    changed["digest"] = "changed-tax-and-row"
    changed["events"][0].update(row=50, tax=0)
    rebuilt, _ = build_report_baseline(initial, changed)
    new_tx = next(row for row in documents(rebuilt, "transactions") if row.get("import_source"))
    new_detail = next(row for row in documents(rebuilt, "transaction_details") if row.get("import_source"))
    assert (new_tx["id"], new_tx["_id"]) == (old_tx["id"], old_tx["_id"])
    assert (new_detail["id"], new_detail["_id"]) == (old_detail["id"], old_detail["_id"])
    assert new_detail["source_row"] == 50 and new_detail["tax"] == 0
    assert new_detail["spreadsheet_profit"] == 37


def test_new_line_at_previous_position_never_steals_moved_line_id():
    initial, _ = build_report_baseline(source(), raw())
    old = next(row for row in documents(initial, "transaction_details") if row.get("import_source"))
    changed = raw()
    changed["digest"] = "new-and-moved"
    changed["events"] = [event(2, 90), event(3, 100)]
    result, _ = build_report_baseline(initial, changed)
    lines = [row for row in documents(result, "transaction_details") if row.get("import_source")]
    preserved = next(row for row in lines if row["subtotal"] == 100)
    new = next(row for row in lines if row["subtotal"] == 90)
    assert preserved["id"] == old["id"]
    assert new["id"] != old["id"]


@pytest.mark.parametrize("invalid", ["nonreconciling", "pending", "marker", "quantity", "wrongsource"])
def test_refuses_invalid_sources_before_any_mutation(invalid):
    original, workbook = source(), raw()
    if invalid == "nonreconciling": workbook["checks"][0]["differences"]["pendapatan"] = 10
    if invalid == "pending": original["collections"]["financial_operations"] = collection([{"_id": "pending"}])
    if invalid == "marker": documents(original, "products")[0]["_financial_operation"] = "pending"
    if invalid == "quantity": workbook["events"][0]["qty"] = -1
    if invalid == "wrongsource": workbook["source"] = "september"
    pristine = deepcopy(original)
    with pytest.raises(ValueError): build_report_baseline(original, workbook)
    assert original == pristine


def test_missing_or_ambiguous_products_are_historical_references_not_new_inventory():
    original, workbook = source(), raw()
    documents(original, "products").clear()
    result, _ = build_report_baseline(original, workbook)
    assert documents(result, "products") == []
    line = next(row for row in documents(result, "transaction_details") if row.get("import_source"))
    assert line["product_id"] == stable("store-history-unresolved", "Tire")


def test_zero_quantity_zero_amount_is_archived_without_an_invoice():
    original, workbook = source(), raw()
    workbook["events"][0].update(qty=0, amount=0, fee=0, profit=0)
    result, summary = build_report_baseline(original, workbook)
    assert summary["source_transactions"] == 0 and summary["skipped_zero_lines"] == 1
    assert len(documents(result, "excel_events")) == 1
    assert len(documents(result, "transactions")) == 1
