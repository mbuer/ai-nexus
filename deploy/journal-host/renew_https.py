"""Replace only the Journal TLS server pair, with retained backup and rollback.

No firewall/configuration/trust changes. Requires a separately approved renewal.
Interrupted replacements require receipt inspection rather than blind retry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time
import uuid

from https_plan import CERTIFICATE, KEY, SITE
from install_https import digest, exclusive, run, request


def replace_pair(certificate, key, new_certificate, new_key, check, restore_check):
    """Keep nginx on its loaded pair until syntax passes; restore both on failure."""
    old_certificate, old_key = certificate.read_bytes(), key.read_bytes()
    pending_certificate = certificate.with_name(certificate.name + '.renewal-pending')
    pending_key = key.with_name(key.name + '.renewal-pending')
    exclusive(pending_certificate, new_certificate, 0o644)
    exclusive(pending_key, new_key, 0o600)
    try:
        pending_certificate.replace(certificate)
        pending_key.replace(key)
        check()
    except Exception as failure:
        # Exclusive backup files are retained outside this helper before entry.
        restore_certificate = certificate.with_name(certificate.name + '.restore-pending')
        restore_key = key.with_name(key.name + '.restore-pending')
        exclusive(restore_certificate, old_certificate, 0o644)
        exclusive(restore_key, old_key, 0o600)
        restore_certificate.replace(certificate)
        restore_key.replace(key)
        try:
            restore_check()
        except Exception as recovery:
            raise RuntimeError('Replacement failed and old-pair reload failed; inspect receipt') from recovery
        raise failure


def renew(stage):
    if stage.is_symlink():
        raise ValueError('Symlink staging refused')
    stage = stage.resolve()
    if (not re.fullmatch(r'/tmp/journal-renewal\.[A-Za-z0-9]{10}', str(stage))
            or stage.stat().st_mode & 0o077
            or stage.stat().st_uid != int(os.environ.get('SUDO_UID', '-1'))):
        raise ValueError('Expected private operator-owned staging')
    metadata = json.loads((stage / 'renewal-review.json').read_text(encoding='utf-8-sig'))
    required = {'renew_https.py', 'install_https.py', 'https_plan.py', 'journal-authority.crt',
                'journal-server.crt', 'journal-server.key'}
    if (metadata['schema_version'] != 'journal-https-renewal-v1'
            or set(metadata['files_sha256']) != required
            or {p.name for p in stage.iterdir()} != required | {'renewal-review.json'}):
        raise ValueError('Unexpected renewal upload')
    for name, expected in metadata['files_sha256'].items():
        if (stage / name).is_symlink() or digest(stage / name) != expected:
            raise ValueError('Reviewed renewal content changed: ' + name)
    address = metadata['address']
    # Validate the origin without interpolating unchecked values into config/commands.
    import ipaddress
    ip = ipaddress.IPv4Address(address)
    if not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        raise ValueError('Invalid reserved LAN address')
    certificate, key = Path(CERTIFICATE), Path(KEY)
    for target in (certificate, key, certificate.parent, Path(SITE)):
        if target.is_symlink() or target.stat().st_uid != 0 or target.stat().st_mode & 0o022:
            raise ValueError('Existing TLS/configuration is not root-controlled')
    if key.stat().st_mode & 0o077 or certificate.parent.stat().st_mode & 0o077:
        raise ValueError('Existing server key is not private')
    if digest(certificate) != metadata['previous_certificate_file_sha256']:
        raise ValueError('Live server certificate differs from the selected previous export')
    ca = str(stage / 'journal-authority.crt')
    run('openssl', 'verify', '-CAfile', ca, '-no_check_time', '-verify_ip', address,
        '-purpose', 'sslserver', str(certificate))
    run('openssl', 'verify', '-CAfile', ca, '-verify_ip', address,
        '-purpose', 'sslserver', str(stage / 'journal-server.crt'))
    run('openssl', 'x509', '-in', str(stage / 'journal-server.crt'), '-checkend', '2592000', '-noout')
    if run('openssl', 'pkey', '-in', str(stage / 'journal-server.key'), '-pubout') != run(
            'openssl', 'x509', '-in', str(stage / 'journal-server.crt'), '-pubkey', '-noout'):
        raise ValueError('Replacement key pair differs')
    run('nginx', '-t')
    http = Path('/etc/nginx/sites-available/birdynator-journal')
    config_hashes = {str(path): digest(path) for path in (http, Path(SITE))}
    request(f'http://{address}:8080/')
    context = ssl.create_default_context(cafile=ca)
    base = Path('/var/lib/birdynator-journal-https')
    if base.is_symlink() or base.stat().st_uid != 0 or base.stat().st_mode & 0o077:
        raise ValueError('Invalid installation receipt directory')
    renewals = base / 'renewals'
    if not renewals.exists():
        renewals.mkdir(mode=0o700)
    if renewals.is_symlink() or renewals.stat().st_uid != 0 or renewals.stat().st_mode & 0o077:
        raise ValueError('Invalid renewal receipt directory')
    for existing in renewals.iterdir():
        record = existing / 'receipt.json'
        if not record.is_file() or json.loads(record.read_text()).get('status') != 'verified':
            raise ValueError('An earlier renewal needs inspection; no retry')
    receipt = renewals / uuid.uuid4().hex
    receipt.mkdir(mode=0o700)
    exclusive(receipt / 'previous-server.crt', certificate.read_bytes(), 0o600)
    exclusive(receipt / 'previous-server.key', key.read_bytes(), 0o600)
    state = {'status': 'replacing', 'stage': str(stage), 'server_expires': metadata['server_expires'],
             'config_sha256': config_hashes}

    def save():
        temporary = receipt / 'receipt.tmp'
        exclusive(temporary, json.dumps(state, indent=2).encode(), 0o600)
        temporary.replace(receipt / 'receipt.json')

    def reload():
        run('nginx', '-t')
        run('systemctl', 'reload', 'nginx')

    def check():
        reload()
        # nginx reload is asynchronous; wait briefly for the new workers.
        for attempt in range(5):
            with socket.create_connection((address, 443), timeout=10) as connection:
                with context.wrap_socket(connection, server_hostname=address) as secured:
                    served = hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest()
            if served == metadata['server_sha256']:
                break
            if attempt == 4:
                raise ValueError('Served server certificate differs from replacement')
            time.sleep(1)
        request(f'https://{address}/', context)
        request(f'http://{address}:8080/')
        if any(digest(Path(path)) != expected for path, expected in config_hashes.items()):
            raise ValueError('Journal configuration changed during renewal')

    save()
    try:
        replace_pair(certificate, key, (stage / 'journal-server.crt').read_bytes(),
                     (stage / 'journal-server.key').read_bytes(), check, reload)
        state['status'] = 'verified'
        save()
        print('Server renewal verified. Device trust, nginx configuration and firewall unchanged.')
        print('Recovery retained: ' + str(receipt))
    except Exception:
        state['status'] = 'failed_needs_inspection'
        save()
        print('Renewal stopped. Inspect recovery before retrying: ' + str(receipt))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renew-approved', action='store_true')
    args = parser.parse_args()
    if not args.renew_approved or os.geteuid() != 0:
        raise SystemExit('Explicit renewal approval and sudo required; nothing changed')
    renew(Path(__file__).parent)
