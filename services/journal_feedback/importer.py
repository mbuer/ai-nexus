"""Bounded explicit imports via the existing administrator path; no automatic generation."""
import base64
from datetime import datetime
import json
import subprocess

from .contract import canonical, digest, hash_value, identifier, validate


def validate_batch(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ValueError('Expected 1-100 queued reviews')
    ids = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {'review', 'payload_sha256'}:
            raise ValueError('Unexpected queue export fields')
        validate(item['review'])
        if item['payload_sha256'] != digest(item['review']):
            raise ValueError('Queue export digest differs')
        feedback_id = item['review']['feedback_id']
        if feedback_id in ids:
            raise ValueError('Duplicate review in import batch')
        ids.add(feedback_id)
    return items


def sql(review):
    validate(review)
    encoded = base64.b64encode(canonical(review)).decode('ascii')
    # Only base64 ASCII enters the literal. Untrusted comments are never SQL syntax.
    return ("BEGIN;\nSET LOCAL ROLE journal_feedback_importer;\n"
            "SELECT public.import_journal_feedback(convert_from(decode('" + encoded + "', 'base64'), 'UTF8'));\nCOMMIT;\n")


def execute(statement):
    result = subprocess.run(['podman', 'exec', '-i', 'ai-nexus-postgres', 'psql',
                             '-U', 'postgres', '-d', 'birdynator', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'],
                            input=statement, text=True, encoding='utf-8', capture_output=True, timeout=60, check=True)
    lines = result.stdout.strip().splitlines()
    if len(lines) != 1:
        raise ValueError('Import output is ambiguous; inspect before retry or acknowledgment')
    return json.loads(lines[0])


def import_batch(items, runner=execute):
    validate_batch(items)  # All input checked before the first database operation.
    for item in items:
        receipt = runner(sql(item['review']))
        if not isinstance(receipt, dict) or set(receipt) != {'feedback_id', 'payload_sha256', 'status', 'imported_at'}:
            raise ValueError('Unexpected database import receipt')
        if receipt['feedback_id'] != item['review']['feedback_id'] or receipt['payload_sha256'] != item['payload_sha256']:
            raise ValueError('Database receipt differs from queued review')
        if receipt['status'] not in ('imported', 'already_imported'):
            raise ValueError('Database has not confirmed import')
        identifier(receipt['feedback_id'])
        hash_value(receipt['payload_sha256'])
        if not isinstance(receipt['imported_at'], str) or len(receipt['imported_at']) > 40:
            raise ValueError('Invalid import receipt time')
        if datetime.fromisoformat(receipt['imported_at'].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('Import receipt time needs a timezone')
        yield receipt
