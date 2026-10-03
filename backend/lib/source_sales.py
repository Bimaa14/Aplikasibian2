"""Read-time corrections of imported sale metadata from the exact source row."""
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from lib.workbooks import dataset


@lru_cache(maxsize=1)
def reference_sale_rows():
    source = dataset('store_current')
    return {'digest': source['digest'], 'rows': {
        (event['sheet'], event['row']): event for event in source['events']
        if event['kind'] in ('cash_sale', 'credit_sale')
    }}


def _same_number(left, right):
    try:
        a, b = Decimal(str(left)), Decimal(str(right))
        return a.is_finite() and b.is_finite() and a == b
    except (InvalidOperation, ValueError):
        return False


def matched_source_sale(record, reference):
    """Never apply a row number to a different sale or a different known file."""
    if record.get('import_source') != 'store_current':
        return None
    digest = record.get('source_digest')
    if digest and digest != reference['digest']:
        return None
    key = (record.get('source_sheet') or record.get('sheet'),
           record.get('source_row') or record.get('row'))
    original = reference['rows'].get(key)
    if not original or record.get('kind') != original.get('kind'):
        return None
    if record.get('date') != original.get('date') or record.get('name') != original.get('name'):
        return None
    if not all(_same_number(record.get(key), original.get(key)) for key in ('qty', 'amount')):
        return None
    return original


def overlay_sale_detail(transaction, detail, reference):
    """Use CASH.P and CREDIT.O only after the original sale is identified."""
    if transaction.get('import_source') != 'store_current':
        return detail
    if detail.get('import_source') not in (None, 'store_current'):
        return detail
    if detail.get('source_digest') and detail['source_digest'] != reference['digest']:
        return detail
    record = {**detail, 'import_source': transaction['import_source'],
              'source_digest': transaction.get('source_digest') or detail.get('source_digest'),
              'date': transaction.get('date_key'), 'amount': detail.get('subtotal'),
              'name': detail.get('product_name'),
              'kind': 'credit_sale' if transaction.get('payment_method') == 'credit' else 'cash_sale'}
    original = matched_source_sale(record, reference)
    if original is None:
        return detail
    result = dict(detail)
    if original['kind'] == 'cash_sale':
        result.update(tax=original.get('tax'), tax_source=original.get('tax_source'))
    if original.get('cash_subtotal') is not None:
        result['cash_subtotal'] = original['cash_subtotal']
    return result


def overlay_sale_event(event, reference):
    original = matched_source_sale(event, reference)
    if original is None:
        return event
    result = dict(event)
    if original['kind'] == 'cash_sale':
        result.update(tax=original.get('tax'), tax_source=original.get('tax_source'))
    if original.get('cash_subtotal') is not None:
        result['cash_subtotal'] = original['cash_subtotal']
    return result
