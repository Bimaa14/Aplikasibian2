"""Prepare a separate local report candidate; never activate or alter the source."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.write_concern import WriteConcern
from lib.runtime_lock import single_writer
from lib.workbooks import dataset
from tools.cloud_copy_core import copy_snapshot, fingerprint, save_snapshot, take_snapshot
from tools.report_baseline_core import build_report_baseline


def prepare(workbook_path, folder):
    workbook_path = Path(workbook_path).resolve(strict=True)
    folder = Path(folder).resolve()
    allowed = (ROOT / ".cache" / "report-baseline").resolve()
    if not folder.is_relative_to(allowed) or folder == allowed:
        raise ValueError("Candidate backups must stay inside .cache/report-baseline.")
    if folder.exists():
        raise ValueError("Use a new backup folder; existing backups are never overwritten.")
    settings = dotenv_values(ROOT / "backend" / ".env")
    uri, source_name = settings["MONGO_URL"], settings["DB_NAME"]
    if urlsplit(uri).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("The preparation source must be the local application.")
    raw = dataset("store_current", workbook_path)
    name = "bian_report_candidate_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    owner = "report-candidate-" + uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    with MongoClient(uri, serverSelectionTimeoutMS=15000) as client, single_writer(source_name), single_writer(name):
        source = client[source_name]
        before = take_snapshot(source)
        before_hash = fingerprint(before)
        if before_hash != fingerprint(take_snapshot(source)):
            raise ValueError("Local business data changed during preparation.")
        candidate, summary = build_report_baseline(before, raw)
        candidate["name"] = name
        save_snapshot(before, folder / "local-before.ejson")
        save_snapshot(candidate, folder / "candidate-expected.ejson")
        target = client.get_database(name, write_concern=WriteConcern(w="majority", j=True))
        if target.list_collection_names():
            raise ValueError("The generated candidate already exists.")
        locks = target.runtime_locks
        locks.insert_one({"_id": "financial-writer", "owner": owner, "started_at": datetime.now(timezone.utc)})
        # A failed copy deliberately retains its lock and private backups. No
        # cleanup can accidentally target the active application database.
        result = copy_snapshot(candidate, target, required_owner=owner)
        if fingerprint(take_snapshot(source)) != before_hash:
            raise ValueError("Source changed; this candidate must not be activated.")
        actual = take_snapshot(target)
        if fingerprint(candidate) != fingerprint(actual):
            raise ValueError("Candidate schema/document verification failed.")
        if hashlib.sha256(workbook_path.read_bytes()).hexdigest() != raw["digest"]:
            raise ValueError("The workbook changed during preparation.")
        if locks.delete_one({"_id": "financial-writer", "owner": owner}).deleted_count != 1:
            raise ValueError("Candidate ownership needs review before activation.")
        manifest = {"source_database": source_name, "candidate_database": name,
                    "source_hash": before_hash, "candidate_hash": fingerprint(candidate),
                    "workbook": str(workbook_path), "activated": False,
                    "summary": summary, "copy": result}
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        return {"candidate_database": name, "activated": False, "summary": summary,
                "manifest": str(folder / "manifest.json"), "source_unchanged": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--folder", required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.workbook, args.folder), indent=2, default=str))
