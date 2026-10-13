"""Report-bound feedback panel; active controls are an explicit publishing option."""
import html
import json

from .contract import SECTIONS, validate_target

LABELS = {'todays_story': "Today's story", 'who_is_changing': 'Who is changing', 'following_up': 'Following up',
          'findings': 'What caught my eye', 'recent_context': 'The recent picture',
          'daily_rhythm': 'The rhythm of the day', 'bird_to_explore': 'Bird to explore',
          'watching': 'Birdynator is watching', 'model_surprise': 'Model surprise'}
CSS = '''
.feedback-shell{margin:40px 0 20px;padding:24px;border:1px solid var(--line);border-radius:16px;background:var(--paper)}
.feedback-shell .review-account{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:0 0 20px;padding:0 0 24px;border-bottom:1px solid var(--line);font:15px/1.5 system-ui,sans-serif}
.feedback-shell .review-account p{margin:0}.feedback-shell .review-account a{font-weight:600}.feedback-shell .review-account button{font:14px system-ui,sans-serif;border:1px solid var(--line);border-radius:18px;padding:7px 12px;background:var(--bg);color:var(--ink)}
.feedback{margin:0;padding:0;border:0}
.feedback summary{font:25px/1.4 Georgia,serif;color:var(--ink);cursor:pointer}.feedback p{color:var(--muted);font:15px/1.6 system-ui,sans-serif}
.feedback fieldset{border:0;padding:0;margin:24px 0}.feedback legend,.feedback .field-label{font:600 15px/1.5 system-ui,sans-serif;margin-bottom:12px;display:block}
.feedback .ratings{display:flex;flex-wrap:wrap;gap:10px}.feedback .ratings label{display:flex;gap:7px;align-items:center;border:1px solid var(--line);border-radius:24px;padding:9px 13px}
.feedback textarea,.feedback select{width:100%;font:16px/1.5 system-ui,sans-serif;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:12px;margin-bottom:18px}
.feedback textarea{min-height:110px;resize:vertical}.feedback input:focus-visible,.feedback textarea:focus-visible,.feedback select:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
.feedback button{font:600 16px system-ui,sans-serif;padding:12px 22px;border:0;border-radius:24px;background:var(--accent);color:var(--paper)}.feedback button:disabled{opacity:.5}
.feedback .status{font-size:13px;margin-top:12px}.feedback .section-review{padding-top:8px;border-top:1px solid var(--line)}
'''


def render(target, sections, active=False):
    validate_target(target)
    if len(sections) != len(set(sections)) or any(key not in SECTIONS for key in sections):
        raise ValueError('Unknown or duplicate feedback section')
    metadata = html.escape(json.dumps(target, separators=(',', ':')), quote=True)
    options = '<option value="">Whole report</option>' + ''.join(
        f'<option value="{key}">{html.escape(LABELS[key])}</option>' for key in sections)
    ratings = ''.join(f'<label><input type="radio" name="feedback-overall" value="{value}">{label}</label>'
                      for value, label in [('yes', 'Yes'), ('partly', 'Partly'), ('no', 'No'), ('unsure', 'Not sure')])
    status = ('Sign in to save a review. Saved reviews stay on Utility until transfer to AI Nexus.' if active
              else 'Local layout preview. Nothing entered here is saved or submitted.')
    account = ('<header class="review-account"><p data-feedback-session role="status" aria-live="polite">Review sign-in not checked · use the HTTPS journal</p>'
               '<a href="/api/journal-feedback/sign-in.html" target="_blank" rel="noopener">Sign in to reviews</a>'
               '<button type="button" data-feedback-session-refresh>Check sign-in</button></header>' if active else '')
    return f'''<section class="feedback-shell" data-feedback-target="{metadata}">{account}<details class="feedback" open>
<summary>Was this worth reading?</summary>
<p>Your impressions can help shape future journals. Tell us what added something and what you would rather learn.</p>
<fieldset><legend>How did this report feel?</legend><div class="ratings">{ratings}</div></fieldset>
<label class="field-label" for="feedback-comment">What worked, or felt repetitive or unsupported?</label>
<textarea id="feedback-comment" maxlength="6000" placeholder="A sentence or two is enough. You can also leave a more detailed review."></textarea>
<label class="field-label" for="feedback-wanted">What would you have liked to learn instead? <span>(optional)</span></label>
<textarea id="feedback-wanted" maxlength="2000"></textarea>
<details class="section-review"><summary style="font:600 15px system-ui,sans-serif">Comment on a section</summary>
<label class="field-label" for="feedback-section">Which part?</label><select id="feedback-section">{options}</select>
<label class="field-label" for="feedback-section-comment">Your impression</label><textarea id="feedback-section-comment" maxlength="2000"></textarea></details>
<p class="status" role="status" aria-live="polite">{status}</p>
<button type="button" {'data-feedback-save' if active else 'disabled'}>Save review</button>
{'<button type="button" data-feedback-history-load>View saved reviews</button><div data-feedback-history></div><script src="/journal-feedback.js?v=3" defer></script>' if active else ''}
</details></section>'''
