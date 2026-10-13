import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HOST = Path(__file__).resolve().parents[1] / 'deploy/journal-host'
sys.path.insert(0, str(HOST))
spec = importlib.util.spec_from_file_location('install_https', HOST / 'install_https.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallationTests(unittest.TestCase):
    def test_exclusive_write_preserves_existing_file(self):
        # Linux retains O_NOFOLLOW; Windows test exercises exclusive creation only.
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.os, 'O_NOFOLLOW', getattr(installer.os, 'O_NOFOLLOW', 0), create=True):
            path = Path(directory) / 'key'
            installer.exclusive(path, b'original', 0o600)
            with self.assertRaises(FileExistsError):
                installer.exclusive(path, b'replacement', 0o600)
            self.assertEqual(path.read_bytes(), b'original')

    def test_rollback_does_not_remove_unowned_rule_or_link(self):
        calls = []
        self.assertEqual(installer.rollback({}, {}, lambda *args: calls.append(args)), [])
        self.assertEqual(calls, [])

    def test_firewall_rollback_runs_even_when_link_changed(self):
        calls = []
        with patch.object(installer, 'ENABLED', '/nonexistent-test-link'):
            errors = installer.rollback({'firewall_remove_if_added_by_this_installation': ['ufw', 'delete', 'allow', 'test']},
                                        {'link_created': True, 'firewall_attempted': True},
                                        lambda *args: calls.append(args))
        self.assertEqual(len(errors), 1)
        self.assertEqual(calls, [('ufw', 'delete', 'allow', 'test')])

    def test_invalid_stage_rejected_before_system_commands(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer, 'run') as execute:
            with self.assertRaises(ValueError):
                installer.install(Path(directory))
            execute.assert_not_called()
