import copy
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/birdynator'))
import trial_replay
from trial_review import prepare_request
import test_journal_trial_review as trial_review_tests

class TrialReplayTests(unittest.TestCase):
    def packets(self):
        report = trial_review_tests.TrialReviewTests().report()
        packets = []
        for identifier, day in zip(('16', '19', '22'), ('2026-10-05', '2026-10-08', '2026-10-11')):
            row = copy.deepcopy(report)
            row['provenance']['analysis_id'] = identifier
            row['provenance']['model'] = 'gpt-6.1-sol'
            original = prepare_request(row)
            envelope = json.loads(original['request']['input'])
            cutoff = day + 'T20:00:00'
            envelope['source_evidence']['window']['latest_hour'] = cutoff
            envelope['trial_species_history'] = {'through': cutoff, 'status': 'available'}
            original['request']['input'] = json.dumps(envelope)
            from journal import digest
            original['source_evidence_digest'] = digest(envelope['source_evidence'])
            original['longitudinal_available'] = True
            original['ready_for_model_comparison'] = True
            original['request_sha256'] = trial_replay.request_hash(original['request'])
            packets.append(original)
        return packets

    def app(self):
        app = types.ModuleType('birdynator')
        app.OPENAI_API_URL = 'https://api.openai.com/v1/responses'
        app.openai_key = Mock(return_value='offline-test-key')
        app.openai_opener = Mock()
        app.connect = Mock(side_effect=AssertionError('No database connection permitted'))
        return app

    def test_tampered_request_stops_before_any_api_attempt(self):
        app = self.app()
        packets = self.packets()
        packets[1]['request']['model'] = 'other-model'
        with patch.dict(sys.modules, {'birdynator': app}), self.assertRaises(ValueError):
            trial_replay.run_batch(packets)
        app.openai_key.assert_not_called()

    def test_approved_scope_is_not_expanded(self):
        packets = self.packets()
        with self.assertRaises(ValueError):
            trial_replay.validate_batch(packets[:1])
        packets[2]['source_analysis_id'] = '23'
        with self.assertRaises(ValueError):
            trial_replay.validate_batch(packets)

    def test_success_makes_three_attempts_and_keeps_enrichment_limits(self):
        app = self.app()
        class Response:
            def __enter__(self): return io.BytesIO(b'{"status":"completed"}')
            def __exit__(self, *args): return False
        app.openai_opener.return_value.open.side_effect = lambda *a, **k: Response()
        events = []
        with patch.dict(sys.modules, {'birdynator': app}), patch.object(trial_replay, 'cited_report', return_value=('A trial story.', {'search_calls':[{}], 'cited_sources':[{}]})):
            self.assertTrue(trial_replay.run_batch(self.packets(), emit=lambda line, **k: events.append(json.loads(line))))
        self.assertEqual(app.openai_opener.return_value.open.call_count, 3)
        self.assertEqual([e['event'] for e in events], ['started','completed'] * 3)
        for call in app.openai_opener.return_value.open.call_args_list:
            payload = json.loads(call.args[0].data)
            self.assertFalse(payload['store'])
            self.assertEqual(payload['max_tool_calls'], 2)
            self.assertEqual(payload['tools'][0]['filters']['allowed_domains'], list(trial_replay.DOMAINS))
        app.connect.assert_not_called()

    def test_timeout_stops_without_retry_or_next_report(self):
        app = self.app()
        app.openai_opener.return_value.open.side_effect = TimeoutError('ambiguous')
        events = []
        with patch.dict(sys.modules, {'birdynator': app}):
            self.assertFalse(trial_replay.run_batch(self.packets(), emit=lambda line, **k: events.append(json.loads(line))))
        self.assertEqual(app.openai_opener.return_value.open.call_count, 1)
        self.assertEqual([e['event'] for e in events], ['started','needs_review'])
        app.connect.assert_not_called()

if __name__ == '__main__':
    unittest.main()
