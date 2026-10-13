"""Approved sign-in status UI delta; no credential, queue or service restart."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import time
import urllib.error
import urllib.request
import uuid

from feedback_config import session_configuration

HTTPS = Path('/etc/nginx/sites-available/birdynator-journal-https')
RATE = Path('/etc/nginx/conf.d/birdynator-journal-feedback-rate.conf')
SCRIPT = Path('/opt/birdynator-journal-feedback/journal_feedback/journal-feedback.js')
BASE_RATE = b'limit_req_zone $binary_remote_addr zone=journal_review_rate:1m rate=10r/m;\n'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, body, mode):
    temporary = path.with_name(path.name + '.new-' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    os.fchmod(fd, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def run(*command):
    import subprocess
    return subprocess.run(command, capture_output=True, text=True, check=True, timeout=30).stdout


def update(stage):
    if stage.is_symlink():
        raise ValueError('Symlink staging refused')
    stage = stage.resolve()
    if (not re.fullmatch(r'/tmp/journal-ui\.[A-Za-z0-9]{10}', str(stage))
            or stage.stat().st_uid != int(os.environ.get('SUDO_UID', '-1')) or stage.stat().st_mode & 0o077):
        raise ValueError('Expected private operator staging')
    review = json.loads((stage / 'ui-review.json').read_text(encoding='utf-8-sig'))
    names = {'update_feedback_ui.py', 'feedback_config.py', 'journal-feedback.js', 'journal-authority.crt'}
    if (review['schema_version'] != 'journal-feedback-ui-v2' or set(review['files_sha256']) != names
            or {p.name for p in stage.iterdir()} != names | {'ui-review.json'}):
        raise ValueError('Unexpected UI update package')
    for name in names:
        if (stage / name).is_symlink() or digest(stage / name) != review['files_sha256'][name]:
            raise ValueError('Reviewed UI update changed')
    for path in (HTTPS, RATE, SCRIPT, HTTPS.parent, RATE.parent, SCRIPT.parent):
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
            raise ValueError('Installed UI/config is not root-controlled')
    if digest(HTTPS) != review['previous_https_sha256'] or digest(SCRIPT) != review['previous_script_sha256'] or RATE.read_bytes() != BASE_RATE:
        raise ValueError('Live feedback configuration/assets changed; inspect first')
    old = {path: path.read_bytes() for path in (HTTPS, RATE, SCRIPT)}
    new_config = session_configuration(old[HTTPS].decode()).encode()
    config = json.loads(Path('/etc/birdynator-journal-feedback/service.json').read_text())
    if config['origin'] != review['origin']:
        raise ValueError('Origin differs from reviewed service')
    context = ssl.create_default_context(cafile=str(stage / 'journal-authority.crt'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
    receipt_root = Path('/var/lib/birdynator-journal-feedback-install')
    if receipt_root.is_symlink() or receipt_root.stat().st_uid != 0 or receipt_root.stat().st_mode & 0o077:
        raise ValueError('Recovery directory is not private')
    receipt = receipt_root / ('ui-' + uuid.uuid4().hex)
    receipt.mkdir(mode=0o700)
    for path, content in old.items():
        atomic(receipt / path.name, content, 0o600)
    state = {'status':'prepared', 'stage':str(stage)}
    def save():
        atomic(receipt / 'receipt.json', json.dumps(state).encode(), 0o600)
    save()
    try:
        atomic(HTTPS, new_config, 0o644)
        atomic(RATE, BASE_RATE + b'limit_req_zone $binary_remote_addr zone=journal_session_rate:1m rate=30r/m;\n', 0o644)
        atomic(SCRIPT, (stage / 'journal-feedback.js').read_bytes(), 0o644)
        run('nginx', '-t')
        run('systemctl', 'reload', 'nginx')
        for attempt in range(10):
            try:
                with opener.open(config['origin'] + '/api/journal-feedback/session', timeout=10) as response:
                    if response.status != 200 or json.loads(response.read()) != {'signed_in':False}:
                        raise ValueError('Anonymous session probe must report signed out')
                break
            except urllib.error.HTTPError as error:
                if error.code not in (401,404) or attempt == 9:
                    raise
                time.sleep(0.5)
        # Anonymous history/saving still require login. Probe cannot acknowledge.
        for route in ('context', 'history?analysis_id=23'):
            try:
                opener.open(config['origin'] + '/api/journal-feedback/' + route, timeout=10)
            except urllib.error.HTTPError as error:
                if error.code != 401: raise
            else:
                raise ValueError('Protected feedback route became anonymous')
        try:
            opener.open(urllib.request.Request(config['origin'] + '/api/journal-feedback/reviews',
                        data=b'{}', headers={'Content-Type':'application/json'}), timeout=10)
        except urllib.error.HTTPError as error:
            if error.code != 401: raise
        else:
            raise ValueError('Anonymous saving must remain blocked')
        state['status'] = 'verified'
        save()
        print('Sign-in status endpoint and updated JS verified. Re-publish report 23 to move its account strip outside the fold.')
        print('Password, reviewer identity, queue, service and AI Nexus unchanged.')
    except Exception:
        errors = []
        for path, content in old.items():
            try: atomic(path, content, 0o644)
            except Exception as error: errors.append(str(error))
        try:
            run('nginx', '-t')
            run('systemctl', 'reload', 'nginx')
        except Exception as error: errors.append(str(error))
        state.update(status='failed_needs_inspection', rollback_errors=errors)
        save()
        print('UI update stopped. Inspect recovery: ' + str(receipt))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-approved', action='store_true')
    args = parser.parse_args()
    if not args.update_approved or os.geteuid() != 0:
        raise SystemExit('Explicit approval and sudo required')
    update(Path(__file__).parent)
