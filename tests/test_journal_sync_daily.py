import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
from test_birdynator_journal import temporary_export

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'clients/windows/journal'))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

sync = load('sync_new', 'clients/windows/journal/sync_new.py')
daily = load('daily_journal', 'scripts/daily-journal.py')
installer = load('install_daily', 'scripts/install-daily-journal.py')


class InstallerTests(unittest.TestCase):
    original_mkdir = Path.mkdir

    def mkdir_for_host(path, mode=0o777, parents=False, exist_ok=False):
        # Windows interprets Linux 0700 as a restrictive ACL for a different SID.
        return InstallerTests.original_mkdir(path, mode=0o777 if os.name == 'nt' else mode,
                                              parents=parents, exist_ok=exist_ok)

    def test_install_schedules_tomorrow_without_starting_generation(self):
        with temporary_export() as directory, patch.object(installer.Path, 'home', return_value=directory), \
             patch.object(installer.os, 'geteuid', return_value=1000, create=True), \
             patch.object(installer.os, 'getuid', return_value=1000, create=True), \
             patch.object(installer.subprocess, 'check_output', return_value=b'yes\n'), \
             patch.object(installer.subprocess, 'run') as commands, patch.object(sys, 'argv', ['installer']), \
             patch.object(Path, 'mkdir', InstallerTests.mkdir_for_host):
            installer.main()
            config = json.loads((directory / '.local/state/birdynator-journal/daily/config.json').read_text())
            tomorrow = datetime.now(ZoneInfo('America/Los_Angeles')).date() + timedelta(days=1)
            self.assertEqual(config['not_before'], tomorrow.isoformat())
            self.assertEqual(config['time'], '21:00')
            calls = [call.args[0] for call in commands.call_args_list]
            verification = next(call for call in calls if call[:2] == ['systemd-analyze', '--user'])
            self.assertIn('--generators', verification)
            self.assertIn(['systemctl', '--user', 'restart', 'ai-nexus-daily-journal.timer'], calls)
            self.assertFalse(any('podman' in call or 'start' in call or
                                 (call[:1] == ['systemctl'] and 'ai-nexus-daily-journal.service' in call)
                                 for call in calls))

    def test_unknown_installed_worker_is_preserved(self):
        with temporary_export() as directory, patch.object(installer.Path, 'home', return_value=directory), \
             patch.object(installer.os, 'geteuid', return_value=1000, create=True), \
             patch.object(installer.os, 'getuid', return_value=1000, create=True), \
             patch.object(installer.subprocess, 'check_output', return_value=b'yes\n'), \
             patch.object(installer.subprocess, 'run') as commands, patch.object(sys, 'argv', ['installer']), \
             patch.object(Path, 'mkdir', InstallerTests.mkdir_for_host):
            worker = directory / '.local/libexec/ai-nexus/daily-journal.py'
            worker.parent.mkdir(parents=True)
            worker.write_text('existing unknown worker')
            with self.assertRaisesRegex(ValueError, 'Unrecognized'):
                installer.main()
            self.assertEqual(worker.read_text(), 'existing unknown worker')
            commands.assert_not_called()


class SyncTests(unittest.TestCase):
    def test_inventory_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            sync.published_ids({'version': 1, 'ids': [13, 13]})

    def test_inventory_rejects_booleans(self):
        with self.assertRaises(ValueError):
            sync.published_ids({'version': 1, 'ids': [True]})

    def test_missing_only_records(self):
        with self.assertRaisesRegex(ValueError, 'ID'):
            sync.validate_records([{'id': 13, 'result_text': 'saved'}], {13})

    def test_up_to_date_makes_no_upload_or_analysis(self):
        with temporary_export() as directory, patch.object(sync, 'ssh_json', side_effect=[
                {'version': 1, 'ids': [13]}, []]) as read, patch.object(sync.subprocess, 'run') as call:
            self.assertEqual(sync.sync('AI_HOST', 'UTILITY_HOST', directory), 0)
            call.assert_not_called()
            self.assertIn('SET TRANSACTION READ ONLY', read.call_args.args[2])
            self.assertNotIn('analyze-birdnet', read.call_args.args[2])

    def test_upload_failure_does_not_mark_ids_published(self):
        record = {'id': 14, 'model': 'offline', 'source_latest_hour': '2026-10-04T20:00:00',
                  'source_digest': None, 'parameters': {}, 'result_text': '# Saved report\n\n## Today\n\nText.'}
        with temporary_export() as directory, patch.object(sync, 'ssh_json', side_effect=[
                {'version': 1, 'ids': [13]}, [record]]) as read, \
             patch.object(sync.subprocess, 'run', side_effect=[
                 types.SimpleNamespace(stdout='/tmp/birdynator-upload.abcdefghij'),
                 RuntimeError('upload failed')]):
            with self.assertRaisesRegex(RuntimeError, 'upload failed'):
                sync.sync('AI_HOST', 'UTILITY_HOST', directory)
            self.assertEqual(read.call_count, 2)

    def test_success_advances_inventory_without_generating(self):
        record = {'id': 14, 'model': 'offline', 'source_latest_hour': '2026-10-04T20:00:00',
                  'source_digest': None, 'parameters': {}, 'result_text': '# Saved report\n\n## Today\n\nText.'}
        with temporary_export() as directory, patch.object(sync, 'ssh_json', side_effect=[
                {'version': 1, 'ids': [13]}, [record], []]) as read, \
             patch.object(sync.subprocess, 'run', side_effect=[
                 types.SimpleNamespace(stdout='/tmp/birdynator-upload.abcdefghij'), None, None]) as remote:
            self.assertEqual(sync.sync('AI_HOST', 'UTILITY_HOST', directory), 1)
            self.assertIn('known = [13, 14]', read.call_args.args[2])
            self.assertEqual(remote.call_args_list[1].args[0][0], 'scp')
            self.assertNotIn('analyze-birdnet', str(remote.call_args_list))


class DailyTests(unittest.TestCase):
    config = {'timezone': 'America/Los_Angeles', 'not_before': '2026-10-04', 'web_enrichment': True}

    def test_no_report_on_installation_day(self):
        with temporary_export() as directory, patch.object(daily, 'latest_today') as read, patch.object(daily.subprocess, 'run') as model:
            result = daily.generate(self.config, directory, datetime(2026, 10, 3, 21, tzinfo=ZoneInfo('America/Los_Angeles')))
            self.assertEqual(result, 'not_started')
            read.assert_not_called()
            model.assert_not_called()

    def test_existing_saved_run_prevents_new_model_call(self):
        with temporary_export() as directory, patch.object(daily, 'latest_today', return_value=14), patch.object(daily.subprocess, 'run') as model:
            self.assertEqual(daily.generate(self.config, directory, datetime(2026, 10, 4, 21, tzinfo=ZoneInfo('America/Los_Angeles'))), 'existing')
            model.assert_not_called()

    def test_ambiguous_failure_is_not_retried(self):
        day = datetime(2026, 10, 4, 21, tzinfo=ZoneInfo('America/Los_Angeles'))
        with temporary_export() as directory, patch.object(daily, 'latest_today', return_value=None), \
             patch.object(daily.subprocess, 'run', side_effect=RuntimeError('timeout')) as model:
            with self.assertRaisesRegex(RuntimeError, 'timeout'):
                daily.generate(self.config, directory, day)
            self.assertEqual(daily.generate(self.config, directory, day), 'already_attempted')
            self.assertEqual(model.call_count, 1)
            self.assertEqual(json.loads((directory / '2026-10-04.json').read_text())['status'], 'needs_review')

    def test_success_records_analysis_id(self):
        day = datetime(2026, 10, 4, 21, tzinfo=ZoneInfo('America/Los_Angeles'))
        with temporary_export() as directory, patch.object(daily, 'latest_today', side_effect=[None, 14]), patch.object(daily.subprocess, 'run') as model:
            self.assertEqual(daily.generate(self.config, directory, day), 'complete')
            self.assertIn('--web-enrichment', model.call_args.args[0])
            self.assertEqual(json.loads((directory / '2026-10-04.json').read_text())['analysis_id'], 14)
