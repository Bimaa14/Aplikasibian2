"""Isolated copy checks: these fakes never contact the application's database."""

from copy import deepcopy
from datetime import datetime, timezone

from bson import Binary, Decimal128, Int64, ObjectId, Timestamp, json_util
import pytest

from tools.cloud_copy_core import (
    CloudCopyError, EXCLUDED_COLLECTIONS, copy_snapshot, document_fingerprint,
    fingerprint, preflight, save_snapshot, take_snapshot,
)


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda document: json_util.dumps(document[key])))


class Collection:
    def __init__(self, database, name):
        self.database, self.name = database, name

    def find(self, query):
        return Cursor(deepcopy(self.database.documents.get(self.name, [])))

    def find_one(self, query):
        for document in self.database.documents.get(self.name, []):
            if all(document.get(key) == value for key, value in query.items()):
                return deepcopy(document)
        return None

    def index_information(self):
        return deepcopy(self.database.indexes.get(self.name, {}))

    def create_index(self, keys, *, name, **options):
        self.database.writes.append(("index", self.name, name))
        self.database.indexes[self.name][name] = {"v": 2, "key": list(keys), **deepcopy(options)}
        return name

    def insert_many(self, documents, *, ordered):
        assert ordered is True
        self.database.writes.append(("insert", self.name, len(documents)))
        if self.database.corrupt_inserts:
            documents = deepcopy(documents)
            documents[0]["copy_corruption"] = True
        self.database.documents[self.name].extend(deepcopy(documents))


class Database:
    def __init__(self, name, documents=None, *, options=None, indexes=None, types=None):
        self.name = name
        self.documents = deepcopy(documents or {})
        self.options = deepcopy(options or {})
        self.indexes = {
            name: {"_id_": {"v": 2, "key": [("_id", 1)]}}
            for name in self.documents
        }
        for collection, specs in (indexes or {}).items():
            self.indexes.setdefault(collection, {}).update(deepcopy(specs))
        self.types = types or {}
        self.writes = []
        self.corrupt_inserts = False

    def __getitem__(self, name):
        return Collection(self, name)

    def list_collections(self):
        return [{"name": name, "type": self.types.get(name, "collection"),
                 "options": deepcopy(self.options.get(name, {}))}
                for name in self.documents]

    def create_collection(self, name, **options):
        assert name not in self.documents
        self.writes.append(("collection", name))
        self.documents[name] = []
        self.options[name] = deepcopy(options)
        self.indexes[name] = {"_id_": {"v": 2, "key": [("_id", 1)]}}
        return self[name]


def demo_account():
    return {"_id": "demo-admin", "id": "demo-admin", "username": "demo-admin",
            "name": "Demo Admin", "role": "admin", "password_hash": "destination-only-hash"}


def destination():
    return Database("demo", {
        "users": [demo_account()],
        "runtime_locks": [{"_id": "financial-writer", "owner": "copy-owner"}],
        "sessions": [{"_id": ObjectId(), "token": "destination-session"}],
        "financial_operations": [],
    })


def test_full_bson_copy_retains_ids_indexes_demo_account_and_excluded_collections():
    bson_document = {
        "_id": ObjectId(), "id": "business-id", "date": datetime(2026, 10, 4, tzinfo=timezone.utc),
        "large": Int64(2**53 + 1), "amount": Decimal128("123.40"),
        "binary": Binary(b"private-bytes", subtype=128), "clock": Timestamp(1700000000, 7),
        "nested": {"unicode": "piutang", "values": [None, True, 3.5]},
    }
    source = Database("local", {
        "products": [bson_document],
        "users": [{"_id": ObjectId(), "id": "local-admin", "username": "local-admin",
                   "role": "admin", "password_hash": "source-account-hash"}],
        "checkout_requests": [{"_id": ObjectId(), "id": "request-id", "transaction_id": "sale-id"}],
        "financial_operations": [],
        "sessions": [{"_id": ObjectId(), "token": "source-session"}],
        "login_attempts": [{"_id": ObjectId(), "username": "local-admin"}],
        "status_checks": [{"_id": ObjectId(), "timestamp": "local"}],
        "runtime_locks": [{"_id": "financial-writer", "owner": "unrelated-source-owner"}],
    }, options={"products": {"validationLevel": "moderate", "validator": {"id": {"$type": "string"}}}},
        indexes={"products": {"id_unique": {"v": 2, "key": [("id", 1)], "unique": True}}})
    target = destination()
    source_before = take_snapshot(source)
    excluded_before = {name: deepcopy(target.documents.get(name)) for name in EXCLUDED_COLLECTIONS}

    result = copy_snapshot(source_before, target, required_owner="copy-owner")

    assert result["counts"] == {"products": 1, "users": 2, "checkout_requests": 1, "financial_operations": 0}
    assert result["hashes"]["products"] == document_fingerprint([bson_document])
    assert target.documents["products"][0] == bson_document
    assert target.documents["users"][0] == demo_account()
    assert target.documents["users"][1] == source_before["collections"]["users"]["documents"][0]
    assert target.options["products"] == source.options["products"]
    assert target.indexes["products"]["id_unique"] == source.indexes["products"]["id_unique"]
    assert {name: target.documents.get(name) for name in EXCLUDED_COLLECTIONS} == excluded_before
    assert take_snapshot(source) == source_before
    assert source.writes == []


def test_document_hash_preserves_bson_types_and_ignores_document_and_field_order():
    first = [{"_id": "a", "count": Int64(1)}, {"_id": "b", "price": Decimal128("1.00")}]
    reordered = [{"price": Decimal128("1.00"), "_id": "b"}, {"count": Int64(1), "_id": "a"}]
    assert document_fingerprint(first) == document_fingerprint(reordered)
    changed_type = deepcopy(first)
    changed_type[0]["count"] = 1
    assert document_fingerprint(first) != document_fingerprint(changed_type)


def test_full_snapshot_fingerprint_includes_options_indexes_and_omits_runtime_noise():
    snapshot = take_snapshot(destination())
    changed = deepcopy(snapshot)
    changed["collections"]["sessions"]["documents"] = []
    changed["collections"]["runtime_locks"]["documents"][0]["owner"] = "new-owner"
    assert fingerprint(snapshot) == fingerprint(changed)
    assert fingerprint(snapshot, exclude=()) != fingerprint(changed, exclude=())
    changed["collections"]["users"]["options"]["validationLevel"] = "moderate"
    assert fingerprint(snapshot) != fingerprint(changed)
    changed = deepcopy(snapshot)
    changed["collections"]["users"]["indexes"]["username_unique"] = {"key": [("username", 1)], "unique": True}
    assert fingerprint(snapshot) != fingerprint(changed)


def test_private_backup_round_trips_bson_and_never_overwrites(tmp_path):
    source = Database("local", {"products": [{"_id": ObjectId(), "value": Decimal128("1.00")}]})
    snapshot = take_snapshot(source)
    path = tmp_path / "private" / "source.bson.json"
    save_snapshot(snapshot, path)
    restored = json_util.loads(path.read_text(encoding="utf-8"))
    assert fingerprint(restored) == fingerprint(snapshot)
    old_content = path.read_bytes()
    with pytest.raises(CloudCopyError, match="new private snapshot"):
        save_snapshot(snapshot, path)
    assert path.read_bytes() == old_content


@pytest.mark.parametrize("which", ["source", "target"])
def test_pending_journal_refuses_before_any_destination_write(which):
    source, target = Database("local", {"financial_operations": []}), destination()
    (source if which == "source" else target).documents["financial_operations"] = [{"_id": ObjectId(), "committed": False}]
    with pytest.raises(CloudCopyError, match="recovery must finish"):
        copy_snapshot(take_snapshot(source), target, required_owner="copy-owner")
    assert source.writes == target.writes == []


@pytest.mark.parametrize("field", ["_id", "id", "username"])
def test_source_demo_identity_conflict_refuses_without_overwriting(field):
    user = {"_id": ObjectId(), "id": "local-user", "username": "local-user"}
    user[field] = "demo-admin"
    target = destination()
    before = take_snapshot(target)
    with pytest.raises(CloudCopyError, match="source account conflicts"):
        copy_snapshot(take_snapshot(Database("local", {"users": [user]})), target, required_owner="copy-owner")
    assert take_snapshot(target) == before
    assert target.writes == []


def test_existing_business_data_refuses_even_in_unknown_collection():
    target = destination()
    target.documents["additional_business_ledger"] = [{"_id": ObjectId(), "amount": 1}]
    source = Database("local", {"products": [{"_id": ObjectId()}]})
    with pytest.raises(CloudCopyError, match="business collections must be empty"):
        copy_snapshot(take_snapshot(source), target, required_owner="copy-owner")
    assert target.writes == []


def test_other_destination_account_refuses_even_when_business_data_empty():
    target = destination()
    target.documents["users"].append({"_id": ObjectId(), "username": "another-user"})
    with pytest.raises(CloudCopyError, match="reserved demo administrator"):
        preflight(take_snapshot(Database("local")), take_snapshot(target))
    assert target.writes == []


@pytest.mark.parametrize("owner", [None, "", "wrong-owner"])
def test_wrong_or_missing_owner_refuses_before_destination_mutations(owner):
    target = destination()
    with pytest.raises(CloudCopyError, match="writer lock must be owned"):
        copy_snapshot(take_snapshot(Database("local", {"products": [{"_id": ObjectId()}]})), target, required_owner=owner)
    assert target.writes == []
    assert target.documents["runtime_locks"][0]["owner"] == "copy-owner"


@pytest.mark.parametrize("metadata_type,options", [
    ("view", {"viewOn": "products"}), ("collection", {"capped": True, "size": 4096}),
    ("collection", {"timeseries": {"timeField": "at"}}),
    ("collection", {"timeseries": {}}),
    ("collection", {"clusteredIndex": {"key": {"_id": 1}, "unique": True}}),
])
def test_nonstandard_collections_refuse(metadata_type, options):
    source = Database("local", {"special": []}, options={"special": options}, types={"special": metadata_type})
    with pytest.raises(CloudCopyError, match="ordinary, uncapped"):
        take_snapshot(source)
    assert source.writes == []


@pytest.mark.parametrize("conflict", ["options", "index", "index_name"])
def test_all_schema_conflicts_are_preflighted_before_copying_any_collection(conflict):
    source = Database("local", {"a_first": [{"_id": ObjectId()}], "z_last": []},
                      indexes={"z_last": {"id_unique": {"key": [("id", 1)], "unique": True}}})
    target = destination()
    target.create_collection("z_last")
    if conflict == "options":
        target.options["z_last"] = {"validationLevel": "moderate"}
    elif conflict == "index":
        target.indexes["z_last"]["id_unique"] = {"key": [("id", 1)], "unique": False}
    else:
        target.indexes["z_last"]["other_name"] = {"key": [("id", 1)], "unique": True}
    target.writes.clear()
    with pytest.raises(CloudCopyError, match="conflict|different name"):
        copy_snapshot(take_snapshot(source), target, required_owner="copy-owner")
    assert target.writes == []
    assert "a_first" not in target.documents


def test_copy_uses_bounded_batches_and_preserves_existing_matching_indexes():
    source = Database("local", {"products": [{"_id": ObjectId(), "id": str(i)} for i in range(1001)]},
                      indexes={"products": {"id_unique": {"v": 2, "key": [("id", 1)], "unique": True}}})
    target = destination()
    target.create_collection("products")
    target.indexes["products"]["id_unique"] = deepcopy(source.indexes["products"]["id_unique"])
    target.writes.clear()
    result = copy_snapshot(take_snapshot(source), target, required_owner="copy-owner")
    assert result["counts"]["products"] == 1001
    assert [item[2] for item in target.writes if item[:2] == ("insert", "products")] == [500, 500, 1]
    assert not any(item[0] == "index" for item in target.writes)


def test_document_verification_detects_copy_corruption():
    source = Database("local", {"products": [{"_id": ObjectId(), "price": 100}]})
    target = destination()
    target.corrupt_inserts = True
    with pytest.raises(CloudCopyError, match="document verification failed"):
        copy_snapshot(take_snapshot(source), target, required_owner="copy-owner")
    assert source.writes == []
    assert target.documents["users"] == [demo_account()]


def test_lost_ownership_stops_before_the_next_write():
    source = Database("local", {"products": [{"_id": ObjectId()}]})
    target = destination()
    original_create = target.create_collection

    def create_and_lose_ownership(name, **options):
        collection = original_create(name, **options)
        target.documents["runtime_locks"][0]["owner"] = "other-owner"
        return collection

    target.create_collection = create_and_lose_ownership
    with pytest.raises(CloudCopyError, match="writer lock must be owned"):
        copy_snapshot(take_snapshot(source), target, required_owner="copy-owner")
    assert target.documents["products"] == []
    assert not any(item[0] == "insert" for item in target.writes)


def test_database_errors_never_expose_credentials_or_document_values():
    source = Database("local", {"products": [{"_id": ObjectId()}]})
    target = destination()

    def fail_create(*args, **kwargs):
        raise RuntimeError("mongodb://secret-user:secret-password@host private-customer-name")

    target.create_collection = fail_create
    with pytest.raises(CloudCopyError) as error:
        copy_snapshot(take_snapshot(source), target, required_owner="copy-owner")
    assert "secret" not in str(error.value)
    assert "customer" not in str(error.value)
    assert error.value.__suppress_context__ is True
