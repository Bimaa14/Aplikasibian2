"""Prevent two local API processes from recovering/writing the same database."""

import hashlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


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
