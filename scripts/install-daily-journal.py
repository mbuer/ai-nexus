"""Install the user's daily generation timer. Starts tomorrow, never runs a report at installation."""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--time', default='21:00')
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Use the existing non-root operator account.')
    if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', args.time):
        raise ValueError('Use HH:MM for the daily Pacific time.')
    linger = subprocess.check_output(['loginctl', 'show-user', str(os.getuid()), '-p', 'Linger', '--value']).decode().strip()
    if linger != 'yes':
        raise SystemExit('User lingering is not enabled. Review the existing rootless runtime before installing the schedule.')
    root = Path(__file__).resolve().parents[1]
    home = Path.home()
    units = home / '.config/systemd/user'
    library = home / '.local/libexec/ai-nexus'
    state = home / '.local/state/birdynator-journal/daily'
    for directory in (units, library, state):
        if directory.is_symlink():
            raise ValueError('Unexpected installation directory symlink')
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    config_path = state / 'config.json'
    installed_path = state / 'installed-files.json'
    if installed_path.is_symlink():
        raise ValueError('Unexpected installation receipt symlink')
    installed = json.loads(installed_path.read_text()) if installed_path.exists() else {}
    timer = (root / 'containers/ai-nexus-daily-journal.timer.in').read_text(encoding='utf-8').replace('@DAILY_TIME@', args.time)
    files = {
        library / 'daily-journal.py': (root / 'scripts/daily-journal.py').read_bytes(),
        units / 'ai-nexus-daily-journal.service': (root / 'containers/ai-nexus-daily-journal.service').read_bytes(),
        units / 'ai-nexus-daily-journal.timer': timer.encode(),
    }
    for path, data in files.items():
        if path.is_symlink():
            raise ValueError('Unexpected installed file symlink')
        if path.exists():
            current = hashlib.sha256(path.read_bytes()).hexdigest()
            if current != installed.get(str(path)) and path.read_bytes() != data:
                raise ValueError('Unrecognized existing scheduled file; review before replacing: ' + str(path))
    if config_path.exists():
        if config_path.is_symlink():
            raise ValueError('Unexpected configuration symlink')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if config.get('timezone') != 'America/Los_Angeles':
            raise ValueError('Existing schedule timezone needs review')
    else:
        tomorrow = datetime.now(ZoneInfo('America/Los_Angeles')).date() + timedelta(days=1)
        config = {'timezone': 'America/Los_Angeles', 'not_before': tomorrow.isoformat(), 'web_enrichment': True}
    config['time'] = args.time
    recovery = state / ('installation-before-' + uuid.uuid4().hex)
    recovery.mkdir(mode=0o700)
    for path in [*files, config_path, installed_path]:
        if path.exists():
            shutil.copy2(path, recovery / path.name)
    for path, data in files.items():
        path.write_bytes(data)
        path.chmod(0o600)
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    config_path.chmod(0o600)
    installed_path.write_text(json.dumps({str(path): hashlib.sha256(data).hexdigest() for path, data in files.items()}, indent=2))
    installed_path.chmod(0o600)
    subprocess.run(['systemd-analyze', 'calendar', '*-*-* ' + args.time + ':00 America/Los_Angeles'], check=True)
    # Quadlet services exist through a user generator, not ordinary unit files.
    subprocess.run(['systemd-analyze', '--user', '--generators', 'verify', str(units / 'ai-nexus-daily-journal.service'), str(units / 'ai-nexus-daily-journal.timer')], check=True)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', 'ai-nexus-daily-journal.timer'], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'ai-nexus-daily-journal.timer'], check=True)
    subprocess.run(['systemctl', '--user', 'list-timers', 'ai-nexus-daily-journal.timer', '--no-pager'], check=True)
    print('Generation schedule: ' + args.time + ' America/Los_Angeles. Starts no earlier than ' + config['not_before'] + '.')
    print('No report was requested by installation. Publication remains manually triggered from Windows.')
    print('Installation recovery: ' + str(recovery))


if __name__ == '__main__':
    main()
