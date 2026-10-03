"""Recoverable multi-document writes for the local, single-worker Mongo deployment.

Undo instructions are persisted BEFORE each write. Document ownership makes undo
idempotent, including when a write succeeded but its acknowledgement was lost.
This is not Mongo snapshot isolation: API reads and cooperating financial writers
use financial_lock. Direct DB clients must not write while the app runs. Run one worker.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from lib.db import db

logger = logging.getLogger(__name__)
MARKER = "_financial_operation"


async def _finish(record):
    """Undo an uncommitted operation, or release markers for a committed one."""
    committed = record.get("committed", False)
    actions = record["actions"] if committed else reversed(record["actions"])
    for action in actions:
        collection = db[action["collection"]]
        owned = {"id": action["id"], MARKER: record["_id"]}
        if committed:
            await collection.update_one(owned, {"$unset": {MARKER: ""}})
        elif action["kind"] == "insert":
            await collection.delete_one(owned)
        else:
            update = {"$unset": {MARKER: "", **action["unset"]}}
            if action["set"]:
                update["$set"] = action["set"]
            if action["inc"]:
                update["$inc"] = action["inc"]
            await collection.update_one(owned, update)
    await db.financial_operations.delete_one({"_id": record["_id"]})


async def recover_financial_operations():
    """Call before serving requests; fail startup if recovery cannot finish."""
    async for record in db.financial_operations.find({}).sort("created_at", 1):
        logger.warning("Recovering financial operation %s (%s)", record["_id"], record["kind"])
        await _finish(record)


class RecoveringFinancialLock:
    def __init__(self):
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        await self.lock.acquire()
        try:
            await recover_financial_operations()
        except BaseException:
            self.lock.release()
            raise

    async def __aexit__(self, *args):
        self.lock.release()


financial_lock = RecoveringFinancialLock()


class FinancialOperation:
    def __init__(self, kind):
        self.record = {
            "_id": uuid.uuid4().hex, "kind": kind,
            "created_at": datetime.now(timezone.utc), "committed": False, "actions": [],
        }

    async def __aenter__(self):
        await db.financial_operations.insert_one(self.record.copy())
        return self

    async def _record(self, action):
        await db.financial_operations.update_one(
            {"_id": self.record["_id"]}, {"$push": {"actions": action}},
        )
        self.record["actions"].append(action)

    async def insert(self, collection_name, doc):
        await self._record({"kind": "insert", "collection": collection_name, "id": doc["id"]})
        await db[collection_name].insert_one({**doc, MARKER: self.record["_id"]})

    async def update(self, collection_name, document_id, update, *, condition=None):
        if set(update) - {"$set", "$inc"}:
            raise ValueError("Only $set and $inc are supported")
        collection = db[collection_name]
        before = await collection.find_one({"id": document_id})
        if not before or MARKER in before:
            raise HTTPException(409, "Data berubah atau sedang dipulihkan. Muat ulang dan coba lagi.")
        set_values = update.get("$set", {})
        increments = update.get("$inc", {})
        if set(set_values) & set(increments) or MARKER in set_values or MARKER in increments:
            raise ValueError("Conflicting update fields")
        action = {
            "kind": "update", "collection": collection_name, "id": document_id,
            "set": {k: before[k] for k in set_values if k in before},
            "unset": {k: "" for k in (*set_values, *increments) if k not in before},
            "inc": {k: -v for k, v in increments.items() if k in before},
        }
        await self._record(action)
        query = {**(condition or {}), "id": document_id, MARKER: {"$exists": False}}
        change = {**update, "$set": {**set_values, MARKER: self.record["_id"]}}
        result = await collection.update_one(query, change)
        if result.matched_count != 1:
            raise HTTPException(409, "Stok atau data berubah. Muat ulang dan coba lagi.")

    async def __aexit__(self, exc_type, exc, traceback):
        if exc_type is None:
            # If acknowledgement is lost, leave the journal for recovery to decide.
            await db.financial_operations.update_one(
                {"_id": self.record["_id"]}, {"$set": {"committed": True}},
            )
            self.record["committed"] = True
        try:
            await _finish(self.record)
        except Exception:
            logger.exception("Financial operation needs recovery: %s", self.record["_id"])
            if exc_type is None and self.record["committed"]:
                # Business writes are committed; don't report a false checkout failure.
                return False
            raise HTTPException(503, "Penyimpanan terputus. Data akan dipulihkan sebelum transaksi berikutnya.") from exc
        return False
