"""Approved Utility-only personal login and queue installer. Never touches AI Nexus.

Receipts, credentials and queue are retained on failure. Inspect before retrying.
Password is entered interactively on Utility, hashed via stdin, never logged.
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import pwd
import grp
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.request
import uuid

from feedback_config import configuration, service_config
from feedback_checks import wait_for_login

HTTPS = Path('/etc/nginx/sites-available/birdynator-journal-https')
APP = Path('/opt/birdynator-journal-feedback')
CONFIG = Path('/etc/birdynator-journal-feedback')
AUTH = Path('/etc/nginx/journal-feedback.htpasswd')
RATE = Path('/etc/nginx/conf.d/birdynator-journal-feedback-rate.conf')
UNIT = Path('/etc/systemd/system/journal-feedback.service')
RECOVERY = Path('/var/lib/birdynator-journal-feedback-install')


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=40)
    if result.returncode:
        # Commands contain no password arguments; diagnostic output stays operator-only.
        print(result.stderr.strip(), flush=True)
        raise RuntimeError('Command failed: ' + args[0])
    return result.stdout


def write(path, data, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    os.fchmod(fd, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def atomic(path, data, mode):
    temporary = path.with_name(path.name + '.new-' + uuid.uuid4().hex)
    write(temporary, data, mode)
    temporary.replace(path)


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_resume(review):
    for path in (APP, APP / 'journal_feedback', CONFIG, AUTH, UNIT, RECOVERY,
                 RECOVERY / 'receipt.json', RECOVERY / 'https-before.conf'):
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
            raise ValueError('Recovery material is not root-controlled: ' + str(path))
    state = json.loads((RECOVERY / 'receipt.json').read_text())
    if (state.get('status') != 'failed_needs_inspection' or state.get('rollback_errors')
            or state.get('reviewer_id') != review['reviewer_id']
            or state.get('origin') != 'https://' + review['address']):
        raise ValueError('Receipt does not show a clean rolled-back matching attempt')
    if fingerprint(RECOVERY / 'https-before.conf') != review['previous_https_sha256']:
        raise ValueError('Recovery HTTPS backup differs from review')
    if os.path.lexists(RATE) or os.path.lexists(RECOVERY / 'initial-queue.sqlite'):
        raise ValueError('Unanticipated later installation phase requires inspection')
    if run('systemctl', 'show', 'journal-feedback.service', '--property=ActiveState', '--value').strip() != 'inactive':
        raise ValueError('Service is not stopped')
    if run('systemctl', 'show', 'journal-feedback.service', '--property=UnitFileState', '--value').strip() != 'disabled':
        raise ValueError('Service is unexpectedly enabled')
    for name in ('__init__.py', 'api.py', 'contract.py', 'outbox.py', 'server.py', 'queue_tools.py', 'journal-feedback.js'):
        path = APP / 'journal_feedback' / name
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022 or fingerprint(path) != review['files_sha256'][name]:
            raise ValueError('Installed application differs from review: ' + name)
    for path, name in ((UNIT, 'journal-feedback.service.example'), (APP / 'journal-review-sign-in.html', 'journal-review-sign-in.html')):
        if path.is_symlink() or fingerprint(path) != review['files_sha256'][name]:
            raise ValueError('Installed support file differs from review')
    expected = service_config(review['address'], review['reviewer_id'])
    if json.loads((CONFIG / 'service.json').read_text()) != expected:
        raise ValueError('Installed reviewer mapping differs')
    if not re.fullmatch(r'personal:\$6\$[A-Za-z0-9./]+\$[A-Za-z0-9./]+\n', AUTH.read_text()):
        raise ValueError('Existing personal password file has unexpected format')
    account = pwd.getpwnam('journal-feedback')
    queue = Path(expected['queue_path'])
    if queue.is_symlink() or queue.stat().st_uid != account.pw_uid or queue.stat().st_mode & 0o077:
        raise ValueError('Existing review queue is not privately owned by the service')
    if fingerprint(Path('/etc/nginx/sites-available/birdynator-journal')) != state['http_sha256']:
        raise ValueError('HTTP journal changed after failure')
    return state


def install(stage, resume=False):
    if stage.is_symlink():
        raise ValueError('Symlink staging refused')
    stage = stage.resolve()
    if (not re.fullmatch(r'/tmp/journal-feedback\.[A-Za-z0-9]{10}', str(stage))
            or stage.stat().st_uid != int(os.environ.get('SUDO_UID', '-1'))
            or stage.stat().st_mode & 0o077):
        raise ValueError('Expected private operator-owned staging directory')
    review = json.loads((stage / 'feedback-review.json').read_text(encoding='utf-8-sig'))
    required = {'install_feedback.py', 'feedback_config.py', 'feedback_checks.py', '__init__.py', 'api.py', 'contract.py',
                'outbox.py', 'server.py', 'queue_tools.py', 'journal-feedback.js',
                'journal-feedback.service.example', 'journal-review-sign-in.html', 'journal-authority.crt'}
    if (review['schema_version'] != 'journal-feedback-install-v1' or set(review['files_sha256']) != required
            or {p.name for p in stage.iterdir()} != required | {'feedback-review.json'}):
        raise ValueError('Unexpected feedback package')
    for name, expected in review['files_sha256'].items():
        if (stage / name).is_symlink() or fingerprint(stage / name) != expected:
            raise ValueError('Reviewed source changed: ' + name)
    recovered = validate_resume(review) if resume else None
    if not resume:
        for path in (APP, CONFIG, AUTH, RATE, UNIT, RECOVERY, Path('/var/lib/journal-feedback')):
            if os.path.lexists(path):
                raise ValueError('Existing feedback material needs inspection: ' + str(path))
    for parent in (APP.parent, CONFIG.parent, AUTH.parent, RATE.parent, UNIT.parent, RECOVERY.parent):
        if parent.is_symlink() or parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022:
            raise ValueError('System directory is not root-controlled')
    if HTTPS.is_symlink() or fingerprint(HTTPS) != review['previous_https_sha256']:
        raise ValueError('HTTPS configuration changed; inspect before installation')
    if not resume:
        try:
            pwd.getpwnam('journal-feedback')
        except KeyError:
            pass
        else:
            raise ValueError('Existing service account requires inspection')
    config = service_config(review['address'], review['reviewer_id'])
    previous = HTTPS.read_bytes()
    replacement = configuration(previous.decode(), review['address']).encode()
    http = Path('/etc/nginx/sites-available/birdynator-journal')
    http_hash = fingerprint(http)
    run('nginx', '-t')
    nginx_group = grp.getgrnam('www-data').gr_gid
    # Compile uploaded Python without writing caches or executing the service.
    for name in required:
        if name.endswith('.py'):
            compile((stage / name).read_bytes(), name, 'exec')
    print('Use the existing Journal login password for verification; it will not be reset.' if resume else
          'Create a separate personal Journal login in your password manager. Username: personal', flush=True)
    password = getpass.getpass('Journal login password (not the CA passphrase): ')
    confirmation = password if resume else getpass.getpass('Confirm Journal login password: ')
    if password != confirmation or not 16 <= len(password) <= 128 or any(not 32 <= ord(c) <= 126 for c in password):
        raise ValueError('Passwords must match and contain 16-128 printable ASCII characters')
    hashed = subprocess.run(['openssl', 'passwd', '-6', '-stdin'], input=password + '\n',
                            text=True, capture_output=True, timeout=10, check=True).stdout.strip()
    if not re.fullmatch(r'\$6\$[A-Za-z0-9./]+\$[A-Za-z0-9./]+', hashed):
        raise ValueError('Unexpected password hash output')
    context = ssl.create_default_context(cafile=str(stage / 'journal-authority.crt'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))

    def get(url, authenticated=False, expected=200, headers=None):
        supplied = dict(headers or {})
        if authenticated:
            supplied['Authorization'] = 'Basic ' + base64.b64encode(('personal:' + password).encode()).decode()
        try:
            with opener.open(urllib.request.Request(url, headers=supplied), timeout=15) as response:
                if response.status != expected:
                    raise ValueError('Unexpected verification response')
                return response.read(32768)
        except urllib.error.HTTPError as error:
            if error.code != expected:
                raise
            return error.read(32768)

    get(config['origin'] + '/')
    if not resume:
        RECOVERY.mkdir(mode=0o700)
        write(RECOVERY / 'https-before.conf', previous)
    else:
        write(RECOVERY / ('receipt-before-resume-' + uuid.uuid4().hex + '.json'),
              json.dumps(recovered, indent=2).encode())
    state = {'status': 'started', 'http_sha256': http_hash, 'reviewer_id': review['reviewer_id'],
             'stage': str(stage), 'origin': config['origin'], 'sql_import_enabled': False}
    def save():
        atomic(RECOVERY / 'receipt.json', json.dumps(state, indent=2).encode(), 0o600)
    save()
    try:
        if not resume:
            provision(stage, config, hashed, nginx_group)
        else:
            print('Guarded resume: existing account, password, reviewer identity and queue preserved.', flush=True)
        run('systemd-analyze', 'verify', str(UNIT))
        run('systemctl', 'daemon-reload')
        state['service_started'] = True
        save()
        run('systemctl', 'start', 'journal-feedback.service')
        for attempt in range(10):
            if Path(config['socket_path']).exists():
                break
            time.sleep(0.5)
        else:
            raise ValueError('Queue socket did not become ready')
        write(RATE, b'limit_req_zone $binary_remote_addr zone=journal_review_rate:1m rate=10r/m;\n', 0o644)
        state['rate_created'] = True
        state['https_modified'] = True
        save()
        atomic(HTTPS, replacement, 0o644)
        run('nginx', '-t')
        run('systemctl', 'reload', 'nginx')
        wait_for_login(lambda: get(config['origin'] + '/api/journal-feedback/context', expected=401))
        body = get(config['origin'] + '/api/journal-feedback/context', authenticated=True,
                   headers={'Remote-User': 'forged-reader'})
        if json.loads(body)['reviewer_id'] != review['reviewer_id']:
            raise ValueError('Authenticated reviewer mapping failed')
        get(config['origin'] + '/api/journal-feedback/sign-in.html', authenticated=True)
        get(config['origin'] + '/journal-feedback.js')
        get('http://' + review['address'] + ':8080/api/journal-feedback/context', expected=404)
        get('http://' + review['address'] + ':8080/')
        if fingerprint(http) != http_hash:
            raise ValueError('Plaintext HTTP configuration changed')
        backup = RECOVERY / 'initial-queue.sqlite'
        run('/usr/bin/python3', '-B', '-m', 'journal_feedback.queue_tools', '--config', str(CONFIG / 'service.json'), '--backup', str(backup))
        state['enable_attempted'] = True
        save()
        run('systemctl', 'enable', 'journal-feedback.service')
        state['status'] = 'verified'
        save()
        print('Personal HTTPS sign-in and private Utility queue verified.', flush=True)
        print('No SQL import or AI Nexus change. Re-publish a saved report with FeedbackEnabled to show its panel.')
    except Exception:
        errors = []
        if state.get('enable_attempted'):
            try: run('systemctl', 'disable', 'journal-feedback.service')
            except Exception as error: errors.append(str(error))
        if state.get('service_started'):
            try: run('systemctl', 'stop', 'journal-feedback.service')
            except Exception as error: errors.append(str(error))
        if state.get('https_modified'):
            try: atomic(HTTPS, previous, 0o644)
            except Exception as error: errors.append(str(error))
        if state.get('rate_created'):
            try: RATE.unlink()
            except Exception as error: errors.append(str(error))
        try:
            run('nginx', '-t')
            run('systemctl', 'reload', 'nginx')
        except Exception as error: errors.append(str(error))
        state.update(status='failed_needs_inspection', rollback_errors=errors)
        save()
        print('Stopped; credentials and state retained privately. Inspect: ' + str(RECOVERY))
        raise


def provision(stage, config, hashed, nginx_group):
    run('useradd', '--system', '--user-group', '--no-create-home', '--shell', '/usr/sbin/nologin', 'journal-feedback')
    APP.mkdir(mode=0o755)
    APP.chmod(0o755)
    package = APP / 'journal_feedback'
    package.mkdir(mode=0o755)
    package.chmod(0o755)
    for name in ('__init__.py', 'api.py', 'contract.py', 'outbox.py', 'server.py', 'queue_tools.py', 'journal-feedback.js'):
        write(package / name, (stage / name).read_bytes(), 0o644)
    write(APP / 'journal-review-sign-in.html', (stage / 'journal-review-sign-in.html').read_bytes(), 0o644)
    CONFIG.mkdir(mode=0o750)
    CONFIG.chmod(0o750)
    os.chown(CONFIG, 0, nginx_group)
    config_path = CONFIG / 'service.json'
    write(config_path, json.dumps(config).encode(), 0o640)
    os.chown(config_path, 0, nginx_group)
    write(AUTH, ('personal:' + hashed + '\n').encode(), 0o640)
    os.chown(AUTH, 0, nginx_group)
    write(UNIT, (stage / 'journal-feedback.service.example').read_bytes(), 0o644)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    approval = parser.add_mutually_exclusive_group(required=True)
    approval.add_argument('--install-approved', action='store_true')
    approval.add_argument('--resume-approved', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Sudo required; nothing changed')
    os.environ['PYTHONPATH'] = str(APP)
    install(Path(__file__).parent, resume=args.resume_approved)
