"""Real Mongo migration checks, confined to each test's owned local database.

These tests never read application credentials or use DB_NAME. Every write and
cleanup targets the random database created by the fixture below.
"""
from copy import deepcopy
from datetime import datetime, timezone
import uuid

from bson import Binary, Decimal128, Int64, ObjectId
import pytest
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.write_concern import WriteConcern

from tools import report_baseline_apply as migration
from tools.cloud_copy_core import CloudCopyError, fingerprint, take_snapshot
from tools.report_baseline_core import build_report_baseline, stable


OWNER = "test-report-baseline-owner"
PREFIX = "bian_report_apply_test_"


@pytest.fixture
def owned_database():
    name = PREFIX + uuid.uuid4().hex
    # A literal loopback URI prevents production configuration from being used.
    client = MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    database = client.get_database(name, write_concern=WriteConcern(w="majority", j=True))
    assert database.name == name and name.startswith(PREFIX)
    try:
        for collection in (
            "products", "users", "customers", "suppliers", "transactions",
            "transaction_details", "accounts_receivable", "accounts_payable",
            "expenses", "excel_events", "purchase_history", "transfer_history",
            "spreadsheet_rows", "import_batches", "financial_operations", "stock_in",
            "checkout_requests", "sessions", "runtime_locks",
        ):
            options = ({"validationLevel": "moderate", "validator": {"id": {"$type": "string"}}}
                       if collection == "products" else {})
            database.create_collection(collection, **options)
            if collection not in ("sessions", "runtime_locks", "financial_operations", "stock_in"):
                database[collection].create_index("id", name="id_unique", unique=True)
        database.transactions.create_index("invoice_number", name="invoice_unique", unique=True)
        database.products.insert_one({
            "_id": ObjectId(), "id": "product", "name": "Tire", "sku": "unchanged-sku",
            "active": True, "stock": Int64(7), "cost_price": Decimal128("50.25"),
            "private_metadata": Binary(b"preserved-bson", subtype=128),
        })
        database.users.insert_one({"_id": ObjectId(), "id": "user", "username": "demo-admin",
                                   "role": "admin", "password_hash": "fixture-only-dummy-hash"})
        database.customers.insert_one({"_id": ObjectId(), "id": "customer", "name": "Customer"})
        database.suppliers.insert_one({"_id": ObjectId(), "id": "supplier", "name": "Supplier"})
        source_id = stable("store-history", "2026-09-01", "prior-invoice", "", "cash_sale")
        database.transactions.insert_many([
            {"_id": ObjectId(), "id": source_id, "invoice_number": "XL-prior", "status": "completed",
             "date_key": "2026-09-01", "import_source": "store_current", "total_amount": 100},
            {"_id": ObjectId(), "id": "native", "invoice_number": "native", "status": "completed",
             "date_key": "2026-09-30", "total_amount": 123, "version": 4,
             "date": datetime(2026, 9, 30, tzinfo=timezone.utc), "cashier_note": "keep"},
        ])
        database.transaction_details.insert_many([
            {"_id": ObjectId(), "id": "prior-line", "transaction_id": source_id,
             "product_name": "Tire", "qty": 1, "subtotal": 100, "cost_price": 50,
             "price": 100, "base_price": 100, "cash_subtotal": 100,
             "spreadsheet_fee": 0, "spreadsheet_profit": 50, "category": "TIRE",
             "source_row": 2, "import_source": "store_current"},
            {"_id": ObjectId(), "id": "native-line", "transaction_id": "native",
             "product_id": "product", "subtotal": 123, "custom": Binary(b"keep-detail")},
        ])
        for collection in ("accounts_receivable", "accounts_payable"):
            database[collection].insert_one({
                "_id": ObjectId(), "id": collection, "transaction_id": "native",
                "remaining": Decimal128("125.25"), "status": "partial", "version": 8,
                "payments": [{"id": "prior-payment", "amount": 25, "payment_date": "2026-09-30"}],
            })
        database.expenses.insert_one({"_id": ObjectId(), "id": "native-expense", "amount": 9,
                                      "date": "2026-09-30", "category": "Operasional"})
        for collection, sheet in (("excel_events", "SELLING CASH"), ("purchase_history", "PURCHASE"),
                                  ("transfer_history", "TRANSFER"), ("spreadsheet_rows", "DATABASE")):
            database[collection].insert_one({"_id": ObjectId(), "id": "obsolete-" + collection,
                                             "import_source": "store_current", "sheet": sheet,
                                             "row": 999, "amount": 99})
        database.import_batches.insert_many([
            {"_id": ObjectId(), "id": "old-history", "source": "store_current", "group": "history"},
            {"_id": ObjectId(), "id": "master-import", "source": "store_current", "group": "products",
             "digest": "old-master", "count": 1},
        ])
        database.checkout_requests.insert_one({"_id": ObjectId(), "id": "request", "transaction_id": "native"})
        database.sessions.insert_one({"_id": ObjectId(), "fixture_session": True})
        database.runtime_locks.insert_one({"_id": "financial-writer", "owner": OWNER})
        yield database
    finally:
        # Only this fixture's generated, loopback database is eligible for deletion.
        assert database.name == name and name.startswith(PREFIX)
        client.drop_database(name)
        client.close()


def checked_workbook():
    sale = {
        "sheet": "SELLING CASH", "row": 2, "date": "2026-09-01", "kind": "cash_sale",
        "invoice": "new-invoice", "customer": "Customer", "name": "Tire", "qty": 2,
        "price": 120, "amount": 200, "fee": 5, "cost": 50, "profit": 93,
        "category": "TIRE", "base_price": 120, "cash_subtotal": 200,
        "credit_surcharge": 0, "discount_amount": 40, "owner": "bian", "tax": 1,
        "tax_source": "SELLING CASH.P",
    }
    return {
        "source": "store_current", "digest": "fixture-checked-workbook", "filename": "fixture.xlsx",
        "events": [sale, {"sheet": "EXPENSES", "row": 2, "date": "2026-09-01",
                          "kind": "expense", "amount": 8, "category": "Operasional"}],
        "products": [],
        "purchases": [{"sheet": "PURCHASE", "row": 2, "date": "2026-09-01", "amount": 90}],
        "transfers": [{"sheet": "TRANSFER", "row": 2, "date": "2026-09-01", "amount": 40}],
        "source_rows": [{"sheet": "DATABASE", "row": 2, "original_value": "archived"}],
        "checks": [{"month": "2026-09", "differences": {"pendapatan": 0}}],
    }


def reviewed(database):
    before = take_snapshot(database)
    expected, _ = build_report_baseline(before, checked_workbook())
    return before, expected


def assert_owned(database):
    assert database.runtime_locks.find_one({"_id": "financial-writer"})["owner"] == OWNER


def test_applies_reviewed_diff_preserving_operational_bson_accounts_and_schema(owned_database):
    database = owned_database
    before, expected = reviewed(database)

    result = migration.apply_reviewed_baseline(before, expected, database, required_owner=OWNER)

    actual = take_snapshot(database)
    assert result["verified_hash"] == fingerprint(expected) == fingerprint(actual)
    for name in ("products", "users", "customers", "suppliers", "checkout_requests", "sessions"):
        assert actual["collections"][name] == before["collections"][name]
    for name, prior in before["collections"].items():
        assert actual["collections"][name]["options"] == prior["options"]
        assert actual["collections"][name]["indexes"] == prior["indexes"]
    native_before = next(t for t in before["collections"]["transactions"]["documents"] if t["id"] == "native")
    native_after = database.transactions.find_one({"id": "native"})
    assert {k: v for k, v in native_after.items() if not k.startswith("report_")} == native_before
    assert native_after["report_excluded"] is True
    assert database.transaction_details.find_one({"id": "native-line"}) == next(
        d for d in before["collections"]["transaction_details"]["documents"] if d["id"] == "native-line")
    for name in ("accounts_receivable", "accounts_payable"):
        debt = database[name].find_one({})
        prior = before["collections"][name]["documents"][0]
        assert {k: v for k, v in debt.items() if k != "payments"} == {k: v for k, v in prior.items() if k != "payments"}
        assert debt["payments"][0]["report_excluded"] is True
    assert database.excel_events.find_one({"id": "obsolete-excel_events"}) is None
    assert database.import_batches.find_one({"id": "master-import"}) == next(
        d for d in before["collections"]["import_batches"]["documents"] if d["id"] == "master-import")
    assert database.report_baselines.find_one({"_id": "store_current"}) is not None
    # Even success leaves release to the caller after its own final checks.
    assert_owned(database)


def test_changed_live_snapshot_is_refused_without_migration_writes(owned_database):
    database = owned_database
    before, expected = reviewed(database)
    database.products.update_one({"id": "product"}, {"$inc": {"stock": 1}})
    current = take_snapshot(database)

    with pytest.raises(CloudCopyError, match="changed after review"):
        migration.apply_reviewed_baseline(before, expected, database, required_owner=OWNER)

    assert fingerprint(take_snapshot(database), exclude=()) == fingerprint(current, exclude=())
    assert_owned(database)


@pytest.mark.parametrize("wrong_owner", [None, "", "another-owner"])
def test_wrong_owner_is_refused_before_any_database_change(owned_database, wrong_owner):
    database = owned_database
    before, expected = reviewed(database)

    with pytest.raises(CloudCopyError, match="writer lock must be owned"):
        migration.apply_reviewed_baseline(before, expected, database, required_owner=wrong_owner)

    assert fingerprint(take_snapshot(database), exclude=()) == fingerprint(before, exclude=())
    assert_owned(database)


@pytest.mark.parametrize("tampering", ["inventory", "users", "schema", "duplicate-business-id"])
def test_unreviewable_expected_changes_are_refused_before_writes(owned_database, tampering):
    database = owned_database
    before, expected = reviewed(database)
    if tampering == "inventory":
        expected["collections"]["products"]["documents"][0]["stock"] = 0
        message = "unrelated operational data"
    elif tampering == "users":
        expected["collections"]["users"]["documents"][0]["role"] = "kasir"
        message = "unrelated operational data"
    elif tampering == "schema":
        expected["collections"]["excel_events"]["indexes"]["added"] = {"key": [("amount", 1)]}
        message = "collection options or indexes"
    else:
        duplicate = deepcopy(expected["collections"]["transactions"]["documents"][0])
        duplicate["_id"] = ObjectId()
        expected["collections"]["transactions"]["documents"].append(duplicate)
        message = "Duplicate business identities"

    with pytest.raises(CloudCopyError, match=message):
        migration.apply_reviewed_baseline(before, expected, database, required_owner=OWNER)

    assert fingerprint(take_snapshot(database), exclude=()) == fingerprint(before, exclude=())
    assert_owned(database)


@pytest.mark.parametrize("condition", ["return-date", "returned-status", "version", "ar-link", "ap-link"])
def test_imported_revisions_and_operational_debt_links_are_refused_before_writes(owned_database, condition):
    database = owned_database
    imported = database.transactions.find_one({"import_source": "store_current"})
    if condition == "return-date":
        database.transactions.update_one({"_id": imported["_id"]}, {"$set": {"return_date": "2026-10-01"}})
    elif condition == "returned-status":
        database.transactions.update_one({"_id": imported["_id"]}, {"$set": {"status": "returned"}})
    elif condition == "version":
        database.transactions.update_one({"_id": imported["_id"]}, {"$set": {"version": 1}})
    else:
        collection = "accounts_receivable" if condition == "ar-link" else "accounts_payable"
        database[collection].update_one({}, {"$set": {"transaction_id": imported["id"]}})
    before, expected = reviewed(database)
    message = "sale revisions or returns" if condition in ("return-date", "returned-status", "version") else "operational debt link"

    with pytest.raises(CloudCopyError, match=message):
        migration.apply_reviewed_baseline(before, expected, database, required_owner=OWNER)

    assert fingerprint(take_snapshot(database), exclude=()) == fingerprint(before, exclude=())
    assert_owned(database)


def test_lost_write_acknowledgement_leaves_owned_lock_and_reports_failure(owned_database, monkeypatch):
    database = owned_database
    before, expected = reviewed(database)
    original = Collection.bulk_write
    injected = False

    def fail_after_ack(collection, requests, *args, **kwargs):
        nonlocal injected
        result = original(collection, requests, *args, **kwargs)
        if collection.database.name == database.name and not injected:
            injected = True
            raise RuntimeError("simulated lost acknowledgement")
        return result

    monkeypatch.setattr(Collection, "bulk_write", fail_after_ack)
    with pytest.raises(CloudCopyError, match="retain backups and the owned lock"):
        migration.apply_reviewed_baseline(before, expected, database, required_owner=OWNER)

    assert injected and fingerprint(take_snapshot(database)) != fingerprint(before)
    assert_owned(database)


def test_full_verification_failure_leaves_owned_lock_for_review(owned_database, monkeypatch):
    database = owned_database
    before, expected = reviewed(database)
    original = migration.take_snapshot
    snapshot_calls = 0

    def corrupt_before_final_snapshot(target):
        nonlocal snapshot_calls
        snapshot_calls += 1
        if snapshot_calls == 2:
            # Simulate an uncooperative writer; only this test-owned DB changes.
            assert target.name == database.name and target.name.startswith(PREFIX)
            target.products.update_one({"id": "product"}, {"$inc": {"stock": 10}})
        return original(target)

    monkeypatch.setattr(migration, "take_snapshot", corrupt_before_final_snapshot)
    with pytest.raises(CloudCopyError, match="Full database verification failed"):
        migration.apply_reviewed_baseline(before, expected, database, required_owner=OWNER)

    assert snapshot_calls == 2
    assert fingerprint(take_snapshot(database)) != fingerprint(expected)
    assert_owned(database)
