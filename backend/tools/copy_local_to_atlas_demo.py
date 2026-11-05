"""Private desktop helper for copying this local app into its Atlas demo database.

Atlas credentials stay in memory. The tool never alters the source database or
the application's .env. Backups and progress are stored only in ignored .cache.
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError
from pymongo.write_concern import WriteConcern

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from lib.runtime_lock import single_writer
from tools.cloud_copy_core import (
    copy_snapshot,
    fingerprint,
    preflight,
    save_snapshot,
    take_snapshot,
)

ATLAS_HOST = "cluster0.rcfqwmu.mongodb.net"
ATLAS_USER = "bian_demo_service"
TARGET_NAME = "bian_client_demo"
EXPECTED_SOURCE = "bian_store_candidate_20260929_222923_cada18"


def source_settings():
    settings = dotenv_values(ROOT / "backend" / ".env")
    uri, name = settings.get("MONGO_URL"), settings.get("DB_NAME")
    if not uri or name != EXPECTED_SOURCE:
        raise ValueError("Database lokal berubah. Minta Codex memeriksa sumbernya dahulu.")
    if urlsplit(uri).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Sumber harus database lokal yang sudah diperiksa.")
    return uri, name


def atlas_uri(password):
    if not password:
        raise ValueError("Isi password database Atlas dahulu.")
    return (
        f"mongodb+srv://{ATLAS_USER}:{quote_plus(password)}@{ATLAS_HOST}/"
        "?retryWrites=true&w=majority&authSource=admin&appName=BianCloudCopy"
    )


def make_client(uri):
    return MongoClient(uri, serverSelectionTimeoutMS=15000, connectTimeoutMS=15000)


def private_directory(path):
    path = path.resolve()
    allowed = (ROOT / ".cache" / "cloud-copy").resolve()
    if not path.is_relative_to(allowed) or path == allowed:
        raise ValueError("Folder backup harus di .cache/cloud-copy dengan subfolder khusus.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_status(folder, phase, **metadata):
    report = {
        "phase": phase,
        "time": datetime.now(timezone.utc).isoformat(),
        "source_database": EXPECTED_SOURCE,
        "target_database": TARGET_NAME,
        **metadata,
    }
    temporary = folder / "status.tmp"
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temporary.replace(folder / "status.json")


def safe_error(error):
    if isinstance(error, DuplicateKeyError):
        return "Database online masih dikunci. Hentikan deployment Railway, lalu coba lagi."
    if isinstance(error, OperationFailure) and error.code == 8000:
        return "Atlas menolak password. Gunakan password database user bian_demo_service."
    if isinstance(error, PyMongoError):
        return f"Koneksi/database gagal ({type(error).__name__}). Codex dapat memeriksa statusnya."
    # These exceptions come from our guard/core, which never include documents or credentials.
    if isinstance(error, (ValueError, RuntimeError)):
        return str(error)
    return f"Proses berhenti ({type(error).__name__}). Codex dapat memeriksa statusnya."


def prepare_source(folder):
    uri, name = source_settings()
    with make_client(uri) as client, single_writer(name):
        snapshot = take_snapshot(client[name])
        digest = fingerprint(snapshot)
        if digest != fingerprint(take_snapshot(client[name])):
            raise ValueError("Data lokal berubah ketika dibaca. Tutup aplikasi lokal dahulu.")
        save_snapshot(snapshot, folder / "source-before.ejson")
        counts = {key: len(value["documents"]) for key, value in snapshot["collections"].items()}
        write_status(folder, "source_backed_up", source_counts=counts, source_hash=digest)
        return snapshot


def run_window(folder):
    import tkinter as tk
    from tkinter import ttk

    messages = queue.Queue()
    root = tk.Tk()
    root.title("Bian - salin data lokal ke demo online")
    root.geometry("710x560")
    root.minsize(650, 510)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Salin data aplikasi ke Atlas", font=("Segoe UI", 17, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        text=("Sumber: database aplikasi lokal yang sudah diperiksa\n"
              "Tujuan: bian_client_demo di Cluster0\n"
              "Data lokal tetap utuh. Akun demo-admin online tetap disimpan."),
        wraplength=650, justify="left",
    ).pack(anchor="w", pady=(12, 18))

    ttk.Label(frame, text="Password database Atlas untuk bian_demo_service:").pack(anchor="w")
    password = ttk.Entry(frame, show="*", width=70)
    password.pack(fill="x", pady=(6, 8))
    ttk.Label(frame, text="Password hanya dipakai di memori; tidak masuk chat, backup, atau log.",
              wraplength=650).pack(anchor="w")

    notice = tk.StringVar(value="1. Isi password Atlas, lalu klik Cek koneksi Atlas.")
    ttk.Label(frame, textvariable=notice, wraplength=650, justify="left").pack(anchor="w", pady=18)

    controls = ttk.Frame(frame)
    controls.pack(fill="x", pady=(0, 14))
    check_button = ttk.Button(controls, text="Cek koneksi Atlas")
    check_button.pack(side="left")
    copy_button = ttk.Button(controls, text="Salin semua data", state="disabled")
    copy_button.pack(side="left", padx=12)

    output = tk.Text(frame, height=8, wrap="word", font=("Segoe UI", 10), state="disabled")
    output.pack(fill="both", expand=True)
    busy = False
    connection_checked = False

    def add_line(text):
        output.configure(state="normal")
        output.insert("end", text + "\n")
        output.see("end")
        output.configure(state="disabled")

    def event(kind, **metadata):
        messages.put((kind, metadata))

    def check_worker(secret):
        try:
            source_uri, source_name = source_settings()
            with make_client(source_uri) as local, single_writer(source_name), make_client(atlas_uri(secret)) as cloud:
                cloud[TARGET_NAME].command("ping")
                source = take_snapshot(local[source_name])
                target = take_snapshot(cloud[TARGET_NAME])
                preflight(source, target)
                locked = cloud[TARGET_NAME].runtime_locks.find_one({"_id": "financial-writer"}, {"_id": 1}) is not None
            write_status(folder, "atlas_checked", cloud_locked=locked)
            event("checked", cloud_locked=locked)
        except Exception as error:
            message = safe_error(error)
            write_status(folder, "connection_refused", error_type=type(error).__name__, message=message)
            event("error", message=message, retained_lock=False)

    def copy_worker(secret):
        owner = "cloud-copy-" + uuid.uuid4().hex
        acquired = False
        writes_started = False
        verified = False
        insert_attempted = False
        cloud = None
        try:
            source_uri, source_name = source_settings()
            cloud = make_client(atlas_uri(secret))
            target = cloud[TARGET_NAME]
            target.command("ping")
            locks = target.runtime_locks.with_options(write_concern=WriteConcern(w="majority", j=True, wtimeout=10000))
            # Never remove another process's lock. A stopped Railway process releases its own lock.
            insert_attempted = True
            locks.insert_one({"_id": "financial-writer", "owner": owner,
                              "started_at": datetime.now(timezone.utc), "purpose": "local-data-copy"})
            acquired = True
            write_status(folder, "copy_locked", transfer_owner=owner)
            event("progress", text="Kunci transfer sudah diperoleh; aplikasi online tetap berhenti.")
            with make_client(source_uri) as local, single_writer(source_name):
                source = take_snapshot(local[source_name])
                source_hash = fingerprint(source)
                if source_hash != fingerprint(take_snapshot(local[source_name])):
                    raise ValueError("Data lokal berubah ketika dibaca. Tutup aplikasi lokal dahulu.")
                target_before = take_snapshot(target)
                preflight(source, target_before)
                save_snapshot(source, folder / "source-at-copy.ejson")
                save_snapshot(target_before, folder / "atlas-before.ejson")
                write_status(folder, "copying", transfer_owner=owner, source_hash=source_hash)
                event("progress", text="Backup sumber dan tujuan tersimpan. Menyalin dan memeriksa semua koleksi...")
                writes_started = True
                result = copy_snapshot(source, target, required_owner=owner)
                if source_hash != fingerprint(take_snapshot(local[source_name])):
                    raise RuntimeError("Data sumber berubah saat transfer. Web tetap dihentikan untuk pemeriksaan.")
                verified = True
                write_status(folder, "verified", transfer_owner=owner, source_hash=source_hash, **result)
                event("progress", text="Jumlah dokumen dan hash seluruh data sesuai dengan sumber.")
            released = locks.delete_one({"_id": "financial-writer", "owner": owner})
            if released.deleted_count != 1:
                raise RuntimeError("Data telah sesuai, tetapi pelepasan kunci perlu diperiksa dahulu.")
            acquired = False
            write_status(folder, "complete", source_hash=source_hash, **result)
            event("complete", counts=result["counts"])
        except Exception as error:
            # If any copy writes may have happened, keep the owned cloud lock to prevent the
            # app booting against an incomplete copy. The backups allow deliberate recovery.
            retained_lock = acquired or (insert_attempted and not isinstance(error, DuplicateKeyError))
            if acquired and not writes_started and cloud is not None:
                try:
                    deleted = cloud[TARGET_NAME].runtime_locks.with_options(
                        write_concern=WriteConcern(w="majority", j=True, wtimeout=10000)
                    ).delete_one({"_id": "financial-writer", "owner": owner})
                    retained_lock = deleted.deleted_count != 1
                except PyMongoError:
                    retained_lock = True
            message = safe_error(error)
            phase = "verified_lock_check" if verified else ("copy_failed_held" if retained_lock else "copy_refused")
            write_status(folder, phase, error_type=type(error).__name__, message=message,
                         transfer_owner=owner if retained_lock else None, retained_lock=retained_lock)
            event("error", message=message, retained_lock=retained_lock)
        finally:
            if cloud is not None:
                cloud.close()

    def start(action):
        nonlocal busy, connection_checked
        if busy:
            return
        secret = password.get()
        if not secret:
            notice.set("Isi password database Atlas terlebih dahulu.")
            return
        busy = True
        check_button.configure(state="disabled")
        copy_button.configure(state="disabled")
        password.configure(state="disabled")
        notice.set("Memeriksa koneksi..." if action == "check" else "Menyalin data. Biarkan jendela ini tetap terbuka.")
        threading.Thread(target=check_worker if action == "check" else copy_worker, args=(secret,), daemon=False).start()

    def poll():
        nonlocal busy, connection_checked
        try:
            while True:
                kind, data = messages.get_nowait()
                if kind == "progress":
                    add_line(data["text"])
                elif kind == "checked":
                    busy = False
                    connection_checked = True
                    password.configure(state="normal")
                    check_button.configure(state="normal")
                    copy_button.configure(state="normal")
                    notice.set("Koneksi benar. Hentikan deployment Railway dahulu, lalu klik Salin semua data.")
                    add_line("Atlas siap. " + ("Web masih memegang kunci database." if data["cloud_locked"] else "Kunci database sudah bebas."))
                elif kind == "complete":
                    busy = False
                    password.configure(state="normal")
                    password.delete(0, "end")
                    password.configure(state="disabled")
                    notice.set("Selesai! Seluruh data sudah diverifikasi. Jalankan kembali deployment Railway.")
                    add_line("Produk: %s | Transaksi: %s | Pelanggan: %s" % (
                        data["counts"].get("products", 0), data["counts"].get("transactions", 0), data["counts"].get("customers", 0)))
                elif kind == "error":
                    busy = False
                    notice.set(data["message"])
                    add_line(data["message"])
                    password.configure(state="normal")
                    if data["retained_lock"]:
                        password.delete(0, "end")
                        password.configure(state="disabled")
                        add_line("Transfer berhenti dan kunci dipertahankan. Kabari Codex sebelum menjalankan web kembali.")
                    else:
                        check_button.configure(state="normal")
                        copy_button.configure(state="normal" if connection_checked else "disabled")
        except queue.Empty:
            pass
        root.after(200, poll)

    def close():
        if busy:
            notice.set("Tunggu proses selesai sebelum menutup jendela ini.")
        else:
            root.destroy()

    check_button.configure(command=lambda: start("check"))
    copy_button.configure(command=lambda: start("copy"))
    root.protocol("WM_DELETE_WINDOW", close)
    root.after_idle(lambda: write_status(folder, "waiting_for_atlas_password",
                                         source_backup_ready=(folder / "source-before.ejson").is_file()))
    root.after(200, poll)
    password.focus_set()
    root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--prepare-source", action="store_true")
    args = parser.parse_args()
    folder = private_directory(Path(args.folder))
    if args.prepare_source:
        prepare_source(folder)
        print(json.dumps({"phase": "source_backed_up", "status_file": str(folder / "status.json")}))
    else:
        run_window(folder)


if __name__ == "__main__":
    main()
