"""Feedback request policy behind the trusted HTTPS/authentication proxy.

This module opens no socket and installs no service. The adapter must supply a
principal from the authenticated private proxy path, never from browser JSON.
"""
from urllib.parse import parse_qs, urlsplit
import sqlite3

from .contract import MAX_BYTES, identifier


class API:
    def __init__(self, outbox, origin, reviewers):
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('Feedback requires an exact HTTPS origin')
        if not isinstance(reviewers, dict) or not reviewers:
            raise ValueError('Authenticated reviewer mapping is required')
        for principal, reviewer in reviewers.items():
            if not isinstance(principal, str) or not principal.strip():
                raise ValueError('Invalid authentication principal')
            identifier(reviewer)
        self.outbox, self.origin, self.reviewers = outbox, origin, dict(reviewers)

    def dispatch(self, method, path, headers, body, authenticated_principal):
        response_headers = {'Content-Type': 'application/json; charset=utf-8',
                            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        def response(status, document):
            return status, response_headers, document
        if authenticated_principal not in self.reviewers:
            return response(403, {'error': 'Review login is required.'})
        reviewer = self.reviewers[authenticated_principal]
        if not isinstance(body, bytes) or len(body) > MAX_BYTES:
            return response(413, {'error': 'Review exceeds the request limit.'})
        # The HTTP adapter must preserve repeated headers for this check.
        normalized = {}
        for key, value in headers:
            key = key.lower()
            if key in normalized:
                return response(400, {'error': 'Repeated request header.'})
            normalized[key] = value
        location = urlsplit(path)
        if location.scheme or location.netloc or location.fragment:
            return response(400, {'error': 'Unexpected request path.'})
        if method == 'GET':
            if body:
                return response(400, {'error': 'Read requests cannot contain a body.'})
            if location.path == '/api/journal-feedback/context' and not location.query:
                return response(200, {'schema_version': 'journal-feedback-v1', 'reviewer_id': reviewer})
            if location.path == '/api/journal-feedback/history':
                try:
                    query = parse_qs(location.query, strict_parsing=True, max_num_fields=2)
                    if set(query) not in ({'analysis_id'}, {'analysis_id', 'before'}) or any(len(v) != 1 for v in query.values()):
                        raise ValueError('Unexpected query')
                    number = query['analysis_id'][0]
                    if not number.isascii() or not number.isdigit() or len(number) > 19 or int(number) <= 0 or int(number) > 9223372036854775807:
                        raise ValueError('Invalid analysis ID')
                    before = query.get('before', [None])[0]
                    return response(200, {'schema_version': 'journal-feedback-v1', 'reviewer_id': reviewer,
                                          'reviews': self.outbox.history(reviewer, int(number), before=before)})
                except (ValueError, KeyError):
                    return response(400, {'error': 'Invalid review history query.'})
            return response(404, {'error': 'Unknown feedback route.'})
        if method != 'POST':
            return response(405, {'error': 'Unsupported feedback operation.'})
        if location.path != '/api/journal-feedback/reviews' or location.query:
            return response(404, {'error': 'Unknown feedback route.'})
        if normalized.get('origin') != self.origin:
            return response(403, {'error': 'Save reviews from the Journal page.'})
        media_type = normalized.get('content-type', '').lower().split(';', 1)[0].strip()
        if media_type != 'application/json':
            return response(415, {'error': 'Reviews must use JSON.'})
        try:
            result = self.outbox.save(body, reviewer)
        except ValueError as error:
            if 'collision' in str(error) or 'revision' in str(error):
                return response(409, {'error': 'This review changed. Refresh its history before revising it.'})
            return response(400, {'error': 'Review does not match the accepted format or reader.'})
        except sqlite3.OperationalError:
            return response(503, {'error': 'Review storage is temporarily unavailable. Your draft is not confirmed saved.'})
        return response(200, result)
