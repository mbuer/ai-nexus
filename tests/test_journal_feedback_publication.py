import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/birdynator'))
sys.path.insert(0, str(ROOT / 'services'))
import journal
from journal_feedback.outbox import Queue
from journal_feedback.queue_tools import backup
from test_journal_feedback import source, review


class FeedbackPublicationTests(unittest.TestCase):
    def test_reading_markdown_omits_large_request_but_preserves_structured_provenance(self):
        report = journal.report_from_analysis(source())
        request = {'input':'synthetic exact request input'}
        report['provenance']['journal_trial'] = {'request':request, 'request_sha256':journal.digest(request)}
        report['provenance']['prompt_version'] = 'birdynator-narrative-v3.2-trial'
        report['provenance']['journal_trial']['prompt_version'] = 'birdynator-narrative-v3.2-trial'
        markdown = journal.render_markdown(report)
        self.assertNotIn('synthetic exact request input', markdown)
        self.assertIn('Structured report and exact model request', markdown)
        self.assertIn(journal.digest(request), markdown)
        self.assertEqual(report['provenance']['journal_trial']['request'], request)

    def test_opt_in_export_preserves_prose_and_binds_raw_narrative(self):
        record = source()
        report = journal.report_from_analysis(record)
        with tempfile.TemporaryDirectory() as directory:
            plain = journal.export(report, directory)
            self.assertNotIn('data-feedback-target', plain.read_text(encoding='utf-8'))
            decorated = journal.export(report, directory, feedback_record=record)
            self.assertIn('data-feedback-target', decorated.read_text(encoding='utf-8'))
            self.assertEqual(json.loads(decorated.with_suffix('.json').read_text(encoding='utf-8')), report)
            changed = dict(record, result_text=record['result_text'] + '\nInvented extra prose.')
            with self.assertRaises(ValueError):
                journal.export(report, directory, feedback_record=changed)

    def test_backup_preserves_reviews_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            queue = Queue(root / 'queue.sqlite')
            packet = review()
            queue.save(json.dumps(packet).encode(), packet['reviewer_id'])
            snapshot = root / 'snapshot.sqlite'
            backup(queue, snapshot, guard=lambda path: None)
            self.assertEqual(Queue(snapshot).pending(), queue.pending())
            with self.assertRaises(ValueError):
                backup(queue, snapshot, guard=lambda path: None)
