"""Build a reviewed report baseline in memory, preserving operational data.

The original snapshot is immutable. Replaced source history and report exclusions
are written only to a separate candidate by the caller, never to a running app.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import uuid

from tools.cloud_copy_core import document_fingerprint

SOURCE_NAMES = frozenset({"store", "store_current"})
REBUILT = frozenset({"transactions", "transaction_details", "excel_events",
                     "purchase_history", "transfer_history", "spreadsheet_rows",
                     "import_batches", "report_baselines"})


def stable(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "|".join(map(str, parts))))


def documents(snapshot, name):
    return snapshot["collections"].get(name, {}).get("documents", [])


def put_documents(snapshot, name, rows):
    collection = snapshot["collections"].setdefault(name, {
        "documents": [], "options": {},
        "indexes": {"_id_": {"v": 2, "key": [("_id", 1)]}},
    })
    collection["documents"] = rows


def sale_key(line):
    """Financial identity independent of moving rows and corrected TAX metadata."""
    return tuple(line.get(key) for key in (
        "product_name", "qty", "price", "base_price", "subtotal", "cost_price",
        "spreadsheet_fee", "spreadsheet_profit", "category", "cash_subtotal",
    ))


def rebuild_history(snapshot, raw):
    old_txs = [t for t in documents(snapshot, "transactions")
               if t.get("import_source") in SOURCE_NAMES]
    old_ids = {t["id"] for t in old_txs}
    old_by_id = {t["id"]: t for t in old_txs}
    old_lines = defaultdict(list)
    for line in documents(snapshot, "transaction_details"):
        if line.get("transaction_id") in old_ids:
            old_lines[(line["transaction_id"], sale_key(line))].append(line)
    reserved_line_ids = {line["id"] for rows in old_lines.values() for line in rows}
    for lines in old_lines.values():
        lines.sort(key=lambda line: (line.get("source_row", 0), line["id"]))

    # Keep the current inventory and its IDs. Historic source lines retain cached
    # amounts even when the master has since changed or a product is ambiguous.
    products = defaultdict(list)
    for product in documents(snapshot, "products"):
        products[product["name"].strip().casefold()].append(product)
    parties = {p["name"].strip().casefold(): p["id"]
               for p in documents(snapshot, "customers")}
    grouped = defaultdict(list)
    skipped = 0
    for event in raw["events"]:
        if event["kind"] not in ("cash_sale", "credit_sale"):
            continue
        if event["qty"] == 0 and event["amount"] == 0:
            skipped += 1
            continue
        if event["qty"] <= 0 or int(event["qty"]) != event["qty"] or event["amount"] < 0:
            raise ValueError("Workbook contains an invalid historical sale.")
        grouped[(event["date"], event["invoice"], event.get("customer", ""), event["kind"])].append(event)

    transactions, details = [], []
    used_line_ids = set()
    for key, entries in grouped.items():
        txid = stable("store-history", *key)
        lines = []
        for event in entries:
            matches = products.get(event["name"].strip().casefold(), [])
            active = [p for p in matches if p.get("active") is not False]
            selected = active[0] if len(active) == 1 else matches[0] if len(matches) == 1 else None
            line = {
                "transaction_id": txid,
                "product_id": selected["id"] if selected else stable("store-history-unresolved", event["name"]),
                "product_name": event["name"],
                "product_type": "jasa" if event["category"] in ("SERVICE", "COMPLEMENTARY") else "barang",
                "product_size": event.get("product_size", ""), "product_brand": event.get("product_brand", ""),
                "product_sku": selected.get("sku") if selected else None,
                "qty": int(event["qty"]), "price": event["price"], "base_price": event["base_price"],
                "cash_subtotal": event["cash_subtotal"], "credit_surcharge": event["credit_surcharge"],
                "discount_amount": event["discount_amount"], "subtotal": event["amount"],
                "cost_price": event["cost"], "service_fee": event["fee"] / event["qty"],
                "spreadsheet_cost": event["cost"],
                "spreadsheet_cost_total": event["cost"] if event["category"] == "SERVICE" else event["cost"] * event["qty"],
                "spreadsheet_fee": event["fee"], "spreadsheet_profit": event["profit"],
                "category": event["category"], "owner": event.get("owner"), "tax": event.get("tax"),
                "tax_source": event.get("tax_source"), "source_row": event["row"], "source_sheet": event["sheet"],
                "source_digest": raw["digest"], "import_source": "store_current",
            }
            prior = old_lines.get((txid, sale_key(line)), [])
            if prior:
                original = prior.pop(0)
                line["id"] = original["id"]
                line["_id"] = original.get("_id", original["id"])
            else:
                line["id"] = stable(txid, event["sheet"], event["row"])
                if line["id"] in reserved_line_ids:
                    line["id"] = stable("report-baseline-line", raw["digest"], txid, event["sheet"], event["row"])
                line["_id"] = line["id"]
            if line["id"] in used_line_ids:
                raise ValueError("Duplicate historical line identity.")
            used_line_ids.add(line["id"])
            lines.append(line)
        prior_tx = old_by_id.get(txid, {})
        tx = {
            "_id": prior_tx.get("_id", txid), "id": txid,
            "invoice_number": "XL-" + key[0].replace("-", "") + "-" + txid[:8], "source_invoice": key[1],
            "date": datetime.fromisoformat(key[0]).replace(tzinfo=timezone.utc), "date_key": key[0],
            "customer_id": parties.get(key[2].strip().casefold()), "customer_name": key[2] or None,
            "payment_method": "credit" if key[3] == "credit_sale" else "cash",
            "source_payment_unallocated": key[3] == "cash_sale", "status": "completed",
            "total_amount": sum(line["subtotal"] for line in lines),
            "discount_total": sum(line["discount_amount"] for line in lines),
            "barang_amount": sum(line["subtotal"] for line in lines if line["product_type"] == "barang"),
            "jasa_amount": sum(line["subtotal"] for line in lines if line["product_type"] == "jasa"),
            "total_cost": sum(line["spreadsheet_cost_total"] for line in lines),
            "service_fee": sum(line["spreadsheet_fee"] for line in lines),
            "total_profit": sum(line["spreadsheet_profit"] for line in lines),
            "spreadsheet_profit": sum(line["spreadsheet_profit"] for line in lines),
            "due_date": entries[0].get("due_date"), "import_source": "store_current",
            "source_row": entries[0]["row"], "source_sheet": entries[0]["sheet"], "source_digest": raw["digest"],
        }
        transactions.append(tx)
        details.extend(lines)
    return transactions, details, old_ids, skipped


def build_report_baseline(original, raw):
    if raw.get("source") != "store_current" or not raw.get("checks"):
        raise ValueError("A checked Store workbook is required.")
    if any(abs(value) > 0.005 for check in raw["checks"] for value in check["differences"].values()):
        raise ValueError("Workbook REPORT totals do not reconcile to source history.")
    if documents(original, "financial_operations") or any(
            "_financial_operation" in row for collection in original["collections"].values()
            for row in collection["documents"]):
        raise ValueError("Pending financial work prevents a baseline update.")
    candidate = deepcopy(original)
    source_txs, source_details, old_ids, skipped = rebuild_history(original, raw)
    native = [row for row in documents(candidate, "transactions") if row.get("import_source") not in SOURCE_NAMES]
    for row in native:
        row.update(report_excluded=True, report_excluded_reason="sheet_baseline", report_baseline_digest=raw["digest"])
    put_documents(candidate, "transactions", native + source_txs)
    native_details = [row for row in documents(candidate, "transaction_details") if row.get("transaction_id") not in old_ids]
    put_documents(candidate, "transaction_details", native_details + source_details)
    for source_key, collection_name in (("events", "excel_events"), ("purchases", "purchase_history"),
                                        ("transfers", "transfer_history"), ("source_rows", "spreadsheet_rows")):
        prior = documents(candidate, collection_name)
        old_by_id = {row["id"]: row for row in prior if row.get("import_source") in SOURCE_NAMES}
        kept = [row for row in prior if row.get("import_source") not in SOURCE_NAMES]
        for row in raw[source_key]:
            identity = stable("store-source", source_key, row["sheet"], row["row"])
            kept.append({**deepcopy(row), "_id": old_by_id.get(identity, {}).get("_id", identity),
                         "id": identity, "import_source": "store_current", "source_digest": raw["digest"]})
        put_documents(candidate, collection_name, kept)
    excluded_payments = 0
    for name in ("accounts_receivable", "accounts_payable"):
        for debt in documents(candidate, name):
            for payment in debt.get("payments", []):
                payment.update(report_excluded=True, report_baseline_digest=raw["digest"])
                excluded_payments += 1
    excluded_expenses = 0
    for expense in documents(candidate, "expenses"):
        if not expense.get("import_source"):
            expense.update(report_excluded=True, report_baseline_digest=raw["digest"])
            excluded_expenses += 1
    counts = {"history": len(source_txs), "purchases": len(raw["purchases"]),
              "transfers": len(raw["transfers"]), "source_rows": len(raw["source_rows"])}
    batches = [row for row in documents(candidate, "import_batches")
               if row.get("source") not in SOURCE_NAMES or row.get("group") not in counts]
    for group, count in counts.items():
        identity = stable(raw["digest"], group)
        batches.append({"_id": identity, "id": identity, "source": "store_current", "group": group,
                        "status": "completed", "count": count, "digest": raw["digest"]})
    put_documents(candidate, "import_batches", batches)
    baseline = {"_id": "store_current", "source": "store_current", "digest": raw["digest"],
                "filename": raw["filename"], "scope": "reports", "excluded_native_transactions": len(native),
                "excluded_payments": excluded_payments, "excluded_expenses": excluded_expenses,
                "source_transactions": len(source_txs), "source_lines": len(source_details),
                "skipped_zero_lines": skipped,
                "checks": deepcopy(raw["checks"])}
    put_documents(candidate, "report_baselines", [baseline])
    changed = sorted(name for name in candidate["collections"] if document_fingerprint(documents(original, name))
                     != document_fingerprint(documents(candidate, name)))
    if any(name not in REBUILT | {"accounts_receivable", "accounts_payable", "expenses"} for name in changed):
        raise ValueError("A report baseline changed an unrelated collection.")
    for name, collection in candidate["collections"].items():
        rows = collection["documents"]
        if len({str(row["_id"]) for row in rows}) != len(rows):
            raise ValueError("Duplicate document identities in candidate.")
        if any(spec.get("unique") and spec.get("key") == [("id", 1)] for spec in collection["indexes"].values()):
            if len({row.get("id") for row in rows}) != len(rows):
                raise ValueError("Duplicate business identities in candidate.")
    return candidate, {**baseline, "changed_collections": changed,
                       "preserved_inventory_hash": document_fingerprint(documents(candidate, "products"))}
