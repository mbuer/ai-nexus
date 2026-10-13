import importlib.util
import ipaddress
import hashlib
import json
from datetime import timedelta
from pathlib import Path
import unittest

CRYPTO_AVAILABLE = importlib.util.find_spec('cryptography') is not None
if CRYPTO_AVAILABLE:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.x509.oid import ExtendedKeyUsageOID

spec = importlib.util.spec_from_file_location('journal_certificates',
    Path(__file__).resolve().parents[1] / 'clients/windows/journal/certificates.py')
certificates = importlib.util.module_from_spec(spec)
if CRYPTO_AVAILABLE:
    spec.loader.exec_module(certificates)


@unittest.skipUnless(CRYPTO_AVAILABLE, 'Optional Windows TLS preparation dependency not installed')
class CertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Synthetic documentation address; no production certificate or trust is created.
        cls.files, cls.manifest = certificates.material('192.0.2.10', b'disposable-test-passphrase')

    def test_signature_address_and_server_only_usage(self):
        ca = x509.load_pem_x509_certificate(self.files['journal-authority.crt'])
        server = x509.load_pem_x509_certificate(self.files['journal-server.crt'])
        server.verify_directly_issued_by(ca)
        self.assertEqual(server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress),
                         [ipaddress.ip_address('192.0.2.10')])
        self.assertEqual(list(server.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value), [ExtendedKeyUsageOID.SERVER_AUTH])
        self.assertFalse(server.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)

    def test_authority_key_is_encrypted_and_passphrase_required(self):
        key = self.files['journal-authority-key.encrypted.pem']
        self.assertIn(b'BEGIN ENCRYPTED PRIVATE KEY', key)
        serialization.load_pem_private_key(key, b'disposable-test-passphrase')
        with self.assertRaises(ValueError):
            serialization.load_pem_private_key(key, b'wrong-passphrase')
        self.assertNotIn('journal-authority-key.encrypted.pem', self.manifest['utility_upload_files'])

    def test_ca_cannot_issue_intermediate_and_leaf_expires_first(self):
        ca = x509.load_pem_x509_certificate(self.files['journal-authority.crt'])
        leaf = x509.load_pem_x509_certificate(self.files['journal-server.crt'])
        self.assertEqual(ca.extensions.get_extension_for_class(x509.BasicConstraints).value.path_length, 0)
        self.assertLess(leaf.not_valid_after_utc, ca.not_valid_after_utc)

    def test_invalid_address_and_weak_passphrase_rejected(self):
        for address in ('127.0.0.1', '0.0.0.0', '8.8.8.8', '::1'):
            with self.assertRaises(ValueError):
                certificates.material(address, b'disposable-test-passphrase')
        with self.assertRaises(ValueError):
            certificates.material('192.0.2.10', b'short')

    def test_renewal_preserves_trust_and_rotates_only_server_material(self):
        ca = x509.load_pem_x509_certificate(self.files['journal-authority.crt'])
        when = ca.not_valid_before_utc + timedelta(days=100)
        renewed, manifest = certificates.renew(self.files, self.manifest, b'disposable-test-passphrase', when)
        for name in certificates.AUTHORITY_FILES:
            self.assertEqual(renewed[name], self.files[name])
        self.assertEqual(manifest['authority_sha256'], self.manifest['authority_sha256'])
        self.assertNotEqual(renewed['journal-server.key'], self.files['journal-server.key'])
        self.assertEqual(manifest['address'], self.manifest['address'])
        self.assertTrue(certificates.verify_material(renewed, manifest, b'disposable-test-passphrase', when)['server_current'])

    def test_near_expired_authority_cannot_be_silently_replaced(self):
        ca = x509.load_pem_x509_certificate(self.files['journal-authority.crt'])
        with self.assertRaisesRegex(ValueError, 'expires too soon'):
            certificates.renew(self.files, self.manifest, b'disposable-test-passphrase', ca.not_valid_after_utc - timedelta(days=10))
        with self.assertRaisesRegex(ValueError, 'expired'):
            certificates.renew(self.files, self.manifest, b'disposable-test-passphrase', ca.not_valid_after_utc + timedelta(days=1))

    def test_backup_contains_only_encrypted_signer_and_public_certificates(self):
        backup = certificates.authority_backup(self.files, self.manifest, b'disposable-test-passphrase')
        payload = json.loads(backup)
        self.assertEqual(set(payload['files']), set(certificates.AUTHORITY_FILES))
        self.assertNotIn(b'disposable-test-passphrase', backup)
        self.assertNotIn('journal-server.key', payload['files'])
        restored = certificates.restore_authority(backup, b'disposable-test-passphrase', self.manifest['authority_sha256'])
        self.assertEqual(restored['journal-authority-key.encrypted.pem'], self.files['journal-authority-key.encrypted.pem'])

    def test_backup_rejects_wrong_identity_password_and_tampering(self):
        backup = certificates.authority_backup(self.files, self.manifest, b'disposable-test-passphrase')
        with self.assertRaisesRegex(ValueError, 'identity'):
            certificates.restore_authority(backup, b'disposable-test-passphrase', '0' * 64)
        with self.assertRaises(ValueError):
            certificates.restore_authority(backup, b'wrong-passphrase', self.manifest['authority_sha256'])
        damaged = json.loads(backup)
        damaged['files_sha256']['journal-authority.crt'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum'):
            certificates.restore_authority(json.dumps(damaged).encode(), b'disposable-test-passphrase', self.manifest['authority_sha256'])

    def test_recovery_issues_new_leaf_using_the_original_authority(self):
        backup = certificates.authority_backup(self.files, self.manifest, b'disposable-test-passphrase')
        files, manifest = certificates.recover_material(backup, b'disposable-test-passphrase', self.manifest['authority_sha256'], '192.0.2.10')
        self.assertEqual(manifest['authority_sha256'], self.manifest['authority_sha256'])
        self.assertNotEqual(files['journal-server.key'], self.files['journal-server.key'])
        certificates.verify_material(files, manifest, b'disposable-test-passphrase')

    def test_mismatched_key_rejected_even_if_manifest_hashes_are_updated(self):
        changed = dict(self.files)
        changed['journal-server.key'] = self.files['journal-authority-key.encrypted.pem']
        manifest = dict(self.manifest)
        manifest['files_sha256'] = {name: hashlib.sha256(data).hexdigest() for name, data in changed.items()}
        with self.assertRaises((ValueError, TypeError)):
            certificates.verify_material(changed, manifest)
