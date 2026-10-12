from datetime import date, datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/birdynator'))
import journal_trial as trial
from journal import digest, report_from_analysis, render_html, export
from test_birdynator_evidence import fixture, build_evidence
from test_birdynator_enrichment import response
from test_journal_publication import temporary_export


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'psycopg': types.ModuleType('psycopg')}):
        spec.loader.exec_module(module)
    return module

daily = load('trial_daily', 'scripts/daily-journal.py')
configure = load('trial_configure', 'scripts/configure-journal-trial.py')


class LiveTrialTests(unittest.TestCase):
    policy = {'start': '2026-10-13', 'end': '2026-10-19', 'prompt_version': trial.PROMPT_VERSION}

    def evidence(self):
        a, s, end = fixture()
        return trial.extend_evidence(build_evidence(a, s, end), a, s)

    def test_bounded_calendar_and_expiry(self):
        for day, active in [(12, False), (13, True), (19, True), (20, False)]:
            self.assertEqual(trial.trial_window('2026-10-13', '2026-10-19', date(2026, 10, day)), active)
        with self.assertRaises(ValueError):
            trial.trial_window('2026-10-13', '2026-10-20', date(2026, 10, 15))

    def test_daily_expiry_selects_baseline_without_new_schedule(self):
        config = {'timezone': 'America/Los_Angeles', 'not_before': '2026-10-04',
                  'journal_trial': self.policy, 'web_enrichment': False}
        for day, active in [(12, False), (13, True), (19, True), (20, False)]:
            with temporary_export() as directory, patch.object(daily, 'latest_today', side_effect=[None, 25]), \
                 patch.object(daily.subprocess, 'run') as model:
                daily.generate(config, directory, datetime(2026, 10, day, 21, tzinfo=ZoneInfo(config['timezone'])))
                self.assertEqual('--journal-trial-start' in model.call_args.args[0], active)
                self.assertEqual(model.call_count, 1)

    def test_invalid_policy_fails_before_lookup_or_model(self):
        config = {'timezone': 'America/Los_Angeles', 'not_before': '2026-10-04',
                  'journal_trial': dict(self.policy, end='2026-10-20')}
        with temporary_export() as directory, patch.object(daily, 'latest_today') as read:
            with self.assertRaises(ValueError):
                daily.generate(config, directory, datetime(2026, 10, 13, 21, tzinfo=ZoneInfo(config['timezone'])))
            read.assert_not_called()

    def test_editorial_topics_do_not_change_source_digest(self):
        data = self.evidence()
        first, second = trial.payload(data, 'offline', []), trial.payload(data, 'offline', [{'topic_key': 'species:X'}])
        self.assertEqual(json.loads(first['input'])['source_evidence'], json.loads(second['input'])['source_evidence'])
        self.assertNotEqual(first['input'], second['input'])
        self.assertNotIn('600-900', first['instructions'])
        self.assertNotIn('450-650', first['instructions'])
        self.assertIn('no word quota', first['instructions'])

    def test_saved_trial_sections_and_single_column_labels(self):
        data = self.evidence()
        record = {'id': 25, 'model': 'offline', 'source_latest_hour': data['window']['latest_hour'],
                  'source_digest': digest(data), 'parameters': {'prompt_version': trial.PROMPT_VERSION,
                  'journal_trial': dict(self.policy, request={'instructions': 'PRIVATE_REQUEST'},
                                        request_sha256=digest({'instructions': 'PRIVATE_REQUEST'}))},
                  'result_text': "# A developing pattern\n\n## Today's story\n\nLead.\n\n## Who is changing\n\nSpecies comparison.\n\n## Following up\n\nNew source observations."}
        report = report_from_analysis(record, data)
        self.assertEqual(report['who_is_changing']['kind'], 'interpretation')
        self.assertEqual(report['following_up']['text'], 'New source observations.')
        page = render_html(report)
        self.assertLess(page.index('<h2>Who is changing'), page.index('<h2>Following up'))
        self.assertNotIn('PRIVATE_REQUEST', page)
        self.assertNotIn('<aside', page)
        self.assertNotIn('<form', page)
        with temporary_export() as directory:
            export(report, directory)
            self.assertIn('Journal trial', (directory / 'index.html').read_text(encoding='utf-8'))
            self.assertNotIn('report 25', (directory / 'index.html').read_text(encoding='utf-8').lower())

    def test_prior_topics_are_read_only_without_generated_prose(self):
        conn = MagicMock()
        report = report_from_analysis({'id': 1, 'model': 'offline',
            'source_latest_hour': self.evidence()['window']['latest_hour'],
            'source_digest': digest(self.evidence()), 'parameters': {},
            'result_text': "Today's story\nEarlier interpretation."}, self.evidence())
        conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [
            (1, 'offline', report['date'], {'journal_report': report})]
        topics = trial.prior_topics(conn, report['provenance']['source_latest_hour'])
        self.assertNotIn('Earlier interpretation', json.dumps(topics))
        calls = conn.cursor.return_value.__enter__.return_value.execute.call_args_list
        self.assertEqual(calls[0].args[0], 'SET TRANSACTION READ ONLY')
        self.assertNotIn('memory', calls[1].args[0])

    def test_trial_request_rejection_has_no_fallback(self):
        self.run_pipeline(HTTPError('https://api.openai.com', 400, 'rejected', {}, None), failure=True)

    def test_trial_missing_search_saves_review_flag_without_second_call(self):
        args, save = self.run_pipeline(response())
        self.assertTrue(args.trial_metadata['citation_review_needed'])
        body = args.trial_metadata['request']
        self.assertEqual(args.trial_metadata['request_sha256'], hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest())
        self.assertEqual(save.call_args.args[4], digest(self.evidence()))

    def run_pipeline(self, result, failure=False):
        app = load('trial_app', 'services/birdynator/birdynator.py')
        args = types.SimpleNamespace(hours=24, baseline_days=30, top_species=25, through=None,
            tier='default', evidence_only=False, web_enrichment=True,
            journal_trial_start=self.policy['start'], journal_trial_end=self.policy['end'])
        opener = MagicMock()
        if isinstance(result, Exception):
            opener.open.side_effect = result
        else:
            opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(result).encode()
        with patch.object(trial, 'trial_window', return_value=True), patch.object(trial, 'prior_topics', return_value=[]), \
             patch.object(app, 'connect'), patch.object(app, 'birdnet_comparison', return_value=self.evidence()), \
             patch.object(app, 'openai_opener', return_value=opener), patch.object(app, 'openai_key', return_value='offline'), \
             patch.object(app, 'save_analysis', return_value=25) as save, patch('builtins.print'):
            if failure:
                with self.assertRaises(HTTPError):
                    app.analyze_birdnet(args)
                save.assert_not_called()
            else:
                app.analyze_birdnet(args)
        self.assertEqual(opener.open.call_count, 1)
        return args, save

    def test_expired_manual_request_makes_no_source_or_model_call(self):
        app = load('expired_app', 'services/birdynator/birdynator.py')
        args = types.SimpleNamespace(journal_trial_start='2026-10-13', journal_trial_end='2026-10-19')
        with patch.object(trial, 'trial_window', return_value=False), patch.object(app, 'birdnet_comparison') as source:
            with self.assertRaisesRegex(ValueError, 'outside'):
                app.analyze_birdnet(args)
            source.assert_not_called()

    def test_trial_persistence_keeps_request_and_never_writes_memory(self):
        app = load('persist_trial_app', 'services/birdynator/birdynator.py')
        args = types.SimpleNamespace(hours=24, baseline_days=30, top_species=25, tier='default',
            prompt_version=trial.PROMPT_VERSION, trial_metadata=dict(self.policy), external_context={'status': 'disabled'})
        data = self.evidence()
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (25,)
        with patch.object(app, 'connect') as connection:
            connection.return_value.__enter__.return_value = conn
            app.save_analysis(data, args, 'offline', "## Today's story\nA useful account.", digest(data))
        query, values = conn.cursor.return_value.__enter__.return_value.execute.call_args.args
        self.assertIn('INSERT INTO analysis_runs', query)
        self.assertNotIn('memory', query)
        parameters = json.loads(values[-2])
        self.assertEqual(parameters['journal_trial'], self.policy)
        self.assertEqual(parameters['prompt_version'], trial.PROMPT_VERSION)
        self.assertEqual(parameters['journal_report']['evidence'], data)

    def test_trial_request_tampering_is_rejected_by_export(self):
        data = self.evidence()
        record = {'id': 25, 'model': 'offline', 'source_latest_hour': data['window']['latest_hour'],
                  'source_digest': digest(data), 'parameters': {'prompt_version': trial.PROMPT_VERSION,
                  'journal_trial': dict(self.policy, request={'input': 'altered'}, request_sha256=digest({'input': 'original'}))},
                  'result_text': "## Today's story\nAn account."}
        with self.assertRaisesRegex(ValueError, 'request digest'):
            report_from_analysis(record, data)


class TrialConfigurationTests(unittest.TestCase):
    def setup_state(self, directory):
        worker = directory / 'worker.py'
        worker.write_text('known old worker')
        (directory / 'installed-files.json').write_text(json.dumps({str(worker): hashlib.sha256(worker.read_bytes()).hexdigest()}))
        (directory / 'config.json').write_text(json.dumps({'timezone': 'America/Los_Angeles', 'time': '21:00',
                                                         'not_before': '2026-10-04', 'web_enrichment': True}))
        source = directory / 'new.py'
        source.write_text('reviewed worker')
        return worker, source

    def test_future_configuration_preserves_schedule_and_can_disable(self):
        with temporary_export() as directory:
            worker, source = self.setup_state(directory)
            # Linux 0700 is replaced by normal Windows test permissions.
            original = Path.mkdir
            with patch.object(configure.subprocess, 'run', return_value=types.SimpleNamespace(stdout=trial.PROMPT_VERSION)) as command, \
                 patch.object(Path, 'mkdir', lambda path, mode=0o777, **kw: original(path, **kw)):
                backup = configure.configure(directory, worker, source, '2026-10-13', today=date(2026, 10, 12))
                state = json.loads((directory / 'config.json').read_text())
                self.assertEqual(state['journal_trial']['end'], '2026-10-19')
                self.assertEqual(state['time'], '21:00')
                self.assertEqual((backup / 'worker.py').read_text(), 'known old worker')
                configure.configure(directory, worker, source, disable=True)
                self.assertNotIn('journal_trial', json.loads((directory / 'config.json').read_text()))
                self.assertEqual(command.call_count, 1)
                self.assertNotIn('analyze-birdnet', str(command.call_args_list))

    def test_unknown_worker_is_not_overwritten(self):
        with temporary_export() as directory:
            worker, source = self.setup_state(directory)
            worker.write_text('unreviewed edit')
            with self.assertRaisesRegex(ValueError, 'Unrecognized'):
                configure.configure(directory, worker, source, '2026-10-13', today=date(2026, 10, 12))
            self.assertNotIn('journal_trial', json.loads((directory / 'config.json').read_text()))

    def test_today_start_rejected_without_runtime_call(self):
        with temporary_export() as directory:
            worker, source = self.setup_state(directory)
            with patch.object(configure.subprocess, 'run') as command:
                with self.assertRaisesRegex(ValueError, 'future'):
                    configure.configure(directory, worker, source, '2026-10-12', today=date(2026, 10, 12))
                command.assert_not_called()
