import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/birdynator'))
from enrichment import DOMAINS, allowed_url, cited_report, enable_search
from evidence import analysis_payload
from test_birdynator_evidence import fixture, build_evidence


def response(text='Local report', citations=None, search=False):
    output = [{'type': 'message', 'content': [
        {'type': 'output_text', 'text': text, 'annotations': citations or []}]}]
    if search:
        output.insert(0, {'type': 'web_search_call', 'id': 'search-test',
                         'status': 'completed', 'action': {'sources': []}})
    return {'id': 'response-test', 'status': 'completed', 'output': output}


class EnrichmentTests(unittest.TestCase):
    def test_search_is_optional_bounded_and_does_not_change_evidence(self):
        base, context = analysis_payload({'observation': 1}, 'test-model')
        web = enable_search(base)
        self.assertNotIn('tools', base)
        self.assertEqual(web['input'], base['input'])
        self.assertEqual(web['tools'][0]['filters']['allowed_domains'], list(DOMAINS))
        self.assertEqual(web['max_tool_calls'], 2)
        self.assertEqual(web['tool_choice'], 'required')
        self.assertIn('Research is required; inclusion is optional', web['instructions'])
        self.assertFalse(web['store'])
        self.assertNotIn('No external enrichment is supplied', web['instructions'])
        self.assertIn('Skip unrelated trivia', web['instructions'])

    def test_domains_reject_deceptive_urls(self):
        for url in ('https://www.allaboutbirds.org/guide/test', 'https://ebird.org/species/test'):
            self.assertTrue(allowed_url(url))
        for url in ('http://ebird.org/x', 'https://ebird.org.evil.test/x',
                    'https://evil.test/ebird.org', 'https://user@ebird.org/x',
                    'https://ebird.org:8443/x', 'https://ebird.org:bad/x',
                    'javascript:alert(1)', 'https://ebird.org/with space'):
            self.assertFalse(allowed_url(url), url)

    def test_inline_citation_and_provenance(self):
        annotation = {'type': 'url_citation', 'start_index': 5, 'end_index': 8,
                      'url': 'https://en.wikipedia.org/wiki/Bird_(animal)',
                      'title': 'untrusted ](markup)'}
        text, meta = cited_report(response('Fact [x].', [annotation], True))
        self.assertEqual(text, 'Fact  [1](https://en.wikipedia.org/wiki/Bird_%28animal%29).')
        self.assertEqual(meta['cited_sources'][0]['title'], annotation['title'])
        self.assertEqual(meta['status'], 'cited_context')
        self.assertEqual(meta['response_id'], 'response-test')
        self.assertIn('received_at', meta)

    def test_invalid_sources_and_offsets_are_rejected(self):
        for url, start, end in [('https://evil.test', 0, 1),
                               ('https://ebird.org', -1, 1),
                               ('https://ebird.org', 0, 999)]:
            with self.assertRaises(ValueError):
                cited_report(response('text', [{'type': 'url_citation', 'url': url,
                                               'start_index': start, 'end_index': end}]))
        data = response(search=True)
        data['output'][0]['action']['sources'] = [{'url': 'https://evil.test'}]
        with self.assertRaises(ValueError):
            cited_report(data)


class EnrichmentPipelineTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('enriched_app',
            Path(__file__).resolve().parents[1] / 'services/birdynator/birdynator.py')
        self.app = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'psycopg': types.ModuleType('psycopg')}):
            spec.loader.exec_module(self.app)
        a, s, end = fixture()
        self.dataset = build_evidence(a, s, end)
        self.args = types.SimpleNamespace(hours=24, baseline_days=30, top_species=25,
            through=None, tier='default', evidence_only=False, web_enrichment=True)

    def run_report(self, results):
        opener = MagicMock()
        replies = []
        for value in results:
            if isinstance(value, Exception):
                replies.append(value)
            else:
                reply = MagicMock()
                reply.__enter__.return_value.read.return_value = json.dumps(value).encode()
                replies.append(reply)
        opener.open.side_effect = replies
        with patch.object(self.app, 'birdnet_comparison', return_value=self.dataset), \
             patch.object(self.app, 'openai_opener', return_value=opener), \
             patch.object(self.app, 'openai_key', return_value='test'), \
             patch.object(self.app, 'save_analysis', return_value=8) as save, \
             patch('builtins.print'):
            self.app.analyze_birdnet(self.args)
        return opener, save

    def test_missing_required_search_falls_back_and_evidence_only(self):
        opener, save = self.run_report([response(), response()])
        self.assertEqual(opener.open.call_count, 2)
        self.assertEqual(self.args.external_context['status'], 'fallback_unusable_sources')
        self.assertEqual(save.call_args.args[3], 'Local report')
        self.args.evidence_only = True
        opener, save = self.run_report([])
        opener.open.assert_not_called()
        save.assert_not_called()

    def test_uncited_search_falls_back_without_tools(self):
        opener, save = self.run_report([response(search=True), response('Fallback')])
        self.assertEqual(opener.open.call_count, 2)
        self.assertNotIn('tools', json.loads(opener.open.call_args.args[0].data))
        self.assertEqual(save.call_args.args[3], 'Fallback')
        self.assertEqual(self.args.external_context['status'], 'fallback_unusable_sources')

    def test_cited_search_is_saved_without_fallback(self):
        annotation = {'type': 'url_citation', 'start_index': 5, 'end_index': 8,
                      'url': 'https://www.allaboutbirds.org/guide/Test', 'title': 'Test'}
        opener, save = self.run_report([response('Fact [x].', [annotation], True)])
        self.assertEqual(opener.open.call_count, 1)
        self.assertIn('[1](https://www.allaboutbirds.org/guide/Test)', save.call_args.args[3])
        self.assertEqual(self.args.external_context['status'], 'cited_context')

    def test_rejected_tool_request_falls_back(self):
        opener, save = self.run_report([
            HTTPError('https://api.openai.com', 400, 'Unsupported tool', {}, None), response()])
        self.assertEqual(opener.open.call_count, 2)
        self.assertEqual(self.args.external_context['status'], 'fallback_request_rejected')

    def test_timeout_is_not_retried(self):
        with self.assertRaises(URLError):
            self.run_report([URLError('timeout')])

    def test_provenance_persisted_in_parameters(self):
        self.args.external_context = {'status': 'cited_context', 'cited_sources': [
            {'url': 'https://ebird.org/species/test'}]}
        conn = MagicMock()
        conn.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = (8,)
        with patch.object(self.app, 'connect', return_value=conn):
            self.app.save_analysis(self.dataset, self.args, 'test-model', 'report', 'digest')
        cursor = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        params = json.loads(cursor.execute.call_args.args[1][-2])
        self.assertTrue(params['web_enrichment'])
        self.assertEqual(params['external_context'], self.args.external_context)


if __name__ == '__main__':
    unittest.main()
