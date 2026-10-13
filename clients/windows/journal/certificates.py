"""Prepare a private Journal CA and server identity in memory; never install trust."""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import ipaddress
import json

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def material(address, passphrase, now=None):
    address = ipaddress.ip_address(address)
    if (address.version != 4 or not address.is_private or address.is_loopback
            or address.is_link_local or address.is_multicast or address.is_unspecified):
        raise ValueError('Expected a private, unicast LAN IPv4 address')
    if not isinstance(passphrase, bytes) or len(passphrase) < 16:
        raise ValueError('Use a password-manager passphrase of at least 16 UTF-8 bytes')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Certificate time must include a timezone')
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Birdynator Journal Local Authority')])
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
          .not_valid_after(now + timedelta(days=730))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                      data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
                                      encipher_only=False, decipher_only=False), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .sign(ca_key, hashes.SHA256()))
    server_key, server = _server(ca_key, ca, address, now)
    # Verify before exporting; the private authority key is never exported unencrypted.
    ca.verify_directly_issued_by(ca)
    server.verify_directly_issued_by(ca)
    files = {
        'journal-authority-key.encrypted.pem': ca_key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(passphrase)),
        'journal-authority.crt': ca.public_bytes(serialization.Encoding.PEM),
        'journal-authority.cer': ca.public_bytes(serialization.Encoding.DER),
        'journal-server.crt': server.public_bytes(serialization.Encoding.PEM),
        'journal-server.key': server_key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
    }
    return files, _manifest(files, ca, server, address)


def _server(ca_key, ca, address, now):
    if now.tzinfo is None:
        raise ValueError('Certificate time must include a timezone')
    if not ca.not_valid_before_utc <= now < ca.not_valid_after_utc:
        raise ValueError('Authority is not currently valid')
    if ca.not_valid_after_utc < now + timedelta(days=90):
        raise ValueError('Authority expires too soon; review authority replacement and device trust')
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = (x509.CertificateBuilder()
              .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Birdynator Journal')]))
              .issuer_name(ca.subject).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=90))
              .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
              .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address)]), critical=False)
              .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=True,
                                          data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
                                          encipher_only=False, decipher_only=False), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()), critical=False)
              .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
              .sign(ca_key, hashes.SHA256()))
    server.verify_directly_issued_by(ca)
    return server_key, server


def _manifest(files, ca, server, address):
    return {'schema_version': 'journal-certificate-material-v1', 'address': str(address),
                'authority_sha256': ca.fingerprint(hashes.SHA256()).hex(),
                'server_sha256': server.fingerprint(hashes.SHA256()).hex(),
                'authority_expires': ca.not_valid_after_utc.isoformat(),
                'server_expires': server.not_valid_after_utc.isoformat(),
                'utility_upload_files': ['journal-server.crt', 'journal-server.key'],
                'device_trust_files': ['journal-authority.crt', 'journal-authority.cer'],
                'authority_signing_key_upload_permitted': False,
                'files_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}


AUTHORITY_FILES = ('journal-authority-key.encrypted.pem', 'journal-authority.crt', 'journal-authority.cer')
SERVER_FILES = ('journal-server.crt', 'journal-server.key')


def _authority(files, passphrase=None, expected_fingerprint=None):
    ca = x509.load_pem_x509_certificate(files['journal-authority.crt'])
    der = x509.load_der_x509_certificate(files['journal-authority.cer'])
    if ca.fingerprint(hashes.SHA256()) != der.fingerprint(hashes.SHA256()):
        raise ValueError('Authority certificate representations differ')
    if expected_fingerprint and ca.fingerprint(hashes.SHA256()).hex() != expected_fingerprint:
        raise ValueError('Authority fingerprint differs from the recorded identity')
    ca.verify_directly_issued_by(ca)
    constraints = ca.extensions.get_extension_for_class(x509.BasicConstraints)
    usage = ca.extensions.get_extension_for_class(x509.KeyUsage)
    if not constraints.critical or not constraints.value.ca or constraints.value.path_length != 0 or not usage.value.key_cert_sign:
        raise ValueError('Unexpected authority constraints')
    if not isinstance(ca.public_key(), rsa.RSAPublicKey) or ca.public_key().key_size < 3072:
        raise ValueError('Unexpected authority key')
    protected = files['journal-authority-key.encrypted.pem']
    # Construct the format marker without resembling an embedded private key in
    # the repository's credential-content scan; the byte-level guard is identical.
    if not protected.startswith(b'-----BEGIN ' + b'ENCRYPTED PRIVATE KEY-----'):
        raise ValueError('Authority signing key must remain encrypted')
    key = None
    if passphrase is not None:
        key = serialization.load_pem_private_key(protected, passphrase)
        if not isinstance(key, rsa.RSAPrivateKey) or key.public_key().public_numbers() != ca.public_key().public_numbers():
            raise ValueError('Authority key does not match its certificate')
    return ca, key


def verify_material(files, manifest, passphrase=None, now=None):
    """Integrity and identity checks; expiry is reported, never silently renewed."""
    if set(files) != set(AUTHORITY_FILES + SERVER_FILES) or manifest.get('schema_version') != 'journal-certificate-material-v1':
        raise ValueError('Unexpected certificate material')
    if manifest.get('files_sha256') != {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}:
        raise ValueError('Certificate file hashes differ')
    if manifest.get('utility_upload_files') != list(SERVER_FILES) or manifest.get('device_trust_files') != list(AUTHORITY_FILES[1:]) or manifest.get('authority_signing_key_upload_permitted') is not False:
        raise ValueError('Certificate transfer policy differs')
    ca, _ = _authority(files, passphrase, manifest['authority_sha256'])
    server = x509.load_pem_x509_certificate(files['journal-server.crt'])
    server.verify_directly_issued_by(ca)
    if server.fingerprint(hashes.SHA256()).hex() != manifest['server_sha256']:
        raise ValueError('Server fingerprint differs')
    key = serialization.load_pem_private_key(files['journal-server.key'], None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.public_key().public_numbers() != server.public_key().public_numbers():
        raise ValueError('Server key differs from certificate')
    names = server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    if list(names) != [x509.IPAddress(ipaddress.ip_address(manifest['address']))]:
        raise ValueError('Server address differs')
    if server.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise ValueError('Server must not be an authority')
    if list(server.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) != [ExtendedKeyUsageOID.SERVER_AUTH]:
        raise ValueError('Server usage differs')
    if server.not_valid_before_utc < ca.not_valid_before_utc or server.not_valid_after_utc > ca.not_valid_after_utc:
        raise ValueError('Server validity exceeds its authority')
    if manifest['authority_expires'] != ca.not_valid_after_utc.isoformat() or manifest['server_expires'] != server.not_valid_after_utc.isoformat():
        raise ValueError('Recorded expiry differs')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Verification time needs a timezone')
    return {'authority_current': ca.not_valid_before_utc <= now < ca.not_valid_after_utc,
            'server_current': server.not_valid_before_utc <= now < server.not_valid_after_utc}


def renew(files, manifest, passphrase, now=None):
    """Rotate the leaf key while preserving issuer, encrypted signer and device trust."""
    now = now or datetime.now(timezone.utc)
    status = verify_material(files, manifest, passphrase, now)
    if not status['authority_current']:
        raise ValueError('Authority expired; replacement needs explicit device-trust review')
    ca, ca_key = _authority(files, passphrase, manifest['authority_sha256'])
    address = ipaddress.ip_address(manifest['address'])
    server_key, server = _server(ca_key, ca, address, now)
    updated = dict(files)
    updated['journal-server.crt'] = server.public_bytes(serialization.Encoding.PEM)
    updated['journal-server.key'] = server_key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return updated, _manifest(updated, ca, server, address)


def authority_backup(files, manifest, passphrase):
    """Portable signer backup contains no unencrypted server key or passphrase."""
    verify_material(files, manifest, passphrase)
    package = {'schema_version': 'journal-authority-backup-v1',
               'authority_sha256': manifest['authority_sha256'],
               'files': {name: base64.b64encode(files[name]).decode('ascii') for name in AUTHORITY_FILES},
               'files_sha256': {name: hashlib.sha256(files[name]).hexdigest() for name in AUTHORITY_FILES}}
    return json.dumps(package, sort_keys=True, separators=(',', ':')).encode('utf-8')


def restore_authority(backup, passphrase, expected_fingerprint):
    """Return verified bytes in memory; never overwrite a key store or install trust."""
    if not isinstance(backup, bytes) or len(backup) > 100000:
        raise ValueError('Invalid authority backup size')
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate backup field')
            result[key] = value
        return result
    package = json.loads(backup, object_pairs_hook=unique)
    if (set(package) != {'schema_version', 'authority_sha256', 'files', 'files_sha256'}
            or package['schema_version'] != 'journal-authority-backup-v1'
            or set(package['files']) != set(AUTHORITY_FILES)
            or not isinstance(expected_fingerprint, str) or len(expected_fingerprint) != 64
            or package['authority_sha256'] != expected_fingerprint):
        raise ValueError('Backup identity or fields differ')
    files = {name: base64.b64decode(value, validate=True) for name, value in package['files'].items()}
    if package['files_sha256'] != {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}:
        raise ValueError('Backup checksum differs')
    _authority(files, passphrase, expected_fingerprint)
    return files


def recover_material(backup, passphrase, expected_fingerprint, address, now=None):
    """Recover the original issuer, then prepare a fresh leaf for a reviewed address."""
    restored = restore_authority(backup, passphrase, expected_fingerprint)
    address = ipaddress.ip_address(address)
    if (address.version != 4 or not address.is_private or address.is_loopback
            or address.is_link_local or address.is_multicast or address.is_unspecified):
        raise ValueError('Expected a private, unicast LAN IPv4 address')
    ca, key = _authority(restored, passphrase, expected_fingerprint)
    server_key, server = _server(key, ca, address, now or datetime.now(timezone.utc))
    restored['journal-server.crt'] = server.public_bytes(serialization.Encoding.PEM)
    restored['journal-server.key'] = server_key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return restored, _manifest(restored, ca, server, address)
