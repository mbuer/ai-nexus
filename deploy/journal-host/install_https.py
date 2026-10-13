"""Initial parallel HTTPS installation; root execution requires --install-approved.

No renewal, feedback endpoint, database operation or AI Nexus connection.
The staging directory and recovery receipt are retained on success and failure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import time
import urllib.request

from https_plan import plan, SITE, ENABLED, CERTIFICATE, KEY


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=30).stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exclusive(path, data, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def rollback(packet, state, execute=run):
    """Undo only changes owned by this attempt; never overwrite the HTTP site."""
    errors = []
    link = Path(ENABLED)
    if state.get('link_created'):
        try:
            if not link.is_symlink() or os.readlink(link) != SITE:
                raise ValueError('HTTPS link changed; manual inspection required')
            link.unlink()
            execute('nginx', '-t')
            execute('systemctl', 'reload', 'nginx')
        except Exception as exc:
            errors.append(str(exc))
    if state.get('firewall_attempted'):
        try:
            execute(*packet['firewall_remove_if_added_by_this_installation'])
        except Exception as exc:
            errors.append(str(exc))
    return errors


def request(url, context=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       urllib.request.HTTPSHandler(context=context))
    with opener.open(url, timeout=10) as response:
        if response.status != 200:
            raise ValueError('Journal verification did not return HTTP 200')
        response.read(1024)


def install(stage):
    if stage.is_symlink():
        raise ValueError('Staging directory is a symlink')
    stage = stage.resolve()
    if (not re.fullmatch(r'/tmp/journal-https\.[A-Za-z0-9]{10}', str(stage))
            or stage.stat().st_mode & 0o077
            or stage.stat().st_uid != int(os.environ.get('SUDO_UID', '-1'))):
        raise ValueError('Staging must be the operator-owned private upload directory')
    metadata = json.loads((stage / 'install-review.json').read_text())
    if metadata['schema_version'] != 'journal-https-package-v1':
        raise ValueError('Unknown installation package')
    required = {'https_plan.py', 'install_https.py', 'nginx-https.conf.example',
                'journal-authority.crt', 'journal-server.crt', 'journal-server.key'}
    if set(metadata['files_sha256']) != required or {p.name for p in stage.iterdir()} != required | {'install-review.json'}:
        raise ValueError('Unexpected upload contents')
    for name, expected in metadata['files_sha256'].items():
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name):
            raise ValueError('Unsafe package filename')
        path = stage / name
        if path.is_symlink() or digest(path) != expected:
            raise ValueError('Package content differs: ' + name)
    packet = plan(metadata['address'], metadata['lan'], metadata['interface'],
                  (stage / 'nginx-https.conf.example').read_text())
    address = metadata['address']
    for target in (SITE, ENABLED, CERTIFICATE, KEY):
        if os.path.lexists(target):
            raise ValueError('Existing HTTPS material requires inspection: ' + target)
    certdir = Path(CERTIFICATE).parent
    if certdir.exists() or certdir.is_symlink():
        raise ValueError('Existing TLS directory requires inspection')
    for parent in (Path(SITE).parent, Path(ENABLED).parent, certdir.parent):
        if parent.is_symlink() or parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022:
            raise ValueError('System directory is not root-controlled')
    http = Path('/etc/nginx/sites-available/birdynator-journal')
    original_hash = digest(http)
    config = http.read_text()
    if f'{address}:8080' not in config or '/srv/birdynator-journal/current' not in config:
        raise ValueError('Original journal configuration differs from inspection')
    if run('ss', '-H', '-lnt', 'sport', '=', ':443').strip():
        raise ValueError('Port 443 already in use')
    addresses = json.loads(run('ip', '-j', '-4', 'address', 'show', 'dev', metadata['interface']))
    if not any(item['local'] == address for entry in addresses for item in entry['addr_info']):
        raise ValueError('Reserved address is not assigned to reviewed interface')
    if 'Status: active' not in run('ufw', 'status') or '443' in run('ufw', 'show', 'added'):
        raise ValueError('Firewall inactive or an existing 443 rule needs review')
    run('nginx', '-t')
    run('openssl', 'verify', '-CAfile', str(stage / 'journal-authority.crt'),
        '-verify_ip', address, '-purpose', 'sslserver', str(stage / 'journal-server.crt'))
    run('openssl', 'x509', '-in', str(stage / 'journal-server.crt'), '-checkend', '2592000', '-noout')
    if run('openssl', 'pkey', '-in', str(stage / 'journal-server.key'), '-pubout') != run(
            'openssl', 'x509', '-in', str(stage / 'journal-server.crt'), '-pubkey', '-noout'):
        raise ValueError('Server key pair mismatch')
    context = ssl.create_default_context(cafile=str(stage / 'journal-authority.crt'))
    request(f'http://{address}:8080/')
    with socket.create_connection((address, 8000), timeout=5):
        pass
    receipt = Path('/var/lib/birdynator-journal-https')
    if os.path.lexists(receipt):
        raise ValueError('Existing installation receipt requires inspection before retry')
    receipt.mkdir(mode=0o700)
    exclusive(receipt / 'http-before.conf', http.read_bytes(), 0o600)
    state = {'status': 'started', 'http_sha256': original_hash, 'stage': str(stage),
             'origin': packet['origin'], 'server_expires': metadata['server_expires']}

    def save():
        temporary = receipt / 'receipt.tmp'
        exclusive(temporary, json.dumps(state, indent=2).encode(), 0o600)
        temporary.replace(receipt / 'receipt.json')

    save()
    try:
        certdir.mkdir(mode=0o700)
        exclusive(Path(CERTIFICATE), (stage / 'journal-server.crt').read_bytes(), 0o644)
        exclusive(Path(KEY), (stage / 'journal-server.key').read_bytes(), 0o600)
        exclusive(Path(SITE), packet['config_text'].encode(), 0o644)
        Path(ENABLED).symlink_to(SITE)
        state['link_created'] = True
        save()
        run('nginx', '-t')
        state['firewall_attempted'] = True
        save()
        run(*packet['firewall_add'])
        run('systemctl', 'reload', 'nginx')
        for attempt in range(5):
            try:
                request(packet['origin'] + '/', context)
                break
            except (OSError, urllib.error.URLError):
                if attempt == 4:
                    raise
                time.sleep(1)
        request(f'http://{address}:8080/')
        with socket.create_connection((address, 8000), timeout=5):
            pass
        if digest(http) != original_hash:
            raise ValueError('Original HTTP configuration changed during installation')
        state['status'] = 'verified'
        save()
        print('HTTPS journal verified: ' + packet['origin'], flush=True)
        print('HTTP configuration unchanged; Companion port reachable. Browser/device trust still needs your check.')
    except Exception:
        state['status'] = 'failed'
        state['rollback_errors'] = rollback(packet, state)
        save()
        print('Stopped; recovery receipt: ' + str(receipt / 'receipt.json'), flush=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-approved', action='store_true')
    args = parser.parse_args()
    if not args.install_approved or os.geteuid() != 0:
        raise SystemExit('Explicit approval switch and sudo required; nothing changed')
    install(Path(__file__).parent)
