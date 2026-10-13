import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HOST = Path(__file__).resolve().parents[1] / 'deploy/journal-host'
sys.path.insert(0, str(HOST))
spec = importlib.util.spec_from_file_location('renew_https', HOST / 'renew_https.py')
renewal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renewal)


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.certificate = Path(self.temp.name) / 'server.crt'
        self.key = Path(self.temp.name) / 'server.key'
        self.certificate.write_bytes(b'old certificate')
        self.key.write_bytes(b'old key')
        self.flags = patch.object(renewal.os, 'O_NOFOLLOW', getattr(renewal.os, 'O_NOFOLLOW', 0), create=True)
        self.flags.start()
        self.addCleanup(self.flags.stop)

    def test_replacement_checked_before_success(self):
        def check():
            self.assertEqual(self.certificate.read_bytes(), b'new certificate')
            self.assertEqual(self.key.read_bytes(), b'new key')
        renewal.replace_pair(self.certificate, self.key, b'new certificate', b'new key', check,
                             lambda: self.fail('No rollback expected'))

    def test_failed_verification_restores_both_files(self):
        def fail():
            raise ValueError('TLS verification failed')
        def restored():
            self.assertEqual(self.certificate.read_bytes(), b'old certificate')
            self.assertEqual(self.key.read_bytes(), b'old key')
        with self.assertRaisesRegex(ValueError, 'TLS verification failed'):
            renewal.replace_pair(self.certificate, self.key, b'new certificate', b'new key', fail, restored)

    def test_failed_recovery_is_reported(self):
        def fail():
            raise ValueError('check failed')
        with self.assertRaisesRegex(RuntimeError, 'old-pair reload failed'):
            renewal.replace_pair(self.certificate, self.key, b'new certificate', b'new key', fail, fail)

    def test_leftover_pending_file_stops_replacement(self):
        self.key.with_name('server.key.renewal-pending').write_bytes(b'interrupted')
        with self.assertRaises(FileExistsError):
            renewal.replace_pair(self.certificate, self.key, b'new certificate', b'new key', lambda: None, lambda: None)
        self.assertEqual(self.certificate.read_bytes(), b'old certificate')
        self.assertEqual(self.key.read_bytes(), b'old key')
