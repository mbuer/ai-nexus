"""One daily analysis through the existing isolated agent; no publishing or automatic retries."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

TODAY_RECORD = r'''
import json
import birdynator
with birdynator.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
        cursor.execute("SELECT id FROM analysis_runs WHERE analysis_type = %s "
                       "AND (created_at AT TIME ZONE %s)::date = %s::date "
                       "ORDER BY id DESC LIMIT 1",
                       ('birdnet_recent_vs_baseline', __TIMEZONE__, __DATE__))
        row = cursor.fetchone()
print(json.dumps({'id': row[0] if row else None}))
'''


def latest_today(day, timezone):
    query = TODAY_RECORD.replace('__TIMEZONE__', repr(timezone)).replace('__DATE__', repr(day))
    result = subprocess.run(['podman', 'exec', '-i', 'agent-birdynator', 'python', '-'],
                            input=query, stdout=subprocess.PIPE, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)['id']


def save_receipt(path, packet):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        os.chmod(temporary, 0o600)
        json.dump(packet, handle)
    temporary.replace(path)


def generate(config, state, now=None):
    timezone = config['timezone']
    zone = ZoneInfo(timezone)
    now = now or datetime.now(zone)
    day = now.astimezone(zone).date().isoformat()
    if day < config['not_before']:
        print('Daily generation starts ' + config['not_before'] + '; no report requested.')
        return 'not_started'
    existing = latest_today(day, timezone)
    receipt = state / (day + '.json')
    if existing:
        save_receipt(receipt, {'date': day, 'status': 'complete', 'analysis_id': existing})
        print('A saved report already exists today: ' + str(existing) + '. No new request.')
        return 'existing'
    if receipt.exists():
        print('An attempt is already recorded for today. Inspect logs; no automatic retry.')
        return 'already_attempted'
    packet = {'date': day, 'status': 'started', 'attempted_at': now.isoformat()}
    save_receipt(receipt, packet)
    command = ['podman', 'exec', 'agent-birdynator', 'python', '/app/birdynator.py',
               'analyze-birdnet', '--hours', '24', '--baseline-days', '30']
    if config.get('web_enrichment', True):
        command.append('--web-enrichment')
    try:
        subprocess.run(command, check=True)
        identifier = latest_today(day, timezone)
        if not identifier:
            raise RuntimeError('No completed saved report found after generation')
        packet.update(status='complete', analysis_id=identifier)
        save_receipt(receipt, packet)
        return 'complete'
    except BaseException:
        packet['status'] = 'needs_review'
        save_receipt(receipt, packet)
        raise


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path.home() / '.local/state/birdynator-journal/daily')
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Use the existing non-root operator account.')
    args.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = json.loads((args.state / 'config.json').read_text(encoding='utf-8'))
    datetime.fromisoformat(config['not_before'])
    if type(config.get('web_enrichment', True)) is not bool:
        raise ValueError('Invalid enrichment setting')
    with (args.state / 'generation.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Daily generation is already running; no second request.')
            return
        generate(config, args.state)


if __name__ == '__main__':
    main()
