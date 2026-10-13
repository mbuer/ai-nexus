"""Explicit human-feedback import. Prints confirmed receipts; never acknowledges Utility."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from journal_feedback.importer import import_batch, validate_batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch', type=Path, help='private bounded queue export')
    parser.add_argument('--import-reviewed', action='store_true', help='explicitly perform the approved database import')
    args = parser.parse_args()
    if args.batch.is_symlink() or not args.batch.is_file() or args.batch.stat().st_size > 4000000:
        raise ValueError('Invalid feedback import file')
    items = json.loads(args.batch.read_text(encoding='utf-8'))
    validate_batch(items)
    if not args.import_reviewed:
        print('Validated ' + str(len(items)) + ' queued reviews. No database operation performed.')
        return
    for receipt in import_batch(items):
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
