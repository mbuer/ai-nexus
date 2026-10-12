import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/birdynator'))
from trial_review import species_history, prepare_request, editorial_context, reading_preview
from journal import digest, report_from_analysis
from test_birdynator_evidence import fixture, build_evidence

class TrialReviewTests(unittest.TestCase):
    def history(self):
        start = datetime(2026, 10, 1)
        end = start + timedelta(days=13, hours=20)
        activity = [{'hour_local': start + timedelta(days=d, hours=h)} for d in range(14) for h in range(21)]
        species = [{'hour_local': start + timedelta(days=d, hours=8), 'species': 'New regular label',
                    'detection_count': 3, 'station_id': 'test'} for d in range(7, 14)]
        species += [{'hour_local': start + timedelta(days=d, hours=9), 'species': 'Earlier label',
                     'detection_count': 1, 'station_id': 'test'} for d in range(7)]
        return activity, species, end

    def report(self):
        a, s, end = fixture()
        evidence = build_evidence(a, s, end)
        return report_from_analysis({'id': 16, 'model': 'offline-test', 'source_latest_hour': end.isoformat(),
            'source_digest': digest(evidence), 'parameters': {'prompt_version': 'original-test'},
            'result_text': '# Original headline\n\n## Today\'s story\n\nAn original species account.'}, evidence)

    def test_species_frequency_composition_and_unknown_states(self):
        a, s, end = self.history()
        history = species_history(a, s, end)
        rows = {r['species']: r for r in history['species']}
        current = rows['New regular label']
        self.assertEqual(current['recent']['days_with_detections'], 7)
        self.assertEqual(current['recent']['occupied_hours'], 7)
        self.assertEqual(current['recent']['classifier_detections'], 21)
        self.assertIsNone(current['days'][0]['detections'])
        self.assertEqual(current['days'][0]['state'], 'no_record_unknown_effort')
        self.assertEqual(history['composition']['recorded_only_recent'], ['New regular label'])
        self.assertEqual(history['composition']['recorded_only_previous'], ['Earlier label'])
        self.assertEqual({c['kind'] for c in history['candidates']}, {'repeated_recent_recordings', 'recorded_less_often'})

    def test_missing_aggregate_hour_blocks_frequency_candidate(self):
        a, s, end = self.history()
        a.pop(0)
        history = species_history(a, s, end)
        self.assertFalse(history['both_windows_aggregate_complete'])
        self.assertEqual(history['candidates'], [])

    def test_confidence_is_hourly_maximum_range_and_missing_is_unknown(self):
        a, s, end = self.history()
        s[0]['max_confidence'] = .65
        s[1]['max_confidence'] = .9
        history = species_history(a, s, end)
        row = next(r for r in history['species'] if r['species'] == 'New regular label')
        self.assertEqual(row['recent']['hourly_max_confidence_min'], .65)
        self.assertEqual(row['recent']['hourly_max_confidence_max'], .9)
        self.assertEqual(row['recent']['hourly_max_confidence_bins_reported'], 2)
        self.assertIsNone(row['previous']['hourly_max_confidence_min'])
        s[0]['max_confidence'] = 65
        with self.assertRaises(ValueError):
            species_history(a, s, end)

    def test_quiet_identical_history_does_not_manufacture_change(self):
        a, _, end = self.history()
        s = [{'hour_local': end - timedelta(days=d), 'species': 'Steady label', 'detection_count': 1} for d in range(14)]
        history = species_history(a, s, end)
        self.assertEqual(history['candidates'], [])
        self.assertEqual(history['composition']['recorded_in_both'], ['Steady label'])
        self.assertEqual(species_history(a, [], end)['candidates'], [])

    def test_future_and_unmatched_hours_do_not_leak(self):
        a, s, end = self.history()
        original = species_history(a, s, end)
        s += [{'hour_local': end + timedelta(hours=1), 'species': 'Future label', 'detection_count': 99},
              {'hour_local': end - timedelta(days=1) + timedelta(hours=1), 'species': 'Outside matched hours', 'detection_count': 99}]
        self.assertEqual(species_history(a, s, end), original)

    def test_duplicate_species_hours_and_mixed_stations_rejected(self):
        a, s, end = self.history()
        with self.assertRaises(ValueError):
            species_history(a, s + [s[0]], end)
        s[0]['station_id'] = 'second-test'
        with self.assertRaises(ValueError):
            species_history(a, s, end)

    def test_editorial_context_has_no_previous_claims_or_future_topics(self):
        report = self.report()
        report['todays_story'] = 'Untrusted previous interpretation must never become evidence.'
        cutoff = datetime.fromisoformat(report['evidence']['window']['latest_hour'])
        topics = editorial_context([report], cutoff + timedelta(days=1))
        self.assertNotIn('Untrusted previous interpretation', json.dumps(topics))
        self.assertEqual(editorial_context([report], cutoff - timedelta(hours=1)), [])
        report['provenance']['source_digest'] = 'bad'
        with self.assertRaises(ValueError):
            editorial_context([report], cutoff + timedelta(days=1))

    def test_request_preserves_evidence_and_reports_missing_species_history(self):
        report = self.report()
        original = copy.deepcopy(report)
        request = prepare_request(report)
        self.assertFalse(request['longitudinal_available'])
        self.assertEqual(request['source_evidence_digest'], report['provenance']['source_digest'])
        self.assertEqual(json.loads(request['request']['input'])['source_evidence'], report['evidence'])
        self.assertEqual(report, original)
        self.assertFalse(request['request']['store'])
        with self.assertRaises(ValueError):
            prepare_request(report, {'status': 'available', 'through': '2000-01-01T00:00:00'})

    def test_preview_is_original_prose_escaped_and_has_no_feedback_submission(self):
        report = self.report()
        report['headline'] = '<script>untrusted</script>'
        preview = reading_preview(report)
        self.assertIn('no revised model generation', preview)
        self.assertIn('An original species account.', preview)
        self.assertIn('&lt;script&gt;', preview)
        self.assertNotIn('<script>', preview)
        self.assertNotIn('<form', preview)
        self.assertIn("form-action 'none'", preview)

if __name__ == '__main__':
    unittest.main()
