"""Human editorial feedback protocol. No network, database or model side effects."""
from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID

VERSION = 'journal-feedback-v1'
MAX_BYTES = 32768
RATINGS = ('yes', 'partly', 'no', 'unsure')
ISSUES = ('repetitive', 'unsupported', 'unclear', 'uninteresting', 'missing_context', 'identification_concern', 'useful')
SECTIONS = ('todays_story', 'who_is_changing', 'following_up', 'findings', 'recent_context',
            'daily_rhythm', 'bird_to_explore', 'watching', 'model_surprise')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Unexpected feedback fields')


def identifier(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError('Expected canonical UUID')


def text(value, maximum, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError('Invalid feedback text')
    if any(ord(char) < 32 and char not in '\t\r\n' for char in value):
        raise ValueError('Unexpected control character')


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('Invalid digest')


def target(record):
    params = record.get('parameters') or {}
    if isinstance(params, str):
        params = json.loads(params)
    result = {'analysis_id': record['id'], 'model': record['model'],
              'prompt_version': params.get('prompt_version'), 'source_digest': record['source_digest'],
              'source_latest_hour': str(record['source_latest_hour']).replace(' ', 'T'),
              'narrative_digest': hashlib.sha256(record['result_text'].encode('utf-8')).hexdigest()}
    validate_target(result)
    return result


def validate_target(value):
    exact(value, ('analysis_id', 'model', 'prompt_version', 'source_digest', 'source_latest_hour', 'narrative_digest'))
    if type(value['analysis_id']) is not int or not 1 <= value['analysis_id'] <= 9223372036854775807:
        raise ValueError('Invalid analysis ID')
    text(value['model'], 128, True)
    if value['prompt_version'] is not None:
        text(value['prompt_version'], 128, True)
    hash_value(value['source_digest'])
    hash_value(value['narrative_digest'])
    hour = value['source_latest_hour']
    if not isinstance(hour, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:00:00', hour):
        raise ValueError('Expected aligned source local hour')
    datetime.fromisoformat(hour)


def tags(value):
    if not isinstance(value, list) or any(not isinstance(item, str) or item not in ISSUES for item in value):
        raise ValueError('Invalid issue tags')
    if len(value) != len(set(value)):
        raise ValueError('Duplicate issue tag')


def rating(value):
    if value is not None and (not isinstance(value, str) or value not in RATINGS):
        raise ValueError('Invalid reading rating')


def validate(review):
    exact(review, ('schema_version', 'feedback_id', 'reviewer_id', 'created_at', 'supersedes', 'target',
                   'overall', 'issue_tags', 'comment', 'wanted_instead', 'sections'))
    if review['schema_version'] != VERSION:
        raise ValueError('Unsupported feedback version')
    identifier(review['feedback_id'])
    identifier(review['reviewer_id'])
    if review['supersedes'] is not None:
        identifier(review['supersedes'])
        if review['supersedes'] == review['feedback_id']:
            raise ValueError('Feedback cannot supersede itself')
    created = review['created_at']
    if not isinstance(created, str) or len(created) > 40:
        raise ValueError('Invalid client timestamp')
    stamp = datetime.fromisoformat(created.replace('Z', '+00:00'))
    if stamp.utcoffset() != timezone.utc.utcoffset(stamp):
        raise ValueError('Client timestamp must explicitly use UTC')
    validate_target(review['target'])
    rating(review['overall'])
    tags(review['issue_tags'])
    text(review['comment'], 6000)
    text(review['wanted_instead'], 2000)
    sections = review['sections']
    if not isinstance(sections, list) or len(sections) > len(SECTIONS):
        raise ValueError('Invalid section reviews')
    seen = set()
    for section in sections:
        exact(section, ('section', 'worth_reading', 'issue_tags', 'comment'))
        if not isinstance(section['section'], str) or section['section'] not in SECTIONS or section['section'] in seen:
            raise ValueError('Unknown or duplicate section')
        seen.add(section['section'])
        rating(section['worth_reading'])
        tags(section['issue_tags'])
        text(section['comment'], 2000)
        if section['worth_reading'] is None and not section['issue_tags'] and not section['comment'].strip():
            raise ValueError('Empty section review')
    if review['overall'] is None and not review['issue_tags'] and not review['comment'].strip() and not review['wanted_instead'].strip() and not sections:
        raise ValueError('Empty review')
    if len(canonical(review)) > MAX_BYTES:
        raise ValueError('Feedback exceeds size limit')
    return review


def parse(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('Invalid feedback bytes or size')
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return validate(json.loads(data.decode('utf-8'), object_pairs_hook=unique,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON'))))


def verify_source(review, record):
    validate(review)
    if review['target'] != target(record):
        raise ValueError('Feedback target differs from saved analysis')
