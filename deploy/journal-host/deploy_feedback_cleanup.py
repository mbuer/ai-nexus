"""Approved API/JS cleanup and existing-report publication; no Git/AI/migration."""
import argparse
import base64
from contextlib import closing
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import time
import urllib.error
import urllib.request
import uuid

from update_feedback_ui import atomic, run
from publish_utility import publish, verified_files

APP = Path('/opt/birdynator-journal-feedback/journal_feedback')
QUEUE = Path('/var/lib/journal-feedback/queue.sqlite')
CURRENT = Path('/srv/birdynator-journal/current')
RELEASES = Path('/srv/birdynator-journal/releases')
RECEIPT = Path('/var/lib/birdynator-journal-feedback-install/cleanup')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def connect_queue():
    return sqlite3.connect('file:' + str(QUEUE) + '?mode=ro', uri=True, timeout=15)


def queue_count():
    with closing(connect_queue()) as database:
        return database.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]


def deploy(stage):
    if stage.is_symlink():
        raise ValueError('Symlink staging refused')
    stage = stage.resolve()
    if (stage.parent != Path('/tmp') or not re.fullmatch(r'birdynator-upload\.[A-Za-z0-9]{10}', stage.name)
            or stage.stat().st_uid != int(os.environ.get('SUDO_UID', '-1')) or stage.stat().st_mode & 0o077):
        raise ValueError('Expected private operator staging')
    review = json.loads((stage / 'cleanup-review.json').read_text(encoding='utf-8-sig'))
    if review['schema_version'] != 'journal-feedback-cleanup-v1':
        raise ValueError('Unexpected review version')
    if {path.name for path in stage.iterdir()} != set(review['files_sha256']) | {'cleanup-review.json'}:
        raise ValueError('Unexpected upload contents')
    for name, expected in review['files_sha256'].items():
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or (stage / name).is_symlink() or sha(stage / name) != expected:
            raise ValueError('Reviewed package changed')
    for name in ('api.py', 'deploy_feedback_cleanup.py', 'update_feedback_ui.py', 'feedback_config.py', 'publish_utility.py'):
        compile((stage / name).read_bytes(), name, 'exec')
    verified_files(stage)
    if os.path.lexists(RECEIPT):
        raise ValueError('Existing cleanup receipt requires inspection; no repeat')
    for path in (APP, APP / 'api.py', APP / 'journal-feedback.js', RECEIPT.parent):
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
            raise ValueError('Installed source/recovery is not root-controlled')
    if (sha(APP / 'api.py') != review['previous_api_sha256']
            or sha(APP / 'journal-feedback.js') != review['previous_js_sha256']):
        raise ValueError('Installed code changed; inspect before updating')
    if not CURRENT.is_symlink() or CURRENT.resolve().parent != RELEASES.resolve():
        raise ValueError('Unexpected current release')
    previous_release = CURRENT.resolve()
    stem = '2026-10-12-23'
    if sha(CURRENT / (stem + '.json')) != sha(stage / (stem + '.json')):
        raise ValueError('Existing report identity/content differs from the saved local export')
    if run('systemctl', 'show', 'journal-feedback.service', '--property=ActiveState', '--value').strip() != 'active':
        raise ValueError('Feedback service is not currently active')
    config = json.loads(Path('/etc/birdynator-journal-feedback/service.json').read_text())
    if config['origin'] != review['origin']:
        raise ValueError('Feedback origin differs from review')
    configuration = [Path('/etc/nginx/sites-available/birdynator-journal'),
                     Path('/etc/nginx/sites-available/birdynator-journal-https'),
                     Path('/etc/nginx/journal-feedback.htpasswd'),
                     Path('/etc/birdynator-journal-feedback/service.json')]
    immutable = {str(path):sha(path) for path in configuration}
    password = getpass.getpass('Existing Journal Reviews password (verification only): ')
    context = ssl.create_default_context(cafile=str(stage / 'journal-authority.crt'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
    def get(route, authenticated=False):
        headers = {}
        if authenticated:
            headers['Authorization'] = 'Basic ' + base64.b64encode(('personal:' + password).encode()).decode()
        with opener.open(urllib.request.Request(config['origin'] + route, headers=headers), timeout=20) as response:
            if response.status != 200: raise ValueError('Unexpected verification response')
            data = response.read(4000001)
            if len(data) > 4000000: raise ValueError('Verification output exceeds limit')
            return data
    # Verify the existing credential before changing code, and keep it off disk.
    if json.loads(get('/api/journal-feedback/context', True))['reviewer_id'] != config['reviewers']['personal']:
        raise ValueError('Existing login verification failed')
    RECEIPT.mkdir(mode=0o700)
    old = {name:(APP / name).read_bytes() for name in ('api.py','journal-feedback.js')}
    for name, body in old.items(): atomic(RECEIPT / name, body, 0o600)
    with closing(connect_queue()) as source, closing(sqlite3.connect(RECEIPT / 'queue-before.sqlite')) as backup:
        (RECEIPT / 'queue-before.sqlite').chmod(0o600)
        source.backup(backup)
    count = queue_count()
    state = {'status':'prepared','previous_release':str(previous_release), 'reviews_before':count,
             'report_id':23,'stage':str(stage)}
    def save(): atomic(RECEIPT / 'receipt.json', json.dumps(state,indent=2).encode(), 0o600)
    save()
    try:
        for name in old: atomic(APP / name, (stage / name).read_bytes(), 0o644)
        run('systemctl', 'restart', 'journal-feedback.service')
        for attempt in range(10):
            if Path(config['socket_path']).exists(): break
            time.sleep(0.5)
        else: raise ValueError('Private socket did not recover')
        history = json.loads(get('/api/journal-feedback/history?analysis_id=23', True))
        if (history.get('schema_version') != 'journal-feedback-v1'
                or history.get('reviewer_id') != config['reviewers']['personal'] or not isinstance(history.get('reviews'),list)):
            raise ValueError('Optimized authenticated history API verification failed')
        if json.loads(get('/api/journal-feedback/session')) != {'signed_in':False}:
            raise ValueError('Anonymous status probe changed')
        try: get('/api/journal-feedback/context')
        except urllib.error.HTTPError as error:
            if error.code != 401: raise
        else: raise ValueError('Anonymous protected context must remain blocked')
        if queue_count() < count: raise ValueError('Review count decreased')
        if any(sha(Path(path)) != expected for path,expected in immutable.items()):
            raise ValueError('Configuration or credential changed')
        state['publication_attempted'] = True
        save()
        publish(str(stage))
        state['published_release'] = str(CURRENT.resolve())
        save()
        body = get('/' + stem + '.html').decode()
        if ('data-feedback-session' not in body or 'journal-feedback.js?v=3' not in body
                or 'padding:0 0 24px' not in body):
            raise ValueError('Published account strip/spacing/cache version mismatch')
        if sha(CURRENT / (stem + '.json')) != sha(stage / (stem + '.json')):
            raise ValueError('Structured provenance changed')
        state.update(status='verified',reviews_after=queue_count())
        save()
        print('Cleanup and symmetrical account spacing verified. Existing report23 updated; reviews retained.')
        print('No model request, AI deployment, SQL migration, credential reset or Git operation.')
    except Exception:
        errors=[]
        if state.get('publication_attempted') and CURRENT.resolve() != previous_release:
            try:
                target = state.get('published_release')
                if target is None or CURRENT.resolve() != Path(target):
                    raise ValueError('Publication target needs manual inspection; no blind symlink rollback')
                link = CURRENT.with_name('current-restore-' + uuid.uuid4().hex)
                link.symlink_to(previous_release)
                link.replace(CURRENT)
            except Exception as error: errors.append(str(error))
        for name,body in old.items():
            try: atomic(APP / name, body, 0o644)
            except Exception as error: errors.append(str(error))
        try: run('systemctl','restart','journal-feedback.service')
        except Exception as error: errors.append(str(error))
        state.update(status='failed_needs_inspection',rollback_errors=errors)
        save()
        print('Cleanup stopped. Queue/backup retained; inspect: ' + str(RECEIPT))
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deploy-approved',action='store_true')
    args=parser.parse_args()
    if not args.deploy_approved or os.geteuid()!=0: raise SystemExit('Explicit approval and sudo required')
    deploy(Path(__file__).parent)
