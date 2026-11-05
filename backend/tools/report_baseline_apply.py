"""Apply a reviewed report baseline while owning the stopped app's writer lock.

Backups are the caller's responsibility and must precede this function. Any
failure after writes begin deliberately leaves the caller's lock in place.
"""
from copy import deepcopy

from pymongo import ReplaceOne

from tools.cloud_copy_core import (
    CloudCopyError, EXCLUDED_COLLECTIONS, _canonical, _logical_index,
    _require_ownership, document_fingerprint, fingerprint, take_snapshot,
)
from tools.report_baseline_core import REBUILT, SOURCE_NAMES, documents

ALLOWED = REBUILT | {'accounts_receivable', 'accounts_payable', 'expenses'}
BATCH_SIZE = 500


def validate_cloud_source(snapshot):
    """Reject operational changes that rebuilding imported history would erase."""
    source_ids = set()
    for tx in documents(snapshot, 'transactions'):
        source = tx.get('import_source')
        if source and source not in SOURCE_NAMES:
            raise CloudCopyError('An additional imported transaction source needs review.')
        if source in SOURCE_NAMES:
            if tx.get('status') != 'completed' or tx.get('return_date') or tx.get('version'):
                raise CloudCopyError('Imported sale revisions or returns need review before replacing history.')
            source_ids.add(tx['id'])
    for name in ('accounts_receivable', 'accounts_payable'):
        if any(d.get('transaction_id') in source_ids for d in documents(snapshot, name)):
            raise CloudCopyError('An imported invoice has an operational debt link; review it first.')
    if documents(snapshot, 'stock_in'):
        raise CloudCopyError('Additional stock receipt records need review to match Get Data exactly.')
    for name in ('excel_events', 'purchase_history', 'transfer_history', 'spreadsheet_rows'):
        if any(row.get('import_source') not in SOURCE_NAMES for row in documents(snapshot, name)):
            raise CloudCopyError('Additional source history needs review before replacing the report baseline.')
    if any(row.get('source') not in SOURCE_NAMES for row in documents(snapshot, 'report_baselines')):
        raise CloudCopyError('Another report baseline must be preserved by a reviewed migration.')


def _schema(collection):
    return {'options': collection['options'], 'indexes': {
        key: _logical_index(value) for key, value in collection['indexes'].items()}}


def preflight_update(before, expected):
    if before['name'] != expected['name']:
        raise CloudCopyError('The reviewed source and destination database must be identical.')
    validate_cloud_source(before)
    before_names = set(before['collections']) - EXCLUDED_COLLECTIONS
    after_names = set(expected['collections']) - EXCLUDED_COLLECTIONS
    if after_names - before_names - {'report_baselines'} or before_names - after_names:
        raise CloudCopyError('The baseline cannot remove collections or add unrelated collections.')
    changed = []
    for name in sorted(after_names):
        candidate = expected['collections'][name]
        prior = before['collections'].get(name)
        if prior and _schema(prior) != _schema(candidate):
            raise CloudCopyError('The baseline cannot change collection options or indexes.')
        if document_fingerprint(documents(before, name)) != document_fingerprint(candidate['documents']):
            if name not in ALLOWED:
                raise CloudCopyError('The baseline cannot change unrelated operational data.')
            changed.append(name)
        ids = [_canonical(row['_id']) for row in candidate['documents']]
        if len(set(ids)) != len(ids):
            raise CloudCopyError('Duplicate document identities prevent the update.')
        for field in ('id', 'invoice_number') if name == 'transactions' else ('id',):
            if any(spec.get('unique') and spec.get('key') == [(field, 1)]
                   for spec in candidate['indexes'].values()):
                values = [_canonical(row.get(field)) for row in candidate['documents']]
                if len(set(values)) != len(values):
                    raise CloudCopyError('Duplicate business identities prevent the update.')
    return changed


def apply_reviewed_baseline(before, expected, database, *, required_owner):
    """Diff only reviewed records; preserve every unrelated document and schema."""
    _require_ownership(database, required_owner)
    if database.name != before['name']:
        raise CloudCopyError('The active destination differs from the reviewed database.')
    changed = preflight_update(before, expected)
    if fingerprint(take_snapshot(database)) != fingerprint(before):
        raise CloudCopyError('Online business data changed after review; check it again before updating.')
    _require_ownership(database, required_owner)
    try:
        for name in changed:
            _require_ownership(database, required_owner)
            prior = {_canonical(row['_id']): row for row in documents(before, name)}
            desired = {_canonical(row['_id']): row for row in documents(expected, name)}
            if name not in before['collections']:
                database.create_collection(name, **deepcopy(expected['collections'][name]['options']))
            collection = database[name]
            obsolete = [prior[key]['_id'] for key in prior.keys() - desired.keys()]
            for start in range(0, len(obsolete), BATCH_SIZE):
                _require_ownership(database, required_owner)
                group = obsolete[start:start + BATCH_SIZE]
                result = collection.delete_many({'_id': {'$in': group}})
                if result.deleted_count != len(group):
                    raise CloudCopyError('A reviewed history deletion did not match; retain backups and lock.')
            replacement = [row for key, row in desired.items()
                           if key not in prior or _canonical(prior[key]) != _canonical(row)]
            for start in range(0, len(replacement), BATCH_SIZE):
                _require_ownership(database, required_owner)
                collection.bulk_write([ReplaceOne({'_id': row['_id']}, deepcopy(row), upsert=True)
                                       for row in replacement[start:start + BATCH_SIZE]], ordered=True)
        _require_ownership(database, required_owner)
        actual = take_snapshot(database)
        if fingerprint(actual) != fingerprint(expected):
            raise CloudCopyError('Full database verification failed; retain backups and lock.')
        _require_ownership(database, required_owner)
        return {'changed_collections': changed, 'verified_hash': fingerprint(actual),
                'counts': {name: len(collection['documents'])
                           for name, collection in actual['collections'].items()
                           if name not in EXCLUDED_COLLECTIONS}}
    except CloudCopyError:
        raise
    except Exception:
        raise CloudCopyError('Baseline update failed; retain backups and the owned lock for review.') from None
