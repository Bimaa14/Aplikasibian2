"""Prevent two local API processes from recovering/writing the same database."""

import hashlib
import os
import tempfile
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from pymongo.errors import DuplicateKeyError
from pymongo.write_concern import WriteConcern


@asynccontextmanager
async def cloud_single_writer(database):
    """Fail closed if another container can still write or recover this database.

    No timeout/TTL: a paused process must never lose ownership while it can still
    write. After a forced stop, an operator must verify it is stopped before
    clearing a stale lock. Graceful shutdown releases ownership automatically.
    """
    if os.environ.get("CLOUD_SINGLE_WRITER", "false").lower() != "true":
        yield
        return
    owner = uuid.uuid4().hex
    locks = database.runtime_locks.with_options(
        write_concern=WriteConcern(w="majority", j=True, wtimeout=10000),
    )
    try:
        await locks.insert_one({
            "_id": "financial-writer", "owner": owner,
            "started_at": datetime.now(timezone.utc),
        })
    except DuplicateKeyError as exc:
        raise RuntimeError(
            "Database demo masih dikunci server lain. Hentikan server sebelumnya; "
            "bersihkan runtime_locks hanya setelah memastikan proses lama sudah berhenti."
        ) from exc
    try:
        yield
    finally:
        await locks.delete_one({"_id": "financial-writer", "owner": owner})


@contextmanager
def single_writer(database_name):
    key = hashlib.sha256(database_name.encode()).hexdigest()[:24]
    path = Path(tempfile.gettempdir()) / f"bian-financial-{key}.lock"
    handle = path.open("a+b")
    try:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Database ini sudah dipakai proses backend lain. Jalankan satu backend dengan satu worker.") from exc
        yield
    finally:
        handle.close()  # OS also releases this lock after a crash.
