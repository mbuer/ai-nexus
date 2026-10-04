import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from test_birdynator_journal import temporary_export
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/birdynator'))
from journal import display_date, report_from_analysis, render_html, export, homepage_entries
from test_birdynator_journal import temporary_export

spec = importlib.util.spec_from_file_location('journal_publisher', ROOT / 'deploy/journal-host/publish_utility.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublicationTests(unittest.TestCase):
    def test_homepage_keeps_latest_day_and_retains_earlier_files(self):
        with temporary_export() as directory:
            for identifier, day in [(9, '2026-09-30'), (10, '2026-10-03'), (13, '2026-10-03')]:
                record = {'id': identifier, 'model': 'offline', 'source_latest_hour': day + 'T12:00:00',
                          'source_digest': None, 'parameters': {},
                          'result_text': '# Saved report ' + str(identifier) + '\n\n## Today\n\nText.'}
                export(report_from_analysis(record), directory)
            page = (directory / 'index.html').read_text(encoding='utf-8')
            self.assertIn('2026-10-03-13.html', page)
            self.assertIn('2026-09-30-9.html', page)
            self.assertNotIn('2026-10-03-10.html', page)
            self.assertTrue((directory / '2026-10-03-10.html').is_file())
            self.assertIn('2026-10-03-10.md', (directory / 'index.md').read_text(encoding='utf-8'))

    def test_publisher_and_renderer_use_numeric_latest_id(self):
        entries = [('2026-10-03', '2026-10-03-9', 'Old'), ('2026-10-03', '2026-10-03-13', 'New'),
                   ('2026-09-30', '2026-09-30-8', 'Previous')]
        self.assertEqual(homepage_entries(entries), publisher.homepage_entries(entries))
        self.assertEqual(homepage_entries(entries)[0][1], '2026-10-03-13')

    def test_weekday_and_citation_title(self):
        record = {
            'id': 13, 'source_latest_hour': '2026-10-03T12:00:00',
            'model': 'offline-test', 'source_digest': None,
            'result_text': "# A sparrow\n\n## Today's story\n\nSee [1](https://www.allaboutbirds.org/guide/Bells_Sparrow/).",
            'parameters': {'external_context': {'cited_sources': [{
                'url': 'https://www.allaboutbirds.org/guide/Bells_Sparrow/',
                'title': 'Bell’s Sparrow | All About Birds',
            }]}},
        }
        page = render_html(report_from_analysis(record))
        self.assertIn('Saturday, October 3, 2026', page)
        self.assertIn('Bell’s Sparrow | All About Birds', page)
        self.assertNotIn('>1</a>', page)

    def test_host_and_renderer_agree_on_date(self):
        self.assertEqual(display_date('2026-10-03'), publisher.display_date('2026-10-03'))

    def test_upload_rejects_checksum_mismatch(self):
        with temporary_export() as directory:
            stage = Path(directory)
            (stage / 'index.html').write_text('changed')
            (stage / 'manifest.json').write_text(json.dumps({
                'version': 1,
                'files': [{'name': 'index.html', 'size': 7,
                           'sha256': hashlib.sha256(b'original').hexdigest()}],
            }))
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                publisher.verified_files(stage)

    def test_upload_rejects_path_traversal(self):
        with temporary_export() as directory:
            stage = Path(directory)
            (stage / 'manifest.json').write_text(json.dumps({
                'version': 1,
                'files': [{'name': '../index.html', 'size': 0, 'sha256': '0' * 64}],
            }))
            with self.assertRaisesRegex(ValueError, 'Unsafe or duplicate filename'):
                publisher.verified_files(stage)
