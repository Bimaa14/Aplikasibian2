"""Exact, append-only database copy for a stopped demo deployment.

The caller must stop application writers, hold the local source process guard,
and own the destination's permanent financial-writer lock. This module never
deletes documents, changes the source, or releases somebody else's lock.
"""

from copy import deepcopy
import hashlib
from pathlib import Path

from bson import json_util
from bson.json_util import CANONICAL_JSON_OPTIONS


EXCLUDED_COLLECTIONS = frozenset({
    "runtime_locks", "sessions", "login_attempts", "status_checks",
})
_DEMO_ID = "demo-admin"
_BATCH_SIZE = 500
_NONSTANDARD_OPTIONS = {"capped", "timeseries", "viewOn", "clusteredIndex", "encryptedFields"}


class CloudCopyError(RuntimeError):
    """An intentionally data-free error safe to display in a setup dialog."""


def _canonical(value):
    return json_util.dumps(
        value, json_options=CANONICAL_JSON_OPTIONS,
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )


def _sorted_documents(documents):
    # Hashing is independent of cursor order and preserves BSON value types.
    return sorted(documents, key=_canonical)


def document_fingerprint(documents):
    """Hash full BSON documents without returning or logging their contents."""
    return hashlib.sha256(_canonical(_sorted_documents(documents)).encode("utf-8")).hexdigest()


def take_snapshot(database):
    """Read documents, regular collection options, and complete index metadata.

    This is not snapshot isolation: the caller must stop writers and compare two
    source fingerprints before permitting the copy.
    """
    try:
        collections = {}
        for metadata in sorted(database.list_collections(), key=lambda item: item["name"]):
            options = deepcopy(metadata.get("options", {}))
            if (metadata.get("type", "collection") != "collection"
                    or metadata["name"].startswith("system.")
                    or any(key in options and (key != "capped" or options[key])
                           for key in _NONSTANDARD_OPTIONS)):
                raise CloudCopyError("Only ordinary, uncapped collections can be copied.")
            collection = database[metadata["name"]]
            collections[metadata["name"]] = {
                "documents": list(collection.find({}).sort("_id", 1)),
                "options": options,
                "indexes": deepcopy(collection.index_information()),
            }
        return {"name": database.name, "collections": collections}
    except CloudCopyError:
        raise
    except Exception:
        raise CloudCopyError("Could not read a complete database snapshot.") from None


def fingerprint(snapshot, exclude=EXCLUDED_COLLECTIONS):
    """Hash documents, counts, collection options, and index definitions."""
    payload = {"name": snapshot["name"], "collections": {}}
    for name, collection in sorted(snapshot["collections"].items()):
        if name not in exclude:
            documents = _sorted_documents(collection["documents"])
            payload["collections"][name] = {
                "count": len(documents), "documents": documents,
                "options": collection["options"], "indexes": collection["indexes"],
            }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def save_snapshot(snapshot, path):
    """Save a private backup as canonical Extended JSON, preserving BSON types."""
    try:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Existing backups are never overwritten.
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(json_util.dumps(
                snapshot, json_options=CANONICAL_JSON_OPTIONS,
                sort_keys=True, indent=2, ensure_ascii=False,
            ))
    except Exception:
        raise CloudCopyError("Could not save a new private snapshot backup.") from None


def _logical_index(spec):
    # Namespace/version describe server storage; background describes its build.
    return {key: value for key, value in spec.items()
            if key not in {"ns", "v", "name", "background"}}


def _validate_indexes(source, target):
    for name, spec in source.items():
        if name in target:
            if _logical_index(spec) != _logical_index(target[name]):
                raise CloudCopyError("An existing destination index conflicts with the source.")
        elif any(spec["key"] == other["key"] for other in target.values()):
            # MongoDB can reject an identical key/options pair under another name.
            raise CloudCopyError("A destination index uses a different name for source keys.")


def _documents(snapshot, name):
    return snapshot["collections"].get(name, {}).get("documents", [])


def _is_fixed_demo(document):
    return (document.get("_id") == _DEMO_ID and document.get("id") == _DEMO_ID
            and document.get("username") == _DEMO_ID and document.get("role") == "admin")


def preflight(source_snapshot, target_snapshot):
    """Refuse nonempty business targets, unfinished writes, and account conflicts."""
    if (_documents(source_snapshot, "financial_operations")
            or _documents(target_snapshot, "financial_operations")):
        raise CloudCopyError("Financial recovery must finish before a database copy.")

    target_users = _documents(target_snapshot, "users")
    if len(target_users) > 1 or any(not _is_fixed_demo(user) for user in target_users):
        raise CloudCopyError("Destination accounts are not limited to the reserved demo administrator.")
    for user in _documents(source_snapshot, "users"):
        if any(user.get(field) == _DEMO_ID for field in ("_id", "id", "username")):
            raise CloudCopyError("A source account conflicts with the reserved demo administrator.")

    for name, collection in target_snapshot["collections"].items():
        if name not in EXCLUDED_COLLECTIONS and name != "users" and collection["documents"]:
            raise CloudCopyError("Destination business collections must be empty before copying.")

    for name, source in source_snapshot["collections"].items():
        if name in EXCLUDED_COLLECTIONS:
            continue
        if any("_financial_operation" in document for document in source["documents"]):
            raise CloudCopyError("Unfinished financial document markers prevent a database copy.")
        target = target_snapshot["collections"].get(name)
        if target is not None:
            if source["options"] != target["options"]:
                raise CloudCopyError("Destination collection options conflict with the source.")
            _validate_indexes(source["indexes"], target["indexes"])


def _require_ownership(database, required_owner):
    if not isinstance(required_owner, str) or not required_owner:
        raise CloudCopyError("The destination writer lock must be owned by this copy operation.")
    try:
        owned = database["runtime_locks"].find_one({
            "_id": "financial-writer", "owner": required_owner,
        })
    except Exception:
        raise CloudCopyError("Could not confirm destination writer lock ownership.") from None
    if owned is None:
        raise CloudCopyError("The destination writer lock must be owned by this copy operation.")


def copy_snapshot(source_snapshot, target_database, *, required_owner):
    """Copy into a fresh target under the caller's existing permanent writer lock.

    A failure can leave an incomplete destination copy. It is intentionally never
    deleted or retried over existing business data; preserve the backups and have
    an operator review the destination before another attempt.
    """
    _require_ownership(target_database, required_owner)
    target_before = take_snapshot(target_database)
    preflight(source_snapshot, target_before)
    _require_ownership(target_database, required_owner)

    expected = {
        name: deepcopy(collection["documents"])
        for name, collection in source_snapshot["collections"].items()
        if name not in EXCLUDED_COLLECTIONS
    }
    demo_users = deepcopy(_documents(target_before, "users"))
    if demo_users:
        expected.setdefault("users", []).extend(demo_users)

    try:
        for name, source in sorted(source_snapshot["collections"].items()):
            if name in EXCLUDED_COLLECTIONS:
                continue
            _require_ownership(target_database, required_owner)
            if name not in target_before["collections"]:
                target_database.create_collection(name, **deepcopy(source["options"]))
            collection = target_database[name]
            existing_indexes = collection.index_information()
            _validate_indexes(source["indexes"], existing_indexes)
            for index_name, spec in source["indexes"].items():
                if index_name in existing_indexes:
                    continue
                _require_ownership(target_database, required_owner)
                options = {key: deepcopy(value) for key, value in spec.items()
                           if key not in {"key", "name", "ns"}}
                collection.create_index(spec["key"], name=index_name, **options)
            documents = source["documents"]
            for offset in range(0, len(documents), _BATCH_SIZE):
                _require_ownership(target_database, required_owner)
                collection.insert_many(deepcopy(documents[offset:offset + _BATCH_SIZE]), ordered=True)

        _require_ownership(target_database, required_owner)
        after = take_snapshot(target_database)
        counts, hashes = {}, {}
        for name, documents in expected.items():
            actual = _documents(after, name)
            expected_hash = document_fingerprint(documents)
            if len(actual) != len(documents) or document_fingerprint(actual) != expected_hash:
                raise CloudCopyError("Destination document verification failed; retain both backups.")
            if name in source_snapshot["collections"]:
                source = source_snapshot["collections"][name]
                target = after["collections"][name]
                if source["options"] != target["options"]:
                    raise CloudCopyError("Destination collection options failed verification.")
                _validate_indexes(source["indexes"], target["indexes"])
            counts[name], hashes[name] = len(actual), expected_hash
        _require_ownership(target_database, required_owner)
        return {"counts": counts, "hashes": hashes}
    except CloudCopyError:
        raise
    except Exception:
        raise CloudCopyError("Database copy failed; the destination may contain an incomplete copy.") from None
