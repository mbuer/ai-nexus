import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from test_birdynator_journal import temporary_export
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/birdynator'))
from journal import display_date, report_from_analysis, render_html

spec = importlib.util.spec_from_file_location('journal_publisher', ROOT / 'deploy/journal-host/publish_utility.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublicationTests(unittest.TestCase):
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
