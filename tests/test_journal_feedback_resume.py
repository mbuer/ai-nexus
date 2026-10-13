"""Synthetic recovery-tree checks; never inspect a real credential or service."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HOST = Path(__file__).resolve().parents[1] / 'deploy/journal-host'
sys.path.insert(0, str(HOST))
spec = importlib.util.spec_from_file_location('feedback_installer_test', HOST / 'install_feedback.py')
installer = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'pwd': SimpleNamespace(getpwnam=lambda _: SimpleNamespace(pw_uid=0)), 'grp': SimpleNamespace()}):
    spec.loader.exec_module(installer)


class ResumeTests(unittest.TestCase):
    def exercise(self, change=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, config, recovery = root / 'app', root / 'config', root / 'recovery'
            for path in (app, app / 'journal_feedback', config, recovery):
                path.mkdir()
            names = ('__init__.py', 'api.py', 'contract.py', 'outbox.py', 'server.py', 'queue_tools.py', 'journal-feedback.js')
            hashes = {}
            for name in names:
                content = ('synthetic ' + name).encode()
                (app / 'journal_feedback' / name).write_bytes(content)
                hashes[name] = hashlib.sha256(content).hexdigest()
            unit, auth, rate = root / 'unit', root / 'auth', root / 'rate'
            unit.write_bytes(b'synthetic unit')
            (app / 'journal-review-sign-in.html').write_bytes(b'synthetic page')
            hashes['journal-feedback.service.example'] = hashlib.sha256(b'synthetic unit').hexdigest()
            hashes['journal-review-sign-in.html'] = hashlib.sha256(b'synthetic page').hexdigest()
            auth.write_text('personal:$6$synthetic$notarealpasswordhash\n')
            reviewer = '11111111-1111-4111-8111-111111111111'
            queue = root / 'queue.sqlite'
            queue.write_bytes(b'synthetic queue placeholder')
            expected = {'origin': 'https://192.0.2.10', 'reviewers': {'personal': reviewer}, 'queue_path': str(queue), 'socket_path': str(root / 'socket')}
            (config / 'service.json').write_text(json.dumps(expected))
            (recovery / 'https-before.conf').write_bytes(b'original config')
            state = {'status': 'failed_needs_inspection', 'rollback_errors': [], 'reviewer_id': reviewer,
                     'origin': expected['origin'], 'http_sha256': 'synthetic-http-hash'}
            (recovery / 'receipt.json').write_text(json.dumps(state))
            review = {'address':'192.0.2.10', 'reviewer_id':reviewer, 'files_sha256':hashes,
                      'previous_https_sha256':hashlib.sha256(b'original config').hexdigest()}
            if change: change(app, recovery)
            original_stat, original_digest = Path.stat, installer.fingerprint
            def protected_stat(path, *args, **kwargs):
                result = original_stat(path, *args, **kwargs)
                return SimpleNamespace(st_uid=0, st_mode=result.st_mode & ~0o077, st_size=result.st_size)
            def fingerprint(path):
                return 'synthetic-http-hash' if path.as_posix().startswith('/etc/') else original_digest(path)
            with patch.multiple(installer, APP=app, CONFIG=config, AUTH=auth, RATE=rate, UNIT=unit, RECOVERY=recovery), \
                 patch.object(Path, 'stat', protected_stat), patch.object(installer, 'fingerprint', fingerprint), \
                 patch.object(installer, 'service_config', return_value=expected), \
                 patch.object(installer, 'run', side_effect=lambda *args: 'inactive' if '--property=ActiveState' in args else 'disabled'):
                return installer.validate_resume(review)

    def test_clean_matching_rollback_can_resume(self):
        self.assertEqual(self.exercise()['status'], 'failed_needs_inspection')

    def test_changed_installed_source_prevents_resume(self):
        with self.assertRaisesRegex(ValueError, 'application differs'):
            self.exercise(lambda app, recovery: (app / 'journal_feedback/api.py').write_bytes(b'changed'))

    def test_rollback_error_prevents_resume(self):
        def change(app, recovery):
            path = recovery / 'receipt.json'
            state = json.loads(path.read_text())
            state['rollback_errors'] = ['reload failed']
            path.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'clean rolled-back'):
            self.exercise(change)

    def test_unexpected_backup_phase_prevents_resume(self):
        with self.assertRaisesRegex(ValueError, 'later installation phase'):
            self.exercise(lambda app, recovery: (recovery / 'initial-queue.sqlite').write_bytes(b'later backup'))
