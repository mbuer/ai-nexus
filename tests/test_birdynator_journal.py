import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import shutil
import uuid
from contextlib import contextmanager
import importlib.util
import types
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/birdynator'))
from journal import digest, export, render_html, report_from_analysis, validate
from test_birdynator_evidence import fixture, build_evidence


@contextmanager
def temporary_export():
    # Default mkdir permissions work with the bundled Windows sandbox runtime.
    root = Path(tempfile.gettempdir()).resolve()
    directory = root / ('journal-test-' + uuid.uuid4().hex)
    directory.mkdir()
    try:
        yield directory
    finally:
        if directory.resolve().parent != root:
            raise ValueError('Test cleanup escaped temporary root')
        shutil.rmtree(directory)


class JournalTests(unittest.TestCase):
    def setUp(self):
        a, s, end = fixture()
        self.evidence = build_evidence(a, s, end)
        self.record = {'id': 9, 'source_latest_hour': end.isoformat(),
                       'source_digest': digest(self.evidence), 'model': 'offline-test',
                       'result_text': "# A day of variety\n\n## Today's story\n\nA little story about species.\n\n## Birdynator is watching\n\nWill this return?",
                       'parameters': {}}

    def test_sections_and_empty_cards(self):
        report = report_from_analysis(self.record, self.evidence)
        self.assertEqual(report['headline'], 'A day of variety')
        self.assertEqual(report['todays_story'], 'A little story about species.')
        self.assertEqual(report['watching']['kind'], 'hypothesis')
        output = render_html(report)
        self.assertNotIn('<h2>Model surprise', output)
        self.assertNotIn('<h2>Bird to explore', output)
        self.assertIn('Recorded species diversity', output)

    def test_legacy_preserves_text_without_inventing_evidence(self):
        self.record['result_text'] = 'An old report without headings.'
        report = report_from_analysis(self.record)
        self.assertEqual(report['todays_story'], self.record['result_text'])
        self.assertEqual(report['summary_metrics'], [])
        self.assertNotIn('<svg', render_html(report))

    def test_saved_evidence_and_curly_heading_are_used(self):
        self.record['parameters']['journal_report'] = {'evidence': self.evidence}
        self.record['result_text'] = self.record['result_text'].replace("Today's", 'Today\u2019s')
        report = report_from_analysis(self.record)
        self.assertEqual(report['todays_story'], 'A little story about species.')
        self.assertEqual(report['evidence'], self.evidence)
        altered = copy.deepcopy(self.record)
        altered['parameters']['journal_report']['evidence']['daily_evidence'][0]['distinct_species'] = 999
        with self.assertRaises(ValueError):
            report_from_analysis(altered)

    def test_two_findings_preserve_legacy_extra_paragraphs(self):
        self.record['result_text'] += '\n\n## What caught my eye\n\nFirst.\n\nSecond.\n\nA shared caution.'
        report = report_from_analysis(self.record)
        self.assertEqual(len(report['findings']), 2)
        self.assertEqual(report['findings'][1]['text'], 'Second.\n\nA shared caution.')

    def test_escaping_and_trusted_links(self):
        self.record['result_text'] = '<script>alert(1)</script>\n\n[bad](javascript:alert) [good](https://ebird.org/species/test)'
        output = render_html(report_from_analysis(self.record))
        self.assertNotIn('<script>', output)
        self.assertNotIn('href="javascript:', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertIn('href="https://ebird.org/species/test"', output)

    def test_evidence_digest_and_metrics_cannot_be_fabricated(self):
        altered = copy.deepcopy(self.evidence)
        altered['daily_evidence'][0]['distinct_species'] = 999
        with self.assertRaises(ValueError):
            report_from_analysis(self.record, altered)
        report = report_from_analysis(self.record, self.evidence)
        report['summary_metrics'][0]['value'] = 999
        with self.assertRaises(ValueError):
            validate(report)

    def test_incomplete_today_omits_metrics(self):
        self.evidence['interesting_signals']['observations']['today'] = None
        self.record['source_digest'] = digest(self.evidence)
        self.assertEqual(report_from_analysis(self.record, self.evidence)['summary_metrics'], [])

    def test_archive_keeps_multiple_runs_and_fallbacks(self):
        with temporary_export() as directory:
            first = report_from_analysis(self.record, self.evidence)
            export(first, directory)
            self.record['id'] = 10
            export(report_from_analysis(self.record), directory)
            root = Path(directory)
            self.assertEqual(len(list(root.glob('*.html'))), 3)
            self.assertIn('-9.html', (root/'index.html').read_text())
            self.assertIn('-10.html', (root/'index.html').read_text())
            saved = json.loads(next(root.glob('*-9.json')).read_text())
            self.assertEqual(saved, first)

    def test_path_traversal_is_rejected(self):
        self.record['id'] = '../../escape'
        with self.assertRaises(ValueError):
            report_from_analysis(self.record)

    def test_chart_is_omitted_when_story_does_not_use_diversity(self):
        self.record['result_text'] = "Today's story\n\nA visitor returned at dawn."
        self.assertNotIn('<svg', render_html(report_from_analysis(self.record, self.evidence)))

    def test_evidence_cutoff_mismatch_is_rejected(self):
        self.record['source_latest_hour'] = '2026-09-17T23:00:00'
        with self.assertRaises(ValueError):
            report_from_analysis(self.record, self.evidence)

    def test_saved_export_reads_only_and_keeps_actual_analysis_id(self):
        spec = importlib.util.spec_from_file_location('journal_app',
            Path(__file__).resolve().parents[1] / 'services/birdynator/birdynator.py')
        app = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'psycopg': types.ModuleType('psycopg')}):
            spec.loader.exec_module(app)
        stored = dict(self.record)
        stored['id'] = 'pending'
        self.record['parameters']['journal_report'] = report_from_analysis(stored, self.evidence)
        conn = MagicMock()
        cursor = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        args = types.SimpleNamespace(analysis_id=9, headline=None, output='unused')
        with patch.object(app, 'connect', return_value=conn), \
             patch.object(app, 'rows_as_dicts', return_value=[self.record]), \
             patch.object(app, 'export_journal') as writer, patch('builtins.print'):
            app.journal_saved(args)
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertTrue(cursor.execute.call_args.args[0].startswith('SELECT '))
        self.assertEqual(cursor.execute.call_args.args[1], (9,))
        report = writer.call_args.args[0]
        self.assertEqual(report['provenance']['analysis_id'], '9')
        self.assertEqual(report['evidence'], self.evidence)


if __name__ == '__main__':
    unittest.main()
