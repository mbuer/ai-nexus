from datetime import date
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manual_preview', ROOT / 'clients/windows/journal/manual_preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class PreviewTests(unittest.TestCase):
    def test_manual_identity_keeps_request_metadata_and_does_not_claim_scheduled_dates(self):
        original = Mock(return_value=23)
        agent = SimpleNamespace(model_for_tier=lambda tier: 'gpt-6.1-sol', save_analysis=original)
        def analyze(args):
            args.prompt_version = preview.PROMPT
            args.trial_metadata = {'prompt_version':preview.PROMPT, 'start':args.journal_trial_start,
                                   'end':args.journal_trial_end, 'request_sha256':'a' * 64}
            agent.save_analysis({}, args, 'gpt-6.1-sol', 'saved prose', 'b' * 64)
        agent.analyze_birdnet = Mock(side_effect=analyze)
        preview.run_preview(agent, '2026-10-12', '2026-10-13', '2026-10-19', today=date(2026,10,12))
        args = original.call_args.args[1]
        self.assertTrue(args.trial_metadata['manual_preview'])
        self.assertNotIn('start', args.trial_metadata)
        self.assertEqual(args.trial_metadata['scheduled_trial_unchanged']['start'], '2026-10-13')
        self.assertEqual(args.trial_metadata['request_sha256'], 'a' * 64)
        self.assertIs(agent.save_analysis, original)
        agent.analyze_birdnet.assert_called_once()

    def test_expired_date_and_wrong_model_fail_before_model_request(self):
        for model, today in (('gpt-6.1-sol', date(2026,10,13)), ('other-model', date(2026,10,12))):
            agent = SimpleNamespace(model_for_tier=lambda tier: model, analyze_birdnet=Mock(), save_analysis=Mock())
            with self.assertRaises(ValueError):
                preview.run_preview(agent, '2026-10-12', '2026-10-13', '2026-10-19', today=today)
            agent.analyze_birdnet.assert_not_called()

    def test_failure_does_not_retry_and_restores_saver(self):
        original = Mock()
        agent = SimpleNamespace(model_for_tier=lambda tier:'gpt-6.1-sol', save_analysis=original,
                                analyze_birdnet=Mock(side_effect=RuntimeError('provider timeout')))
        with self.assertRaises(RuntimeError):
            preview.run_preview(agent, '2026-10-12', '2026-10-13', '2026-10-19', today=date(2026,10,12))
        agent.analyze_birdnet.assert_called_once()
        self.assertIs(agent.save_analysis, original)
