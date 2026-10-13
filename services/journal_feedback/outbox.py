"""Durable Utility outbox. An acknowledgment never deletes the original review."""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from .contract import canonical, digest, hash_value, identifier, parse


class Queue:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError('Unexpected queue symlink')
        if not self.path.parent.is_dir():
            raise ValueError('Queue directory must be privately provisioned first')
        with self.connect() as connection:
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            has_tables = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()
            if version not in (0, 1) or (version == 0 and has_tables):
                raise ValueError('Unrecognized outbox schema; preserve it for migration review')
            connection.execute('CREATE TABLE IF NOT EXISTS reviews ('
                'sequence INTEGER PRIMARY KEY, feedback_id TEXT NOT NULL UNIQUE, reviewer_id TEXT NOT NULL, '
                'analysis_id INTEGER NOT NULL, supersedes TEXT UNIQUE REFERENCES reviews(feedback_id), payload_sha256 TEXT NOT NULL, '
                'payload BLOB NOT NULL, received_at TEXT NOT NULL, acknowledged_at TEXT, receipt TEXT)')
            connection.execute('CREATE INDEX IF NOT EXISTS reviews_pending ON reviews(acknowledged_at, sequence)')
            connection.execute('CREATE INDEX IF NOT EXISTS reviews_reader_report ON reviews(reviewer_id, analysis_id, sequence)')
            connection.execute('PRAGMA user_version = 1')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        self.path.chmod(0o600)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA busy_timeout = 15000')
        connection.execute('PRAGMA synchronous = FULL')
        connection.execute('PRAGMA foreign_keys = ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, raw, authenticated_reviewer):
        identifier(authenticated_reviewer)
        review = parse(raw)
        if review['reviewer_id'] != authenticated_reviewer:
            raise ValueError('Review identity differs from authenticated reader')
        payload, checksum = canonical(review), digest(review)
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            existing = connection.execute('SELECT * FROM reviews WHERE feedback_id = ?', (review['feedback_id'],)).fetchone()
            if existing:
                if existing['payload_sha256'] != checksum:
                    raise ValueError('Review UUID collision with different content')
                return {'feedback_id': review['feedback_id'], 'payload_sha256': checksum,
                        'status': 'imported' if existing['acknowledged_at'] else 'saved_on_utility'}
            if review['supersedes']:
                prior = connection.execute('SELECT payload FROM reviews WHERE feedback_id = ?', (review['supersedes'],)).fetchone()
                if not prior:
                    raise ValueError('Previous review must be saved before its revision')
                predecessor = parse(bytes(prior['payload']))
                if predecessor['reviewer_id'] != authenticated_reviewer or predecessor['target'] != review['target']:
                    raise ValueError('Revision must retain reader and exact report target')
                if connection.execute('SELECT 1 FROM reviews WHERE supersedes = ?', (review['supersedes'],)).fetchone():
                    raise ValueError('Previous review already has a revision')
            connection.execute('INSERT INTO reviews(feedback_id, reviewer_id, analysis_id, supersedes, payload_sha256, payload, received_at) '
                               'VALUES (?, ?, ?, ?, ?, ?, ?)',
                               (review['feedback_id'], authenticated_reviewer, review['target']['analysis_id'], review['supersedes'], checksum, payload,
                                datetime.now(timezone.utc).isoformat()))
        return {'feedback_id': review['feedback_id'], 'payload_sha256': checksum, 'status': 'saved_on_utility'}

    def pending(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Queue batch limit must be 1-100')
        with self.connect() as connection:
            rows = connection.execute('SELECT payload, payload_sha256 FROM reviews WHERE acknowledged_at IS NULL '
                                      'ORDER BY sequence LIMIT ?', (limit,)).fetchall()
        return [{'review': parse(bytes(row['payload'])), 'payload_sha256': row['payload_sha256']} for row in rows]

    def acknowledge(self, receipt):
        if not isinstance(receipt, dict) or set(receipt) != {'feedback_id', 'payload_sha256', 'status', 'imported_at'}:
            raise ValueError('Unexpected import receipt')
        identifier(receipt['feedback_id'])
        hash_value(receipt['payload_sha256'])
        if receipt['status'] not in ('imported', 'already_imported'):
            raise ValueError('Receipt does not confirm an import')
        stamp = datetime.fromisoformat(receipt['imported_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Import receipt must have a timezone')
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT * FROM reviews WHERE feedback_id = ?', (receipt['feedback_id'],)).fetchone()
            if not row or row['payload_sha256'] != receipt['payload_sha256']:
                raise ValueError('Receipt differs from queued review')
            if row['acknowledged_at']:
                previous = json.loads(row['receipt'])
                if previous['imported_at'] != receipt['imported_at']:
                    raise ValueError('Repeated receipt has different import time')
                return 'already_acknowledged'
            connection.execute('UPDATE reviews SET acknowledged_at = ?, receipt = ? WHERE feedback_id = ?',
                               (datetime.now(timezone.utc).isoformat(), canonical(receipt).decode(), receipt['feedback_id']))
        return 'acknowledged'

    def history(self, reviewer, analysis_id, before=None, limit=100):
        identifier(reviewer)
        if type(analysis_id) is not int or analysis_id <= 0:
            raise ValueError('Invalid analysis ID')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('History batch limit must be 1-100')
        with self.connect() as connection:
            ceiling = 9223372036854775807
            if before is not None:
                identifier(before)
                cursor = connection.execute('SELECT sequence FROM reviews WHERE feedback_id = ? AND reviewer_id = ? AND analysis_id = ?',
                                            (before, reviewer, analysis_id)).fetchone()
                if not cursor:
                    raise ValueError('History cursor does not belong to this reader/report')
                ceiling = cursor['sequence']
            rows = connection.execute('SELECT payload, acknowledged_at FROM reviews WHERE reviewer_id = ? AND analysis_id = ? AND sequence < ? '
                                      'ORDER BY sequence DESC LIMIT ?', (reviewer, analysis_id, ceiling, limit)).fetchall()
        return [{'review': parse(bytes(row['payload'])), 'status': 'imported' if row['acknowledged_at'] else 'saved_on_utility'}
                for row in rows]
