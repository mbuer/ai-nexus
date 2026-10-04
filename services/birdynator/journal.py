"""Offline, deterministic Journal v1 exports. No network or database dependencies."""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from enrichment import allowed_url

VERSION = 'birdynator-journal-v1'
SECTION_NAMES = {
    "today's story": 'todays_story', 'what caught my eye': 'findings',
    'something to watch': 'watching', 'birdynator is watching': 'watching',
    'model surprise': 'model_surprise', 'bird to explore': 'bird_to_explore',
}
LABELS = {'todays_story': "Today's story", 'findings': 'What caught my eye',
          'watching': 'Birdynator is watching', 'model_surprise': 'Model surprise',
          'bird_to_explore': 'Bird to explore'}
CSS = """
:root{color-scheme:light dark;--bg:#f5f3ec;--paper:#fffef9;--ink:#253c33;--muted:#52635a;--line:#d4dacf;--accent:#35664b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.7 system-ui,sans-serif}
main{max-width:940px;margin:auto;padding:40px 24px 64px}a{color:var(--accent);text-underline-offset:4px}
a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:5px}
.brand,.eyebrow{font-size:12px;letter-spacing:.15em;text-transform:uppercase;font-weight:700;color:var(--muted)}
header{padding:30px 0 24px;border-bottom:1px solid var(--line);margin-bottom:28px}
h1,h2{font-family:Georgia,serif;line-height:1.15;font-weight:400}h1{font-size:clamp(36px,6vw,62px);max-width:780px;margin:14px 0 22px}h2{font-size:29px;margin:0 0 18px}
p{margin:0 0 18px;overflow-wrap:anywhere}.date,.note{color:var(--muted);font-size:14px}
.metrics{display:flex;gap:12px;flex-wrap:wrap;margin:26px 0 0}.metric{padding:14px 20px;border:1px solid var(--line);border-radius:14px;background:var(--paper)}
.metric strong{display:block;font:32px Georgia,serif}.metric span{font-size:13px;color:var(--muted)}
.grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(0,1fr);gap:20px;align-items:start}
.card{background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:28px;margin-bottom:20px}
.story p{font:20px/1.8 Georgia,serif}.tag{display:block;color:var(--muted);font-size:12px;font-weight:650;margin-bottom:12px}
figure{margin:0}svg{width:100%;height:auto;color:var(--accent)}svg text{fill:var(--ink);font:13px system-ui,sans-serif}
figcaption{font-size:13px;color:var(--muted);margin-top:10px}details{margin-top:24px;padding:18px;border-top:1px solid var(--line)}summary{cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 monospace}footer{margin-top:30px;color:var(--muted);font-size:13px}.entry{display:block;padding:22px 0;border-bottom:1px solid var(--line)}
@media(max-width:650px){main{padding:20px 18px 40px}.grid{display:block}.card{padding:23px}.story p{font-size:19px}}
@media(prefers-color-scheme:dark){:root{--bg:#18251f;--paper:#22332a;--ink:#f0f1e6;--muted:#bccbbf;--line:#485e50;--accent:#b4d9b9}}
"""
ARCHIVE_CSS = """
.archive-header{display:grid;grid-template-columns:170px 1fr;gap:30px;align-items:center;padding:22px 0 34px}
.archive-header.no-logo{grid-template-columns:1fr}
.logo-frame{background:transparent;aspect-ratio:1}
.logo-frame img{display:block;width:100%;height:100%;object-fit:contain}
.archive-header .brand{color:var(--accent)}.archive-header h1{font-size:clamp(34px,5vw,54px);margin:12px 0 16px;max-width:600px}
.archive-header p{margin:0;color:var(--muted)}.archive .entry{padding:24px 26px;margin:0 0 16px;border:1px solid var(--line);border-radius:18px;background:var(--paper)}
.archive .entry h2{font-size:27px;margin:8px 0 16px}.archive .entry h2 a{text-decoration:none;color:var(--ink)}.archive .entry h2 a:hover{text-decoration:underline}
@media(max-width:650px){.archive-header{grid-template-columns:104px 1fr;gap:18px;align-items:start}.logo-frame{border-radius:20px}.archive-header h1{font-size:32px}.archive-header .brand{font-size:10px;letter-spacing:.12em}.archive .entry{padding:22px}.archive .entry h2{font-size:25px}}
@media(max-width:420px){.archive-header{grid-template-columns:1fr}.logo-frame{width:110px}.archive-header h1{max-width:320px}}
"""


def digest(evidence):
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def split_sections(text):
    """Recognize only known whole-line headings; retain unrecognized legacy text."""
    sections = {key: [] for key in LABELS}
    current = 'todays_story'
    for line in text.splitlines():
        cleaned = re.sub(r'^[^A-Za-z]+', '', line).strip().rstrip(':').strip('* ').lower()
        cleaned = cleaned.replace('\u2019', "'").replace('\u2018', "'")
        if cleaned in SECTION_NAMES:
            current = SECTION_NAMES[cleaned]
        else:
            sections[current].append(line)
    return {key: '\n'.join(lines).strip() for key, lines in sections.items()}


def report_from_analysis(record, evidence=None, headline=None):
    """Preserve prose as interpretation; never relabel generated claims as facts."""
    parameters = record.get('parameters') or {}
    if isinstance(parameters, str):
        parameters = json.loads(parameters)
    if evidence is None:
        saved = parameters.get('journal_report')
        evidence = saved.get('evidence') if isinstance(saved, dict) else None
    expected = record.get('source_digest')
    if evidence is not None and (not expected or digest(evidence) != expected):
        raise ValueError('Evidence digest does not match the saved analysis')
    if evidence is not None and str(record['source_latest_hour']).replace(' ', 'T') != evidence['window']['latest_hour']:
        raise ValueError('Evidence cutoff does not match the analysis')
    date = str(record['source_latest_hour'])[:10]
    datetime.strptime(date, '%Y-%m-%d')
    sections = split_sections(record['result_text'])
    story = sections.pop('todays_story')
    # New prompt emits a headline on its own line before the story heading.
    first, _, rest = story.partition('\n')
    if first.startswith('# ') and rest.strip():
        headline = headline or first[2:].strip()
        story = rest.strip()
    signals = evidence.get('interesting_signals', {}) if evidence else {}
    today = signals.get('observations', {}).get('today') or {}
    metrics = []
    for metric, label in [('distinct_species', 'species recorded'), ('activity_index', 'activity index')]:
        value = today.get(metric, {}).get('value')
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            metrics.append({'label': label, 'value': value, 'kind': 'observation'})
    finding_parts = [text.strip() for text in re.split(r'\n\s*\n', sections['findings']) if text.strip()]
    if len(finding_parts) > 2:
        finding_parts = [finding_parts[0], '\n\n'.join(finding_parts[1:])]
    return validate({
        'schema_version': VERSION, 'date': date,
        'headline': headline or 'A day in the backyard',
        'summary_metrics': metrics, 'todays_story': story,
        'findings': [{'text': text, 'kind': 'interpretation'} for text in finding_parts],
        'watching': {'text': sections['watching'], 'kind': 'hypothesis'} if sections['watching'] else None,
        'model_surprise': {'text': sections['model_surprise'], 'kind': 'prediction_interpretation'} if sections['model_surprise'] else None,
        'bird_to_explore': {'text': sections['bird_to_explore'], 'kind': 'interpretation'} if sections['bird_to_explore'] else None,
        'charts': ['diversity'] if evidence and re.search(r'\b(species|diversity|variety)\b', story, re.I) else [],
        'evidence': evidence,
        'provenance': {'analysis_id': str(record['id']), 'model': record.get('model'),
                       'source_digest': expected, 'source_latest_hour': str(record['source_latest_hour']),
                       'prompt_version': parameters.get('prompt_version'),
                       'origin': record.get('origin', 'saved analysis; generated interpretation'),
                       'external_context': parameters.get('external_context', {'status': 'disabled'})},
    })


def validate(report):
    if not isinstance(report, dict) or report.get('schema_version') != VERSION:
        raise ValueError('Unsupported journal schema')
    for key in ('headline', 'date', 'todays_story'):
        if not isinstance(report.get(key), str) or not report[key].strip():
            raise ValueError(f'Missing {key}')
    datetime.strptime(report['date'], '%Y-%m-%d')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', report['provenance']['analysis_id']):
        raise ValueError('Unsafe analysis ID')
    if not isinstance(report.get('summary_metrics'), list) or len(report['summary_metrics']) > 3:
        raise ValueError('Expected at most three metrics')
    if not isinstance(report.get('findings'), list) or len(report['findings']) > 2:
        raise ValueError('Expected at most two findings')
    for item in report['findings'] + [report[k] for k in ('watching', 'model_surprise', 'bird_to_explore') if report.get(k)]:
        if not isinstance(item, dict) or not isinstance(item.get('text'), str):
            raise ValueError('Invalid narrative section')
    for key, kind in [('watching', 'hypothesis'), ('model_surprise', 'prediction_interpretation'), ('bird_to_explore', 'interpretation')]:
        if report.get(key) and report[key].get('kind') != kind:
            raise ValueError('Incorrect section evidence type')
    if any(item.get('kind') != 'interpretation' for item in report['findings']):
        raise ValueError('Findings must remain interpretation')
    if report.get('charts', []) not in ([], ['diversity']):
        raise ValueError('Unsupported chart selection')
    evidence = report.get('evidence')
    if evidence is not None and digest(evidence) != report['provenance'].get('source_digest'):
        raise ValueError('Evidence digest mismatch')
    # Display metrics are always re-derived from verified evidence, not trusted JSON.
    for item in report['summary_metrics']:
        metric = {'species recorded': 'distinct_species', 'activity index': 'activity_index'}.get(item.get('label'))
        if not metric or evidence is None:
            raise ValueError('Metric has no verified evidence')
        value = evidence['interesting_signals']['observations']['today'][metric]['value']
        if isinstance(item.get('value'), bool) or item.get('value') != value:
            raise ValueError('Metric differs from evidence')
    return report


def source_titles(report):
    context = report['provenance'].get('external_context') or {}
    titles = {}
    for source in context.get('cited_sources', []):
        url, title = source.get('url'), source.get('title')
        if allowed_url(url) and isinstance(title, str) and title.strip():
            title = ' '.join(title.split())[:300]
            titles[url] = title
            titles[urlsplit(url)._replace(query='', fragment='').geturl().rstrip('/')] = title
    return titles


def inline(text, titles=None):
    """Escape all HTML; only a small safe subset of Markdown is rendered."""
    pieces = []
    cursor = 0
    for match in re.finditer(r'\[([^\]\n]+)\]\(([^\s)]+)\)', text):
        pieces.append(html.escape(text[cursor:match.start()]))
        label, url = match.groups()
        if allowed_url(url):
            if label.strip().isdigit():
                parsed = urlsplit(url)
                key = parsed._replace(query='', fragment='').geturl().rstrip('/')
                host = parsed.hostname or ''
                fallback = ('Cornell All About Birds' if host == 'allaboutbirds.org' or host.endswith('.allaboutbirds.org')
                            else 'eBird' if host == 'ebird.org' or host.endswith('.ebird.org') else 'Wikipedia')
                label = (titles or {}).get(url) or (titles or {}).get(key) or fallback
            pieces.append(f'<a href="{html.escape(url, quote=True)}" rel="noreferrer">{html.escape(label)}</a>')
        else:
            pieces.append(html.escape(match.group(0)))
        cursor = match.end()
    pieces.append(html.escape(text[cursor:]))
    return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', ''.join(pieces))


def paragraphs(text, titles=None):
    return ''.join('<p>' + inline(p.strip(), titles).replace('\n', '<br>') + '</p>'
                   for p in re.split(r'\n\s*\n', text) if p.strip())


def chart(report):
    evidence = report.get('evidence')
    if not evidence or 'diversity' not in report.get('charts', []):
        return ''
    rows = evidence.get('daily_evidence', [])[-14:]
    points = [(r['date'], r.get('distinct_species')) for r in rows]
    if len(points) < 2 or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                              or not math.isfinite(v) or v < 0 for _, v in points):
        return ''
    maximum = max(1, max(v for _, v in points))
    dates = [datetime.strptime(day, '%Y-%m-%d') for day, _ in points]
    duration = (dates[-1] - dates[0]).days
    if duration <= 0:
        return ''
    marks = []
    for i, (day, value) in enumerate(points):
        x, y = 45 + (dates[i] - dates[0]).days * 410 / duration, 150 - value / maximum * 110
        marks.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="currentColor"><title>{html.escape(day)}: {value:g} species</title></circle>')
    table = '; '.join(f'{day}: {value:g}' for day, value in points)
    return ('<section class="card"><h2>Variety, day by day</h2><figure>'
            '<svg viewBox="0 0 500 190" role="img" aria-labelledby="chart-title chart-desc">'
            '<title id="chart-title">Recorded species diversity</title>'
            f'<desc id="chart-desc">{html.escape(table)}</desc>'
            '<path d="M45 30V150H455" fill="none" stroke="currentColor" opacity=".5"/>'
            f'<text x="12" y="40">{maximum:g}</text><text x="20" y="155">0</text>'
            + ''.join(marks) + f'<text x="45" y="178">{html.escape(points[0][0][5:])}</text>'
            f'<text x="418" y="178">{html.escape(points[-1][0][5:])}</text></svg>'
            '<figcaption>Distinct species across matching clock hours. Each dot is an available comparable day; gaps are not zero-filled.</figcaption>'
            f'<details><summary>Chart values</summary><p>{html.escape(table)}</p></details></figure></section>')


def display_date(value):
    day = datetime.strptime(value, '%Y-%m-%d')
    return f'{day:%A}, {day:%B} {day.day}, {day.year}'


def document(title, body, archive=False):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="referrer" content="no-referrer">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{html.escape(title)} · Birdynator</title><style>{CSS}{ARCHIVE_CSS if archive else ""}</style></head>'
            f'<body class="{"archive" if archive else "report"}"><main>{body}</main></body></html>')


def render_html(report):
    validate(report)
    titles = source_titles(report)
    metrics = ''.join(f'<div class="metric"><strong>{m["value"]:g}</strong><span>{html.escape(m["label"])}</span></div>' for m in report['summary_metrics'])
    story = '<section class="card story"><span class="eyebrow">Today’s story</span>' + paragraphs(report['todays_story'], titles) + '</section>'
    findings = ''.join(paragraphs(f['text'], titles) for f in report['findings'])
    if findings:
        story += '<section class="card"><h2>What caught my eye</h2>' + findings + '</section>'
    story += chart(report)
    side = ''
    for key, tag in [('watching', 'A question to revisit'), ('model_surprise', 'Experimental model context'), ('bird_to_explore', 'Connected to this day')]:
        item = report.get(key)
        if item and item['text'].strip():
            side += f'<section class="card"><span class="tag">{tag}</span><h2>{LABELS[key]}</h2>{paragraphs(item["text"], titles)}</section>'
    evidence = report.get('evidence')
    provenance = html.escape(json.dumps(report['provenance'], ensure_ascii=False, indent=2))
    if evidence:
        provenance += '\n\n' + html.escape(json.dumps({'coverage': evidence.get('coverage'), 'interesting_signals': evidence.get('interesting_signals')}, ensure_ascii=False, indent=2))
    return document(report['headline'], '<nav aria-label="Journal"><a href="index.html">← Journal archive</a></nav>'
        f'<header><div class="brand">Birdynator / Field journal</div><p class="date">{display_date(report["date"])}</p><h1>{html.escape(report["headline"])}</h1><p class="note">{html.escape(report["provenance"]["origin"])}</p><div class="metrics">{metrics}</div></header>'
        f'<div class="grid"><div>{story}</div><aside aria-label="More to explore">{side}</aside></div>'
        '<details><summary>Evidence &amp; provenance</summary><p>Narrative is interpretation. Observations, exploratory correlations, hypotheses, predictions and external context are retained separately below. Questions are not canonical memory.</p>'
        f'<pre>{provenance}</pre></details><footer>Birdynator · A personal record of what caught our attention.</footer>')


def render_markdown(report):
    validate(report)
    parts = [f'# {report["headline"]}', display_date(report['date']), report['provenance']['origin'],
             "## Today's story", report['todays_story']]
    for key in ('findings', 'watching', 'model_surprise', 'bird_to_explore'):
        items = report[key] if key == 'findings' else [report[key]]
        text = '\n\n'.join(i['text'] for i in items if i and i['text'].strip())
        if text:
            parts += [f'## {LABELS[key]}', text]
    parts += ['## Provenance', json.dumps(report['provenance'], ensure_ascii=False, indent=2)]
    return '\n\n'.join(parts) + '\n'


def atomic_write(path, text):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


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


def export(report, directory):
    validate(report)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f'{report["date"]}-{report["provenance"]["analysis_id"]}'
    atomic_write(directory / f'{stem}.html', render_html(report))
    atomic_write(directory / f'{stem}.md', render_markdown(report))
    atomic_write(directory / f'{stem}.json', json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    entries = []
    for path in directory.glob('*.json'):
        saved = validate(json.loads(path.read_text(encoding='utf-8')))
        expected = f'{saved["date"]}-{saved["provenance"]["analysis_id"]}'
        if path.stem != expected:
            raise ValueError('Journal filename does not match its record')
        entries.append((saved['date'], path.stem, saved['headline']))
    entries.sort(reverse=True)
    links = ''.join(f'<article class="entry"><p class="date">{display_date(date)}</p><h2><a href="{stem}.html">{html.escape(title)}</a></h2><a href="{stem}.md">Markdown</a> · <a href="{stem}.json">Structured report</a></article>' for date, stem, title in homepage_entries(entries))
    logo_path = Path(__file__).resolve().parent / 'birdynator-logo.png'
    logo = ''
    if logo_path.is_file():
        shutil.copyfile(logo_path, directory / 'birdynator-logo.png')
        logo = '<div class="logo-frame"><img src="birdynator-logo.png" alt="Birdynator bird logo" width="170" height="170"></div>'
    atomic_write(directory / 'index.html', document('Burbank - Bird Home', '<header class="archive-header' + ('' if logo else ' no-logo') + '">' + logo + '<div><div class="brand">Birdynator / Field journal</div><h1>Burbank - Bird Home</h1><p>A growing record of birds, patterns, and questions.</p></div></header>' + links, archive=True))
    atomic_write(directory / 'index.md', '# Birdynator Journal\n\n' + '\n'.join(f'- [{display_date(date)} — {title}]({stem}.md)' for date, stem, title in entries) + '\n')
    return directory / f'{stem}.html'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('analysis_json', type=Path, help='Exported analysis_runs record')
    parser.add_argument('--evidence', type=Path, help='Exact evidence packet matching source_digest')
    parser.add_argument('--headline')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.analysis_json.read_text(encoding='utf-8-sig'))
    evidence = json.loads(args.evidence.read_text(encoding='utf-8-sig')) if args.evidence else None
    print(export(report_from_analysis(record, evidence, args.headline), args.output))


if __name__ == '__main__':
    main()
