"""Configure a future seven-day candidate on the existing worker; never start a job."""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
from zoneinfo import ZoneInfo

PROMPT = 'birdynator-narrative-v3.2-trial'


def configure(state, worker, source, start=None, disable=False, today=None):
    """Called under the existing generation lock. Recovery copies precede any write."""
    config_path, installed_path = state / 'config.json', state / 'installed-files.json'
    for path in (state, worker, config_path, installed_path):
        if path.is_symlink():
            raise ValueError('Unexpected installed symlink')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    installed = json.loads(installed_path.read_text(encoding='utf-8'))
    if config.get('timezone') != 'America/Los_Angeles':
        raise ValueError('Existing schedule timezone needs review')
    if hashlib.sha256(worker.read_bytes()).hexdigest() != installed.get(str(worker)):
        raise ValueError('Unrecognized installed worker; inspect before updating')
    if disable:
        config.pop('journal_trial', None)
    else:
        today = today or datetime.now(ZoneInfo(config['timezone'])).date()
        first = datetime.strptime(start, '%Y-%m-%d').date()
        if first <= today:
            raise ValueError('Trial must start on a future Pacific date')
        config['journal_trial'] = {'start': first.isoformat(), 'end': (first + timedelta(days=6)).isoformat(),
                                   'prompt_version': PROMPT}
        # Ensure the container was explicitly updated before enabling its worker flag.
        result = subprocess.run(['podman', 'exec', 'agent-birdynator', 'python', '-c',
                                 'import journal_trial; print(journal_trial.PROMPT_VERSION)'],
                                check=True, stdout=subprocess.PIPE, text=True)
        if result.stdout.strip() != PROMPT:
            raise ValueError('Container candidate version differs; trial not enabled')
    recovery = state / ('trial-before-' + uuid.uuid4().hex)
    recovery.mkdir(mode=0o700)
    for path in (worker, config_path, installed_path):
        shutil.copy2(path, recovery / path.name)
    def write(path, data):
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(data)
        temporary.chmod(0o600)
        temporary.replace(path)
    if not disable:
        data = source.read_bytes()
        write(worker, data)
        installed[str(worker)] = hashlib.sha256(data).hexdigest()
        write(installed_path, json.dumps(installed, indent=2).encode())
    write(config_path, json.dumps(config, indent=2).encode())
    return recovery


def main():
    import fcntl
    if os.geteuid() == 0:
        raise SystemExit('Use the existing non-root operator account.')
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--start', help='future Pacific YYYY-MM-DD; end is six days later')
    group.add_argument('--disable', action='store_true', help='return future generation to the accepted baseline')
    args = parser.parse_args()
    state = Path.home() / '.local/state/birdynator-journal/daily'
    worker = Path.home() / '.local/libexec/ai-nexus/daily-journal.py'
    source = Path(__file__).with_name('daily-journal.py')
    with (state / 'generation.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Generation is running; configure later without interrupting it.')
        recovery = configure(state, worker, source, args.start, args.disable)
    print('Future trial policy updated. No service/timer restart, model call or publication.')
    print('Recovery copies: ' + str(recovery))


if __name__ == '__main__':
    main()
