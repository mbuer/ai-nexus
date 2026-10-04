"""Build a bounded upload manifest from the locally rendered journal."""
import hashlib
import json
from pathlib import Path
import re
import sys

NAME = re.compile(r'(?:(?:index|\d{4}-\d{2}-\d{2}-[A-Za-z0-9_-]{1,80})\.(?:html|md|json)|birdynator-logo\.png)\Z')


def build(directory):
    directory = Path(directory)
    files = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file() or not NAME.fullmatch(path.name):
            raise ValueError('Unexpected file in the journal directory')
        content = path.read_bytes()
        if path.name == 'birdynator-logo.png' and not content.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Logo must be a PNG image')
        if len(content) > 10_000_000:
            raise ValueError('Journal file exceeds 10 MB')
        files.append({'name': path.name, 'size': len(content),
                      'sha256': hashlib.sha256(content).hexdigest()})
    if not files or len(files) > 1000 or sum(f['size'] for f in files) > 100_000_000:
        raise ValueError('Journal archive exceeds transfer bounds')
    if 'index.html' not in {f['name'] for f in files}:
        raise ValueError('Missing archive index')
    return {'version': 1, 'files': files}


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(json.dumps(build(sys.argv[1])), encoding='utf-8')
