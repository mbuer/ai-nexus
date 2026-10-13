"""One explicitly approved current-day preview using installed candidate code.

Executed inside Birdynator only. No files, timer, prompt or runtime setting changes.
The existing trial branch supplies evidence, editorial context and one provider
attempt. Its scheduling fields are replaced with explicit manual provenance before
persistence, rather than falsely claiming an altered scheduled trial.
"""
import argparse
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

PROMPT = 'birdynator-narrative-v3.2-trial'


def run_preview(agent, approved_date, scheduled_start, scheduled_end, today=None):
    today = today or datetime.now(ZoneInfo('America/Los_Angeles')).date()
    approved = date.fromisoformat(approved_date)
    first, last = date.fromisoformat(scheduled_start), date.fromisoformat(scheduled_end)
    if approved != today or last - first != timedelta(days=6):
        raise ValueError('Manual preview approval must match today and the recorded seven-day schedule')
    if agent.model_for_tier('default') != 'gpt-6.1-sol':
        raise ValueError('Reviewed manual preview requires the installed Sol 6.1 default')
    args = SimpleNamespace(hours=24, baseline_days=30, top_species=25, through=None,
                           tier='default', evidence_only=False, journal_output=None,
                           web_enrichment=True, journal_trial_start=today.isoformat(),
                           journal_trial_end=(today + timedelta(days=6)).isoformat())
    original = agent.save_analysis
    saved = False

    def save(dataset, parameters, model, text, digest):
        nonlocal saved
        if saved:
            raise ValueError('One manual preview may save only one analysis')
        metadata = dict(parameters.trial_metadata or {})
        if parameters.prompt_version != PROMPT or metadata.get('prompt_version') != PROMPT:
            raise ValueError('Installed candidate prompt differs from the reviewed preview')
        metadata.pop('start', None)
        metadata.pop('end', None)
        metadata.update(policy_version='journal-manual-preview-v1', manual_preview=True,
                        manual_date=approved_date,
                        scheduled_trial_unchanged={'start': scheduled_start, 'end': scheduled_end},
                        status='manual candidate preview; human review pending')
        parameters.trial_metadata = metadata
        saved = True
        return original(dataset, parameters, model, text, digest)

    agent.save_analysis = save
    try:
        print('One manual candidate preview. Scheduled policy and installed prompt unchanged.', flush=True)
        agent.analyze_birdnet(args)
    finally:
        agent.save_analysis = original


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-date', required=True)
    parser.add_argument('--scheduled-start', required=True)
    parser.add_argument('--scheduled-end', required=True)
    args = parser.parse_args()
    import birdynator
    from journal_trial import PROMPT_VERSION
    if PROMPT_VERSION != PROMPT:
        raise SystemExit('Installed trial prompt differs; no model request')
    run_preview(birdynator, args.approved_date, args.scheduled_start, args.scheduled_end)
