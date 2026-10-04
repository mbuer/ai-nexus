import importlib.util
import hashlib
import json
import random
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services' / 'birdynator'))
from evidence import build_evidence, analysis_payload, spearman, prediction_signals, temperature_summary


def fixture(days=16):
    activity, species = [], []
    start = datetime(2026, 9, 1)
    for day in range(days):
        for hour in range(24):
            t = start + timedelta(days=day, hours=hour)
            activity.append(dict(hour_local=t, activity_index=day + 1, raw_detections=day + 2,
                                 temperature_f=80-day, humidity_pct=40+day,
                                 hours_from_sunrise=hour-6))
            if hour == 8:
                for n in range(day + 1):
                    species.append(dict(hour_local=t, species=f'Bird {n:02}', detection_count=1,
                                        present=1, max_confidence=.8))
    return activity, species, activity[-1]['hour_local']


class EvidenceTests(unittest.TestCase):
    def test_temperature_rank_does_not_follow_diversity_rank(self):
        a, s, end = fixture()
        for r in a:
            if r['hour_local'].date() == end.date():
                r['temperature_f'] = 72.5
        today = build_evidence(a, s, end)['interesting_signals']['observations']['today']
        self.assertEqual(today['distinct_species']['rank_desc'], 1)
        self.assertEqual(today['temperature_f']['rank_asc'], 8)
        self.assertEqual(today['temperature_f']['minimum_f'], 66)
        self.assertEqual(today['temperature_f']['sample_days'], 16)

    def test_temperature_rank_ties_and_missing_values(self):
        rank = temperature_summary(70, [70, 70, 80])
        self.assertEqual((rank['rank_asc'], rank['rank_desc'], rank['ties']), (1, 2, 2))
        a, s, end = fixture()
        a[-1]['temperature_f'] = None
        today = build_evidence(a, s, end)['interesting_signals']['observations']['today']
        self.assertNotIn('temperature_f', today)

    def test_ranks_diversity_and_novelty(self):
        a, s, end = fixture()
        o = build_evidence(a, s, end)['interesting_signals']['observations']
        self.assertEqual(o['today']['distinct_species'], dict(value=16, rank_desc=1, ties=1, sample_days=16))
        self.assertEqual([r['species'] for r in o['novelty']['first_seen_in_window']], ['Bird 15'])
        self.assertEqual(o['today']['raw_detections'], 17*24)

    def test_cutoff_excludes_future_and_order_does_not_matter(self):
        a, s, end = fixture()
        cutoff = end - timedelta(days=3)
        expected = build_evidence(a, s, cutoff)
        a.append(dict(a[-1], hour_local=end+timedelta(days=1), activity_index=999999))
        random.Random(7).shuffle(a)
        random.Random(8).shuffle(s)
        self.assertEqual(expected, build_evidence(a, s, cutoff))
        self.assertNotIn('Bird 15', json.dumps(expected))

    def test_matching_partial_days_and_ties(self):
        a, s, end = fixture()
        for r in a:
            r['activity_index'] = 1
        data = build_evidence(a, s, end.replace(hour=12))
        rank = data['interesting_signals']['observations']['today']['activity_index']
        self.assertEqual(rank, dict(value=13, rank_desc=1, ties=16, sample_days=16))

    def test_missing_hour_is_not_zero_filled(self):
        a, s, end = fixture()
        a = [r for r in a if r['hour_local'] != end.replace(hour=4)]
        data = build_evidence(a, s, end)
        self.assertIsNone(data['interesting_signals']['observations']['today'])
        self.assertEqual(data['coverage']['excluded_incomplete_days'], 1)

    def test_nonfinite_weather_is_excluded(self):
        a, s, end = fixture()
        for r in a:
            r['temperature_f'] = float('nan')
            r['humidity_pct'] = None
        data = build_evidence(a, s, end)
        self.assertEqual(data['interesting_signals']['correlations'], [])
        json.dumps(data, allow_nan=False)

    def test_spearman_ties_constant_and_baseline_only(self):
        self.assertAlmostEqual(spearman([1, 1, 3], [3, 3, 1]), -1)
        self.assertIsNone(spearman([1, 1], [1, 2]))
        a, s, end = fixture()
        correlations = build_evidence(a, s, end)['interesting_signals']['correlations']
        self.assertEqual(len(correlations), 2)
        self.assertTrue(all(r['sample_days'] == 15 for r in correlations))
        a, s, end = fixture(5)
        self.assertEqual(build_evidence(a, s, end)['interesting_signals']['correlations'], [])

    def test_returning_species_and_unusual_hour(self):
        a, s, end = fixture()
        s = [r for r in s if r['species'] != 'Bird 00' or r['hour_local'].day <= 6]
        s.append(dict(hour_local=end, species='Bird 00', detection_count=2, max_confidence=.9))
        o = build_evidence(a, s, end)['interesting_signals']['observations']
        self.assertEqual(o['novelty']['returning_after_gap'][0]['species'], 'Bird 00')
        self.assertEqual(o['unusual_hours'][0]['hour_of_day'], 23)

    def test_sunrise_shift_requires_history_and_offsets(self):
        a, s, end = fixture()
        for r in a:
            if r['hour_local'].date() == end.date():
                r['hours_from_sunrise'] += 2
        o = build_evidence(a, s, end)['interesting_signals']['observations']
        self.assertEqual(o['sunrise_relative_shift']['shift_hours'], 2)
        for r in a:
            r.pop('hours_from_sunrise')
        self.assertIsNone(build_evidence(a, s, end)['interesting_signals']['observations']['sunrise_relative_shift'])

    def test_three_day_trend_and_gap(self):
        a, s, end = fixture()
        for r in a:
            r['activity_index'] = 3 if r['hour_local'].day >= 14 else 1
        o = build_evidence(a, s, end)['interesting_signals']['observations']
        self.assertEqual(o['emerging_trends'][0]['values'], [72, 72, 72])
        a = [r for r in a if r['hour_local'] != end-timedelta(days=1)]
        self.assertEqual(build_evidence(a, s, end)['interesting_signals']['observations']['emerging_trends'], [])

    def test_unlimited_species_and_explore_choice(self):
        a, s, end = fixture(31)
        result = build_evidence(a, s, end)['interesting_signals']
        self.assertEqual(result['observations']['today']['distinct_species']['value'], 31)
        self.assertEqual(result['bird_to_explore']['species'], 'Bird 30')

    def test_invalid_bounds_duplicates_and_multiple_stations(self):
        a, s, end = fixture()
        for cutoff in (end.replace(minute=30), end.isoformat()+'+00:00'):
            with self.assertRaises(ValueError):
                build_evidence(a, s, cutoff)
        with self.assertRaises(ValueError):
            build_evidence(a, s, end, recent_hours=0)
        with self.assertRaises(ValueError):
            build_evidence(a+[a[0]], s, end)
        with self.assertRaises(ValueError):
            build_evidence(a, s+[dict(s[-1], station_id='second')], end)

    def test_prediction_provenance_join_and_deduplication(self):
        target = datetime(2026, 9, 24, 10)
        a = [dict(hour_local=target, activity_index=42)]
        def row(created, value=10):
            return dict(predicted_hour=target, prediction_created_at=created, model='experimental',
                        predicted_activity=value, actual_activity=999)
        rows = [row('2026-09-24T16:00:00+00:00'), row('2026-09-24T16:30:00+00:00', 12),
                row('2026-09-24T18:00:00+00:00', 0), row('2026-09-24T09:00:00')]
        data = prediction_signals(rows, a, target-timedelta(days=1), target)
        self.assertEqual(data['eligible_forecasts'], 1)
        self.assertEqual(data['surprises'][0]['actual_activity'], 42)
        self.assertEqual(data['surprises'][0]['predicted_activity'], 12)
        self.assertEqual(prediction_signals(None, a, target, target)['surprises'], [])

    def test_prompt_contract_and_stable_payload(self):
        a, s, end = fixture()
        dataset = build_evidence(a, s, end)
        payload, context = analysis_payload(dataset, 'test-model')
        self.assertFalse(payload['store'])
        for heading in ("Today's story", 'What caught my eye', 'Something to watch', 'Model surprise', 'Bird to explore'):
            self.assertIn(heading, payload['instructions'])
        self.assertIn('No external enrichment', payload['instructions'])
        self.assertIn('not individual birds', payload['instructions'])
        self.assertIn('rank_asc=1 for lowest', payload['instructions'])
        self.assertIn('SAME metric', payload['instructions'])
        self.assertIn('No word targets or padding', payload['instructions'])
        self.assertIn('Balance scientific care', payload['instructions'])
        self.assertIn('comparison scope needed to assess', payload['instructions'])
        self.assertIn('ties=1 means unique', payload['instructions'])
        self.assertIn('only ties>1 permits', payload['instructions'])
        self.assertIn('never imply recording access was verified', payload['instructions'])
        self.assertIn('most informative unanswered question', payload['instructions'])
        self.assertIn('never HTML, JSON', payload['instructions'])
        self.assertIn('six to ten words', payload['instructions'])
        self.assertIn('one meaningful\ncomparison', payload['instructions'])
        self.assertIn('imagined local\nscene', payload['instructions'])
        self.assertIn('supplied sunrise evidence', payload['instructions'])
        self.assertIn('not\ninterchangeable', payload['instructions'])
        self.assertIn('two to four short connected paragraphs', payload['instructions'])
        self.assertIn('both rank first across at least seven comparable days', payload['instructions'])
        self.assertIn('without implying a historical', payload['instructions'])
        self.assertIn('caveat once', payload['instructions'])
        self.assertEqual(dataset, json.loads(context))
        self.assertEqual((payload, context), analysis_payload(dict(reversed(list(dataset.items()))), 'test-model'))


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A DB driver is deliberately unnecessary for offline unit tests.
        spec = importlib.util.spec_from_file_location('birdynator_under_test',
            Path(__file__).resolve().parents[1] / 'services/birdynator/birdynator.py')
        cls.app = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'psycopg': types.ModuleType('psycopg')}):
            spec.loader.exec_module(cls.app)

    def test_sql_uses_shared_cutoff_and_readonly_snapshot(self):
        a, s, end = fixture()
        conn = MagicMock()
        cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        with patch.object(self.app, 'connect_birdnet', return_value=conn), patch.object(
                self.app, 'rows_as_dicts', side_effect=[a, s]):
            result = self.app.birdnet_comparison(24, 30, 1, end.isoformat())
        calls = cur.execute.call_args_list
        self.assertIn('REPEATABLE READ, READ ONLY', calls[0].args[0])
        self.assertEqual(calls[1].args[1], calls[2].args[1])
        self.assertNotIn('LIMIT', calls[2].args[0])
        self.assertEqual(result, build_evidence(a, s, end))

    def test_evidence_only_has_no_openai_or_persistence(self):
        a, s, end = fixture()
        args = types.SimpleNamespace(hours=24, baseline_days=30, top_species=25,
                                     through=None, tier='default', evidence_only=True)
        with patch.object(self.app, 'birdnet_comparison', return_value=build_evidence(a, s, end)), \
             patch.object(self.app, 'openai_opener') as api, patch.object(self.app, 'save_analysis') as save, \
             patch('builtins.print'):
            self.app.analyze_birdnet(args)
        api.assert_not_called()
        save.assert_not_called()

    def test_analysis_sends_v2_context_and_saves_matching_digest(self):
        a, s, end = fixture()
        dataset = build_evidence(a, s, end)
        args = types.SimpleNamespace(hours=24, baseline_days=30, top_species=25,
                                     through=end.isoformat(), tier='default', evidence_only=False)
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(
            {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Test narrative'}]}]}).encode()
        with patch.object(self.app, 'birdnet_comparison', return_value=dataset), \
             patch.object(self.app, 'openai_opener', return_value=opener), \
             patch.object(self.app, 'openai_key', return_value='offline-test'), \
             patch.object(self.app, 'save_analysis', return_value=1) as save, patch('builtins.print'):
            self.app.analyze_birdnet(args)
        request = opener.open.call_args.args[0]
        payload = json.loads(request.data)
        expected, context = analysis_payload(dataset, self.app.MODEL_DEFAULT)
        self.assertEqual(payload, expected)
        save.assert_called_once_with(dataset, args, self.app.MODEL_DEFAULT, 'Test narrative',
                                     hashlib.sha256(context.encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
