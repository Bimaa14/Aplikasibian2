"""Activate a verified candidate while the local backend is stopped.

Preserves the previous database and .env backup. Refuses activation if source
business data or the supplied spreadsheet changed after preparation.
"""
import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import set_key
from lib.db import db, client
from lib.runtime_lock import single_writer
from tools.prepare_store_candidate import snapshot, fingerprint, ROOT


async def activate(plan_path):
    plan_path = Path(plan_path).resolve()
    if not plan_path.is_relative_to(ROOT / 'test_reports' / 'spreadsheet'):
        raise ValueError('Plan must belong to this workspace')
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    target_name = plan['candidate_database']
    if not target_name.startswith('bian_store_candidate_') or plan['source_database'] != db.name:
        raise ValueError('Source/target does not match the reviewed migration plan')
    validation = json.loads((ROOT / 'test_reports/spreadsheet/candidate-validation.json').read_text(encoding='utf-8'))
    if validation['database'] != target_name or validation['products_matched'] != plan['products'] or not all(c['matches'] for c in validation['monthly_checks']):
        raise ValueError('Candidate has not passed reconciliation')
    workbook = ROOT / 'refrensi-spreadsheet/Perkasa Jaya - Store information system (1).xlsx'
    if hashlib.sha256(workbook.read_bytes()).hexdigest() != plan['digest']:
        raise ValueError('Source file changed; prepare again')
    with single_writer(db.name), single_writer(target_name):
        current = await snapshot(db)
        if fingerprint(current) != plan['source_fingerprint']:
            raise ValueError('Business data changed; prepare a fresh candidate before switching')
        if await client[target_name].products.count_documents({'import_source':'store_current'}) != plan['products']:
            raise ValueError('Candidate product count changed')
        # Preserve existing browser sessions for the unchanged user IDs, without printing tokens.
        sessions = current.get('sessions', [])
        if sessions and not await client[target_name].sessions.count_documents({}):
            await client[target_name].sessions.insert_many(sessions)
        env = ROOT / 'backend/.env'
        backup = ROOT / 'backend/.env.pre-store-migration'
        if not backup.exists():
            backup.write_bytes(env.read_bytes())
        set_key(str(env), 'DB_NAME', target_name)
        plan['activated'] = True
        plan['activated_at'] = datetime.now(timezone.utc).isoformat()
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Activated verified Store database. Original database and backup preserved.')
    client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('plan')
    asyncio.run(activate(parser.parse_args().plan))
