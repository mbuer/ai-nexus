import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'clients/windows/journal'))
AVAILABLE = importlib.util.find_spec('cryptography') is not None
if AVAILABLE:
    import certificate_export as exporter
    import certificates
from test_journal_publication import temporary_export


@unittest.skipUnless(AVAILABLE, 'Optional Windows TLS preparation dependency not installed')
class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.manifest = certificates.material('192.0.2.10', b'disposable-export-passphrase')

    def test_private_directory_guard_precedes_key_writes(self):
        with temporary_export() as directory:
            with self.assertRaisesRegex(ValueError, 'permissions'):
                exporter.write_bundle(directory, self.files, self.manifest, b'disposable-export-passphrase',
                                      guard=Mock(side_effect=ValueError('permissions')))
            self.assertEqual(list(directory.iterdir()), [])

    def test_verified_export_separates_transfer_and_backup_material(self):
        with temporary_export() as directory:
            packet = exporter.write_bundle(directory, self.files, self.manifest, b'disposable-export-passphrase', guard=lambda _: None)
            self.assertEqual(packet['export_status'], 'complete')
            self.assertEqual({p.name for p in (directory / 'utility').iterdir()}, set(certificates.SERVER_FILES))
            self.assertEqual({p.name for p in (directory / 'device-trust').iterdir()}, set(certificates.AUTHORITY_FILES[1:]))
            files, loaded = exporter.load_bundle(directory, b'disposable-export-passphrase', guard=lambda _: None)
            self.assertEqual(files, self.files)
            self.assertEqual(loaded['authority_sha256'], packet['authority_sha256'])
            with self.assertRaisesRegex(ValueError, 'not empty'):
                exporter.write_bundle(directory, self.files, self.manifest, b'disposable-export-passphrase', guard=lambda _: None)

    def test_failed_export_retains_incomplete_receipt_and_refuses_use(self):
        with temporary_export() as directory:
            original = Path.mkdir
            from unittest.mock import patch
            def fail(path, *args, **kwargs):
                if path.name == 'utility':
                    raise OSError('simulated storage failure')
                return original(path, *args, **kwargs)
            with patch.object(Path, 'mkdir', fail):
                with self.assertRaises(OSError):
                    exporter.write_bundle(directory, self.files, self.manifest, b'disposable-export-passphrase', guard=lambda _: None)
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                exporter.load_bundle(directory, b'disposable-export-passphrase', guard=lambda _: None)
