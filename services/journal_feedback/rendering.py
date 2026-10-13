"""Opt-in exact-report decoration, not yet wired into normal publication.

The nginx HTTPS CSP must independently allow the reviewed external script/API.
"""
import re
from .contract import target
from .panel import CSS, render


def decorate(page, saved_record, sections):
    if 'data-feedback-target=' in page:
        raise ValueError('Report already has a review panel')
    if page.count('</main>') != 1 or page.count('</style>') != 1:
        raise ValueError('Unexpected journal structure')
    pattern = r'(<meta http-equiv="Content-Security-Policy" content=")([^"]+)(">)'
    matches = list(re.finditer(pattern, page))
    if len(matches) != 1 or "default-src 'none'" not in matches[0][2]:
        raise ValueError('Unexpected journal CSP')
    policy = matches[0][2]
    if 'script-src' in policy or 'connect-src' in policy:
        raise ValueError('Review an existing active-content policy before decorating')
    policy += "; script-src 'self'; connect-src 'self'"
    page = re.sub(pattern, lambda match: match[1] + policy + match[3], page)
    page = page.replace('</style>', CSS + '</style>')
    return page.replace('</main>', render(target(saved_record), sections, active=True) + '</main>')
