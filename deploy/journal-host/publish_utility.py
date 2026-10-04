"""Publish verified manual uploads to Utility. Run with sudo, not as a service."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid
from datetime import datetime

NAME = re.compile(r'(?:(?:index|\d{4}-\d{2}-\d{2}-[A-Za-z0-9_-]{1,80})\.(?:html|md|json)|birdynator-logo\.png)\Z')


def display_date(value):
    day = datetime.strptime(value, '%Y-%m-%d')
    return f'{day:%A}, {day:%B} {day.day}, {day.year}'


def verified_files(stage):
    manifest = stage / 'manifest.json'
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 1_000_000:
        raise ValueError('Invalid manifest file')
    packet = json.loads(manifest.read_text(encoding='utf-8'))
    files = packet.get('files')
    if packet.get('version') != 1 or not isinstance(files, list) or not 1 <= len(files) <= 1000:
        raise ValueError('Invalid upload manifest')
    names, total, result = set(), 0, []
    for item in files:
        name, size = item.get('name'), item.get('size')
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise ValueError('Unsafe or duplicate filename')
        names.add(name)
        if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= 10_000_000:
            raise ValueError('Invalid file size')
        total += size
        if total > 100_000_000:
            raise ValueError('Upload exceeds 100 MB')
        path = stage / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size != size:
            raise ValueError('Unexpected file type or size')
        if hashlib.sha256(path.read_bytes()).hexdigest() != item.get('sha256'):
            raise ValueError('Upload checksum mismatch')
        if name == 'birdynator-logo.png' and not path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Logo must be a PNG image')
        result.append(path)
    if 'index.html' not in names:
        raise ValueError('Missing archive index')
    return result


def allow_local_logo(base):
    """Permit same-origin static images only on the existing journal server."""
    configs = []
    for enabled in Path('/etc/nginx/sites-enabled').iterdir():
        if enabled.is_file():
            text = enabled.read_text()
            if 'root /srv/birdynator-journal/current;' in text and re.search(r'listen\s+[^;]*:8080\s*;', text):
                configs.append((enabled.resolve(), text))
    if len(configs) != 1:
        raise ValueError('Cannot uniquely identify journal nginx configuration; no publication performed')
    config, text = configs[0]
    policy = re.search(r'add_header\s+Content-Security-Policy\s+"([^"]+)"', text)
    if not policy:
        raise ValueError('Missing journal content security policy')
    if re.search(r'(?:^|;)\s*img-src\s', policy.group(1)):
        if not re.search(r"(?:^|;)\s*img-src\s+'self'\s*(?:;|$)", policy.group(1)):
            raise ValueError('Existing image policy needs review')
        return
    updated = text[:policy.start(1)] + "img-src 'self'; " + text[policy.start(1):]
    backup = base / ('nginx-before-logo-' + uuid.uuid4().hex + '.conf')
    backup.write_text(text)
    backup.chmod(0o600)
    config.write_text(updated)
    try:
        subprocess.run(['nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
    except Exception:
        config.write_text(text)
        subprocess.run(['nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        raise
    print('Journal images allowed from this server only. nginx backup: ' + str(backup))


def homepage_entries(entries):
    """Show the highest saved analysis ID per date; retain all archived files."""
    def order(entry):
        identifier = entry[1].rsplit('-', 1)[-1]
        return (entry[0], int(identifier) if identifier.isdigit() else -1, entry[1])
    visible, dates = [], set()
    for entry in sorted(entries, key=order, reverse=True):
        if entry[0] not in dates:
            visible.append(entry)
            dates.add(entry[0])
    return visible


def publish(stage):
    stage = Path(stage)
    if (stage.parent != Path('/tmp') or not re.fullmatch(r'birdynator-upload\.[A-Za-z0-9]{10}', stage.name)
            or stage.is_symlink() or stage.resolve() != stage):
        raise ValueError('Unexpected staging directory')
    info = stage.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != int(os.environ['SUDO_UID']) or info.st_mode & 0o077:
        raise ValueError('Staging directory ownership or permissions are unsafe')
    files = verified_files(stage)
    base = Path('/srv/birdynator-journal')
    if base.is_symlink():
        raise ValueError('Unexpected journal root symlink')
    base.mkdir(exist_ok=True)
    releases = base / 'releases'
    if releases.is_symlink():
        raise ValueError('Unexpected releases symlink')
    releases.mkdir(exist_ok=True)
    current = base / 'current'
    if current.is_symlink() and current.resolve().parent != releases.resolve():
        raise ValueError('Current release escapes the journal directory')
    release = releases / ('manual-' + uuid.uuid4().hex)
    release.mkdir(mode=0o755)
    # Merge existing history; publishing one old run must not erase newer runs.
    if current.exists():
        for previous in current.iterdir():
            if previous.is_symlink() or not previous.is_file() or not NAME.fullmatch(previous.name):
                raise ValueError('Unexpected file in current journal')
            shutil.copyfile(previous, release / previous.name)
    for path in files:
        shutil.copyfile(path, release / path.name)
    # Rebuild the archive from the union of all published reports, with escaped titles.
    import html
    entries = []
    for path in release.glob('*.json'):
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved.get('schema_version') != 'birdynator-journal-v1':
            raise ValueError('Unexpected published report schema')
        date, title = saved['date'], saved['headline']
        if not isinstance(title, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
            raise ValueError('Invalid archive entry')
        expected = date + '-' + saved['provenance']['analysis_id']
        if path.stem != expected or not (release / (expected + '.html')).is_file():
            raise ValueError('Missing report HTML')
        entries.append((date, expected, title))
    entries.sort(reverse=True)
    # Keep the locally rendered index's styling and replace only its article list.
    index = (release / 'index.html').read_text(encoding='utf-8')
    if '<article class="entry">' not in index:
        raise ValueError('Unexpected journal index structure')
    links = ''.join(f'<article class="entry"><p class="date">{display_date(date)}</p><h2><a href="{stem}.html">{html.escape(title)}</a></h2><a href="{stem}.md">Markdown</a> · <a href="{stem}.json">Structured report</a></article>' for date, stem, title in homepage_entries(entries))
    index = re.sub(r'<article class="entry">.*?</article>', '', index, flags=re.S)
    index = index.replace('</main>', links + '</main>')
    (release / 'index.html').write_text(index, encoding='utf-8')
    (release / 'index.md').write_text('# Birdynator Journal\n\n' + '\n'.join(f'- [{display_date(date)} — {title}]({stem}.md)' for date, stem, title in entries), encoding='utf-8')
    for path in release.iterdir():
        path.chmod(0o644)
    if (release / 'birdynator-logo.png').exists():
        allow_local_logo(base)
    temporary_link = base / ('current-new-' + uuid.uuid4().hex)
    temporary_link.symlink_to(release)
    backup = None
    if current.exists() and not current.is_symlink():
        backup = base / ('initial-site-' + uuid.uuid4().hex)
        current.rename(backup)
    try:
        os.replace(temporary_link, current)
    except Exception:
        if backup:
            backup.rename(current)
        raise
    print('Published completed release: ' + release.name)
    print('Previous releases retained. Upload staging: ' + str(stage))


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Run this publisher with sudo')
    publish(sys.argv[1])
