"""Operator-only queue export/receipt/consistent backup; never a browser endpoint."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from contextlib import closing

from .outbox import Queue


def private_directory(path):
    if path.is_symlink() or not path.is_dir() or path.stat().st_mode & 0o077:
        raise ValueError('Backup directory must be private')


def backup(queue, destination, guard=private_directory):
    destination = Path(destination)
    if (destination.is_symlink() or destination.exists() or destination.parent.is_symlink()
            or not destination.parent.is_dir()):
        raise ValueError('Backup needs a new file in a private directory')
    guard(destination.parent)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    # SQLite backup API takes a consistent snapshot while saving can continue.
    with queue.connect() as source:
        with closing(sqlite3.connect(destination)) as target:
            source.backup(target)
    destination.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    operations = parser.add_mutually_exclusive_group(required=True)
    operations.add_argument('--pending', action='store_true')
    operations.add_argument('--acknowledge-reviewed', action='store_true')
    operations.add_argument('--backup', type=Path)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    path = Path(config['queue_path'])
    if not path.is_file() or path.is_symlink():
        raise ValueError('Existing queue required; nothing created')
    queue = Queue(path)
    if args.pending:
        print(json.dumps(queue.pending(), ensure_ascii=True))
    elif args.acknowledge_reviewed:
        data = sys.stdin.buffer.read(16001)
        if len(data) > 16000:
            raise ValueError('Receipt exceeds limit')
        print(queue.acknowledge(json.loads(data)))
    else:
        backup(queue, args.backup)
        print('Consistent private queue backup completed.')


if __name__ == '__main__':
    main()
