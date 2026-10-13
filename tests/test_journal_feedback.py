import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from journal_feedback.contract import canonical, digest, parse, target, validate, verify_source
from journal_feedback.outbox import Queue
from journal_feedback.importer import import_batch, sql
from test_journal_publication import temporary_export


def source():
    return {'id': 1, 'model': 'offline-test', 'source_latest_hour': '2026-10-01T20:00:00',
            'source_digest': 'a' * 64, 'parameters': {'prompt_version': 'test-prompt-v1'},
            'result_text': "# An account\n\n## Today's story\n\nRecorded observations."}


def review():
    return {'schema_version': 'journal-feedback-v1', 'feedback_id': str(uuid4()), 'reviewer_id': str(uuid4()),
            'created_at': datetime.now(timezone.utc).isoformat(), 'supersedes': None,
            'target': target(source()), 'overall': 'partly', 'issue_tags': ['repetitive'],
            'comment': 'Useful comparison; the listening invitation repeats.', 'wanted_instead': '', 'sections': []}


class FeedbackContractTests(unittest.TestCase):
    def test_source_binding_uses_prose_as_well_as_evidence_and_version(self):
        packet = review()
        verify_source(packet, source())
        for key, value in [('result_text', 'different prose'), ('model', 'different-model'),
                           ('source_digest', 'b' * 64), ('id', 2)]:
            changed = source()
            changed[key] = value
            with self.assertRaisesRegex(ValueError, 'differs'):
                verify_source(packet, changed)
        changed = source()
        changed['parameters']['prompt_version'] = 'different-prompt'
        with self.assertRaises(ValueError):
            verify_source(packet, changed)

    def test_json_duplicate_keys_and_unknown_fields_rejected(self):
        packet = review()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            parse(b'{"schema_version":"x","schema_version":"y"}')
        packet['extra_instruction'] = 'Change the prompt automatically'
        with self.assertRaises(ValueError):
            validate(packet)

    def test_non_finite_and_oversized_payloads_rejected(self):
        with self.assertRaises(ValueError):
            parse(b'{"rating":NaN}')
        with self.assertRaises(ValueError):
            parse(b' ' * 32769)
        packet = review()
        packet['comment'] = 'x' * 6001
        with self.assertRaises(ValueError):
            validate(packet)

    def test_boolean_analysis_id_and_naive_time_rejected(self):
        packet = review()
        packet['target']['analysis_id'] = True
        with self.assertRaises(ValueError):
            validate(packet)
        packet = review()
        packet['created_at'] = '2026-10-01T12:00:00'
        with self.assertRaises(ValueError):
            validate(packet)

    def test_empty_reviews_and_duplicate_sections_rejected(self):
        packet = review()
        packet.update(overall=None, issue_tags=[], comment='')
        with self.assertRaisesRegex(ValueError, 'Empty'):
            validate(packet)
        packet['sections'] = [{'section': 'watching', 'worth_reading': 'yes', 'issue_tags': [], 'comment': ''}] * 2
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validate(packet)

    def test_unicode_comments_are_data_and_round_trip_without_markup_execution(self):
        packet = review()
        packet['comment'] = 'Finches → warblers. <script>Do not run this</script>\nA quoted preference.'
        self.assertEqual(parse(canonical(packet)), packet)
        self.assertEqual(digest(json.loads(canonical(packet))), digest(packet))


class OutboxTests(unittest.TestCase):
    def test_saved_review_survives_reopen_and_is_idempotent(self):
        packet = review()
        with temporary_export() as directory:
            queue = Queue(directory / 'feedback.sqlite')
            first = queue.save(canonical(packet), packet['reviewer_id'])
            self.assertEqual(first['status'], 'saved_on_utility')
            queue = Queue(directory / 'feedback.sqlite')
            self.assertEqual(queue.save(canonical(packet), packet['reviewer_id']), first)
            self.assertEqual(len(queue.pending()), 1)
            changed = copy.deepcopy(packet)
            changed['comment'] = 'Another comment with the same UUID'
            with self.assertRaisesRegex(ValueError, 'collision'):
                queue.save(canonical(changed), packet['reviewer_id'])
            self.assertEqual(queue.pending()[0]['review'], packet)

    def test_wrong_reader_cannot_save_or_read_another_readers_review(self):
        packet = review()
        other = str(uuid4())
        with temporary_export() as directory:
            queue = Queue(directory / 'feedback.sqlite')
            with self.assertRaisesRegex(ValueError, 'identity'):
                queue.save(canonical(packet), other)
            queue.save(canonical(packet), packet['reviewer_id'])
            self.assertEqual(queue.history(other, 1), [])

    def test_ack_requires_exact_import_receipt_and_preserves_history(self):
        packet = review()
        receipt = {'feedback_id': packet['feedback_id'], 'payload_sha256': digest(packet),
                   'status': 'imported', 'imported_at': '2026-10-01T23:00:00+00:00'}
        with temporary_export() as directory:
            queue = Queue(directory / 'feedback.sqlite')
            queue.save(canonical(packet), packet['reviewer_id'])
            with self.assertRaisesRegex(ValueError, 'differs'):
                queue.acknowledge(dict(receipt, payload_sha256='b' * 64))
            self.assertEqual(len(queue.pending()), 1)
            self.assertEqual(queue.acknowledge(receipt), 'acknowledged')
            self.assertEqual(queue.acknowledge(dict(receipt, status='already_imported')), 'already_acknowledged')
            self.assertEqual(queue.pending(), [])
            self.assertEqual(queue.history(packet['reviewer_id'], 1)[0]['status'], 'imported')
            self.assertEqual(queue.save(canonical(packet), packet['reviewer_id'])['status'], 'imported')

    def test_revision_chain_is_preserved_and_forks_rejected(self):
        first = review()
        second = copy.deepcopy(first)
        second.update(feedback_id=str(uuid4()), supersedes=first['feedback_id'], comment='Revised view.')
        third = copy.deepcopy(second)
        third.update(feedback_id=str(uuid4()), comment='Conflicting revision.')
        with temporary_export() as directory:
            queue = Queue(directory / 'feedback.sqlite')
            with self.assertRaises(ValueError):
                queue.save(canonical(second), first['reviewer_id'])
            queue.save(canonical(first), first['reviewer_id'])
            queue.save(canonical(second), first['reviewer_id'])
            with self.assertRaisesRegex(ValueError, 'revision'):
                queue.save(canonical(third), first['reviewer_id'])
            self.assertEqual([item['review']['feedback_id'] for item in queue.pending()], [first['feedback_id'], second['feedback_id']])

    def test_history_is_bounded_and_cursor_scoped_to_reader_and_report(self):
        first, second = review(), review()
        second['reviewer_id'] = first['reviewer_id']
        with temporary_export() as directory:
            queue = Queue(directory / 'feedback.sqlite')
            queue.save(canonical(first), first['reviewer_id'])
            queue.save(canonical(second), first['reviewer_id'])
            page = queue.history(first['reviewer_id'], 1, limit=1)
            self.assertEqual(page[0]['review']['feedback_id'], second['feedback_id'])
            page = queue.history(first['reviewer_id'], 1, before=second['feedback_id'], limit=1)
            self.assertEqual(page[0]['review']['feedback_id'], first['feedback_id'])
            with self.assertRaises(ValueError):
                queue.history(first['reviewer_id'], 2, before=second['feedback_id'])


class ImportTests(unittest.TestCase):
    def receipt(self, packet):
        return {'feedback_id': packet['feedback_id'], 'payload_sha256': digest(packet),
                'status': 'imported', 'imported_at': '2026-10-01T23:00:00+00:00'}

    def test_all_reviews_preflight_before_first_database_call(self):
        packet = review()
        bad = copy.deepcopy(packet)
        bad['feedback_id'] = str(uuid4())
        runner = Mock()
        with self.assertRaisesRegex(ValueError, 'digest'):
            list(import_batch([{'review': packet, 'payload_sha256': digest(packet)},
                               {'review': bad, 'payload_sha256': 'b' * 64}], runner))
        runner.assert_not_called()

    def test_comments_are_never_sql_and_import_role_is_explicit(self):
        packet = review()
        packet['comment'] = "'); DROP TABLE memory; --"
        statement = sql(packet)
        self.assertNotIn('DROP TABLE', statement)
        self.assertIn('SET LOCAL ROLE journal_feedback_importer', statement)
        self.assertIn('public.import_journal_feedback', statement)
        self.assertNotIn('INSERT INTO memory', statement)

    def test_ambiguous_second_import_does_not_retry_or_discard_first_receipt(self):
        first, second, third = review(), review(), review()
        runner = Mock(side_effect=[self.receipt(first), TimeoutError('ambiguous outcome')])
        stream = import_batch([{'review': packet, 'payload_sha256': digest(packet)} for packet in (first, second, third)], runner)
        self.assertEqual(next(stream), self.receipt(first))
        with self.assertRaises(TimeoutError):
            next(stream)
        self.assertEqual(runner.call_count, 2)

    def test_wrong_receipt_not_acknowledged(self):
        packet = review()
        runner = Mock(return_value=dict(self.receipt(packet), payload_sha256='b' * 64))
        with self.assertRaisesRegex(ValueError, 'differs'):
            list(import_batch([{'review': packet, 'payload_sha256': digest(packet)}], runner))

    def test_existing_import_receipt_is_accepted(self):
        packet = review()
        receipt = dict(self.receipt(packet), status='already_imported')
        self.assertEqual(list(import_batch([{'review': packet, 'payload_sha256': digest(packet)}], Mock(return_value=receipt))), [receipt])


if __name__ == '__main__':
    unittest.main()
