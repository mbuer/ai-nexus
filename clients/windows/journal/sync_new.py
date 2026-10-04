"""Manually publish missing saved analyses. Never starts an analysis or model request."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'services/birdynator'))
from journal import export, rebuild_index, report_from_analysis
from prepare_upload import build

INVENTORY = r'''
import json, re
from pathlib import Path
root = Path('/srv/birdynator-journal/current')
ids = []
if root.exists():
    for path in root.glob('*.json'):
        if path.is_symlink() or not path.is_file():
            raise SystemExit('Unexpected archive file')
        if path.stat().st_size > 10000000:
            raise SystemExit('Archive record exceeds size limit')
        record = json.loads(path.read_text(encoding='utf-8'))
        identifier = record.get('provenance', {}).get('analysis_id')
        date = record.get('date')
        if (record.get('schema_version') != 'birdynator-journal-v1'
            or not isinstance(identifier, str) or not re.fullmatch(r'[1-9][0-9]*', identifier)
            or not isinstance(date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date)):
            raise SystemExit('Unexpected archive record')
        stem = date + '-' + identifier
        if path.stem != stem or any(not (root / (stem + ext)).is_file() for ext in ('.html', '.md')):
            raise SystemExit('Incomplete published report; repair with explicit AnalysisId')
        ids.append(int(identifier))
print(json.dumps({'version': 1, 'ids': ids}))
'''

FETCH = r'''
import json
import birdynator
known = __KNOWN_IDS__
with birdynator.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
        cursor.execute("SELECT id, model, source_latest_hour, source_digest, parameters, result_text "
                       "FROM analysis_runs WHERE analysis_type = %s AND NOT (id = ANY(%s)) "
                       "ORDER BY id LIMIT 250", ('birdnet_recent_vs_baseline', known))
        records = birdynator.rows_as_dicts(cursor)
print(json.dumps(records, default=str, ensure_ascii=True))
'''


def published_ids(packet):
    ids = packet.get('ids')
    if packet.get('version') != 1 or not isinstance(ids, list) or len(ids) > 10000:
        raise ValueError('Unexpected published inventory')
    if any(type(value) is not int or value <= 0 for value in ids) or len(ids) != len(set(ids)):
        raise ValueError('Invalid or duplicate published analysis IDs')
    return set(ids)


def validate_records(records, known):
    if not isinstance(records, list) or len(records) > 250:
        raise ValueError('Unexpected saved-analysis response')
    seen = set()
    for record in records:
        identifier = record.get('id')
        if type(identifier) is not int or identifier <= 0 or identifier in known or identifier in seen:
            raise ValueError('Unexpected saved analysis ID')
        if not isinstance(record.get('result_text'), str) or not record['result_text'].strip():
            raise ValueError('Saved analysis has no report')
        seen.add(identifier)
    return seen


def ssh_json(host, command, code):
    result = subprocess.run(['ssh', host, command], input=code, stdout=subprocess.PIPE,
                            text=True, encoding='utf-8', check=True)
    if len(result.stdout.encode('utf-8')) > 25000000:
        raise ValueError('Remote response exceeds transfer limit')
    return json.loads(result.stdout)


def sync(ai_host, utility_host, private):
    private = Path(private)
    private.mkdir(parents=True, exist_ok=True)
    print('Reading Utility archive IDs; no model request will be made.', flush=True)
    known = published_ids(ssh_json(utility_host, 'python3 -', INVENTORY))
    count = 0
    while True:
        code = FETCH.replace('__KNOWN_IDS__', json.dumps(sorted(known)))
        records = ssh_json(ai_host, 'podman exec -i agent-birdynator python -', code)
        added = validate_records(records, known)
        if not added:
            print(f'Up to date. Published {count} new saved reports.', flush=True)
            return count
        batch = private / ('sync-' + uuid.uuid4().hex)
        pages = batch / 'journal'
        pages.mkdir(parents=True)
        for record in records:
            (private / ('analysis-' + str(record['id']) + '.json')).write_text(
                json.dumps(record, ensure_ascii=False), encoding='utf-8')
            export(report_from_analysis(record), pages, update_index=False)
        rebuild_index(pages)
        manifest = batch / 'manifest.json'
        packet = build(pages)
        manifest.write_text(json.dumps(packet), encoding='utf-8')
        stage_result = subprocess.run(['ssh', utility_host, 'mktemp -d /tmp/birdynator-upload.XXXXXXXXXX'],
                                      stdout=subprocess.PIPE, text=True, encoding='utf-8', check=True)
        stage = stage_result.stdout.strip()
        if not re.fullmatch(r'/tmp/birdynator-upload\.[A-Za-z0-9]{10}', stage):
            raise ValueError('Unexpected remote staging path')
        # Relative page paths keep large batches below Windows' command-line limit.
        uploads = [item['name'] for item in packet['files']]
        uploads += [str(manifest), str(ROOT / 'deploy/journal-host/publish_utility.py')]
        subprocess.run(['scp', *uploads, utility_host + ':' + stage + '/'], cwd=pages, check=True)
        subprocess.run(['ssh', '-t', utility_host,
                        'sudo python3 ' + stage + '/publish_utility.py ' + stage], check=True)
        # Advance only after successful publication; a failed run is safe to rerun.
        known.update(added)
        count += len(added)
        if len(records) < 250:
            print(f'Up to date with the saved-analysis snapshot. Published {count} new saved reports.', flush=True)
            return count
        print(f'Published {count} new saved reports so far. Reading the next batch.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ai-host', required=True)
    parser.add_argument('--utility-host', required=True)
    parser.add_argument('--private', type=Path, required=True)
    args = parser.parse_args()
    for host in (args.ai_host, args.utility_host):
        if not re.fullmatch(r'[A-Za-z0-9_.@:-]+', host) or host.startswith('-'):
            raise ValueError('Invalid SSH host')
    sync(args.ai_host, args.utility_host, args.private)


if __name__ == '__main__':
    main()
