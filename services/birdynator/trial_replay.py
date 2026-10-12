"""Explicit three-report API replay through existing agent secrets/proxy; no DB writes."""
from datetime import datetime, timezone
import hashlib
import json
import uuid
from urllib.error import HTTPError
from urllib.request import Request

from enrichment import DOMAINS, cited_report, enable_search

APPROVED_IDS = ('16', '19', '22')
MODEL = 'gpt-6.1-sol'

def request_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

def validate_batch(packets):
    if not isinstance(packets, list) or tuple(p.get('source_analysis_id') for p in packets) != APPROVED_IDS:
        raise ValueError('This replay is limited to the three approved source analyses')
    previous = None
    for packet in packets:
        body = packet['request']
        if body.get('model') != MODEL or body.get('store') is not False:
            raise ValueError('Model or store policy changed')
        if set(body) != {'model', 'store', 'instructions', 'input'}:
            raise ValueError('Unexpected API request fields before enrichment')
        if packet['prompt_version'] != 'birdynator-narrative-v3.1-trial' or not packet.get('longitudinal_available'):
            raise ValueError('Expected reviewed trial prompt and species history')
        if not packet.get('ready_for_model_comparison') or packet.get('request_sha256') != request_hash(body):
            raise ValueError('Request checksum or replay gate mismatch')
        envelope = json.loads(body['input'])
        source = envelope['source_evidence']
        sha = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if sha != packet['source_evidence_digest']:
            raise ValueError('Original evidence checksum mismatch')
        cutoff = source['window']['latest_hour']
        if envelope['trial_species_history'].get('through') != cutoff or (previous and cutoff <= previous):
            raise ValueError('History cutoff or chronological order mismatch')
        previous = cutoff

def run_batch(packets, emit=print):
    """Exactly one API attempt per selected report; stop on ambiguity, never retry."""
    validate_batch(packets)
    if tuple(DOMAINS) != ('allaboutbirds.org', 'ebird.org', 'en.wikipedia.org'):
        raise ValueError('Trusted-source domain policy changed')
    import birdynator
    if birdynator.OPENAI_API_URL != 'https://api.openai.com/v1/responses':
        raise ValueError('Unexpected API destination')
    def event(packet):
        emit(json.dumps(packet, ensure_ascii=True), flush=True)
    for packet in packets:
        run_id = 'trial-' + uuid.uuid4().hex
        payload = enable_search(packet['request'])
        envelope = json.loads(payload['input'])
        receipt = {'trial_run_id': run_id, 'source_analysis_id': packet['source_analysis_id'],
                   'model': MODEL, 'prompt_version': packet['prompt_version'],
                   'trial_version': packet['trial_version'],
                   'source_evidence_digest': packet['source_evidence_digest'],
                   'source_latest_hour': envelope['source_evidence']['window']['latest_hour'],
                   'prepared_request_sha256': packet['request_sha256'],
                   'actual_request_sha256': request_hash(payload),
                   'actual_request': payload,
                   'attempted_at': datetime.now(timezone.utc).isoformat(),
                   'max_tool_calls': 2, 'allowed_domains': list(DOMAINS)}
        event({'event': 'started', **receipt})
        data = None
        try:
            request = Request(birdynator.OPENAI_API_URL, data=json.dumps(payload).encode(),
                              headers={'Authorization': 'Bearer ' + birdynator.openai_key(),
                                       'Content-Type': 'application/json'})
            with birdynator.openai_opener().open(request, timeout=180) as response:
                data = json.loads(response.read())
            if data.get('status') in ('failed', 'incomplete', 'cancelled'):
                raise ValueError('Provider response did not complete')
            text, context = cited_report(data)
            if not text.strip():
                raise ValueError('Provider returned no report text')
            citation_review = not context.get('search_calls') or not context.get('cited_sources')
            event({'event': 'completed', **receipt, 'result_text': text, 'external_context': context,
                   'citation_review_needed': citation_review, 'response': data,
                   'completed_at': datetime.now(timezone.utc).isoformat()})
        except Exception as error:
            # Preserve paid output when available; never disclose auth or request headers.
            event({'event': 'needs_review', **receipt, 'error_type': type(error).__name__,
                   'http_status': error.code if isinstance(error, HTTPError) else None,
                   'response': data})
            return False
    return True
