from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from journal_feedback.api import API
from journal_feedback.contract import canonical
from test_journal_feedback import review


class FeedbackAPITests(unittest.TestCase):
    def setUp(self):
        self.packet = review()
        self.store = Mock()
        self.api = API(self.store, 'https://journal.example.test', {'personal': self.packet['reviewer_id']})
        self.headers = [('Origin', 'https://journal.example.test'), ('Content-Type', 'application/json')]

    def save(self, **changes):
        args = {'method': 'POST', 'path': '/api/journal-feedback/reviews', 'headers': self.headers,
                'body': canonical(self.packet), 'authenticated_principal': 'personal'}
        args.update(changes)
        return self.api.dispatch(**args)

    def test_origin_and_authentication_are_required_before_storage(self):
        for changes in ({'authenticated_principal': 'unknown'}, {'headers': [('Content-Type', 'application/json')]},
                        {'headers': [('Origin', 'https://other.example.test'), ('Content-Type', 'application/json')]}):
            self.assertEqual(self.save(**changes)[0], 403)
        self.store.save.assert_not_called()

    def test_json_only_bounded_requests_and_repeated_headers(self):
        self.assertEqual(self.save(headers=[('Origin', self.api.origin), ('Content-Type', 'text/plain')])[0], 415)
        self.assertEqual(self.save(body=b'x' * 32769)[0], 413)
        self.assertEqual(self.save(headers=self.headers + [('origin', self.api.origin)])[0], 400)
        self.store.save.assert_not_called()

    def test_save_forwards_only_the_authenticated_reviewer(self):
        self.store.save.return_value = {'status': 'saved_on_utility'}
        status, headers, result = self.save()
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'saved_on_utility')
        self.store.save.assert_called_once_with(canonical(self.packet), self.packet['reviewer_id'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_no_browser_acknowledgment_or_arbitrary_route(self):
        self.assertEqual(self.save(path='/api/journal-feedback/acknowledge')[0], 404)
        self.assertEqual(self.save(method='DELETE')[0], 405)
        self.assertEqual(self.save(method='OPTIONS')[0], 405)
        self.store.acknowledge.assert_not_called()

    def test_history_is_scoped_and_bad_queries_never_reach_storage(self):
        for query in ('analysis_id=1&reviewer_id=someone', 'analysis_id=1&analysis_id=2', 'analysis_id=-1'):
            self.assertEqual(self.api.dispatch('GET', '/api/journal-feedback/history?' + query, [], b'', 'personal')[0], 400)
        self.store.history.assert_not_called()
        self.store.history.return_value = []
        self.assertEqual(self.api.dispatch('GET', '/api/journal-feedback/history?analysis_id=1', [], b'', 'personal')[0], 200)
        self.store.history.assert_called_once_with(self.packet['reviewer_id'], 1, before=None)
        result = self.api.dispatch('GET', '/api/journal-feedback/history?analysis_id=1', [], b'', 'personal')[2]
        self.assertEqual(result['reviewer_id'], self.packet['reviewer_id'])
        self.assertEqual(result['schema_version'], 'journal-feedback-v1')

    def test_revision_conflict_is_visible_without_overwrite(self):
        self.store.save.side_effect = ValueError('Previous review already has a revision')
        self.assertEqual(self.save()[0], 409)

    def test_plain_http_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            API(self.store, 'http://journal.example.test', {'personal': self.packet['reviewer_id']})
