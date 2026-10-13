/* Exact report identity, append-only revisions, stable retry UUID. */
(() => {
  "use strict";
  const panel = document.querySelector('[data-feedback-target]');
  if (!panel) return;
  const button = panel.querySelector('[data-feedback-save]');
  if (!button) return;
  const status = panel.querySelector('.status');
  const history = panel.querySelector('[data-feedback-history]');
  const session = panel.querySelector('[data-feedback-session]');
  const refreshSessionButton = panel.querySelector('[data-feedback-session-refresh]');
  const target = JSON.parse(panel.dataset.feedbackTarget);
  let pending = null, latest = null, busy = false;
  const fields = [...panel.querySelectorAll('input, textarea, select')];
  const value = id => panel.querySelector('#' + id).value;
  const matches = review => Object.keys(target).every(key => review.target[key] === target[key]);
  const lock = enabled => fields.forEach(field => { field.disabled = enabled; });
  let sessionBusy = false, lastSessionCheck = 0, authGeneration = 0;
  async function refreshSession(force = false) {
    if (!session || sessionBusy || (!force && Date.now() - lastSessionCheck < 5000)) return;
    if (location.protocol !== 'https:') { session.textContent = 'Open HTTPS to sign in to reviews.'; return; }
    sessionBusy = true;
    const generation = authGeneration;
    session.textContent = 'Checking review sign-in…';
    lastSessionCheck = Date.now();
    try {
      const state = await call('session');
      if (generation !== authGeneration) return;
      // This endpoint returns 200 signed_in:false instead of a Basic challenge,
      // so opening a report never triggers a login dialog.
      if (state.signed_in === false) session.textContent = 'Not signed in to reviews';
      else if (state.schema_version === 'journal-feedback-v1' && state.reviewer_id) session.textContent = 'Signed in to reviews';
      else session.textContent = 'Review sign-in status unavailable';
    } catch (_) { if (generation === authGeneration) session.textContent = 'Review sign-in status unavailable · check again'; }
    finally { sessionBusy = false; }
  }
  async function call(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch('/api/journal-feedback/' + path, {
        ...options, credentials: 'same-origin', cache: 'no-store', signal: controller.signal
      });
      if (!response.ok) {
        if (session && (response.status === 401 || response.status === 403)) { authGeneration++; session.textContent = 'Not signed in to reviews'; }
        const error = new Error(response.status === 401 || response.status === 403
          ? 'Sign in to reviews, then try again.'
          : response.status === 409 ? 'A newer review exists. Your draft is kept; try again to save a revision.'
          : 'Saving was not confirmed. Please try again.');
        // A definite client rejection never saved this attempt. Transport/5xx
        // errors are ambiguous, so retain exactly the same UUID and body.
        error.definite = response.status >= 400 && response.status < 500;
        throw error;
      }
      const document = await response.json();
      if (session && (path === 'context' || path.startsWith('history?')) && document.reviewer_id) { authGeneration++; session.textContent = 'Signed in to reviews'; }
      return document;
    } finally { clearTimeout(timeout); }
  }
  async function loadHistory() {
    const data = await call('history?analysis_id=' + encodeURIComponent(target.analysis_id));
    const reviews = data.reviews.filter(item => matches(item.review));
    latest = reviews.length ? reviews[0].review.feedback_id : null;
    history.replaceChildren();
    if (!reviews.length) return data;
    const title = document.createElement('p');
    title.textContent = 'Your saved reviews';
    history.append(title);
    for (const item of reviews.slice(0, 10)) {
      const entry = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = new Date(item.review.created_at).toLocaleString() + ' · ' +
        (item.status === 'imported' ? 'Synced to AI Nexus' : 'Saved on Utility');
      const text = document.createElement('p');
      text.style.whiteSpace = 'pre-wrap';
      text.textContent = [item.review.overall ? 'Worth reading: ' + item.review.overall : '',
        item.review.comment, item.review.wanted_instead ? 'Wanted instead: ' + item.review.wanted_instead : '',
        ...item.review.sections.map(section => section.section + ': ' + section.comment)].filter(Boolean).join('\n\n');
      entry.append(summary, text);
      history.append(entry);
    }
    return data;
  }
  panel.querySelector('[data-feedback-history-load]').addEventListener('click', async () => {
    if (location.protocol !== 'https:') { status.textContent = 'Open the HTTPS journal to view feedback.'; return; }
    try { await loadHistory(); status.textContent = latest ? 'Saved reviews loaded.' : 'No saved reviews for this report yet.'; }
    catch (error) { status.textContent = error.message; }
  });
  refreshSessionButton?.addEventListener('click', () => refreshSession(true));
  window.addEventListener('focus', () => refreshSession());
  refreshSession();
  window.addEventListener('beforeunload', event => {
    if (pending) { event.preventDefault(); event.returnValue = ''; }
  });
  button.addEventListener('click', async () => {
    if (busy) return;
    if (location.protocol !== 'https:') {
      status.textContent = 'Open the HTTPS journal to save feedback.';
      return;
    }
    busy = true; button.disabled = true;
    try {
      if (!pending) {
        const state = await loadHistory();
        // Older installed servers return history without context. Retain a
        // fallback until this backward-compatible API update is deployed.
        const context = state.reviewer_id && state.schema_version ? state : await call('context');
        const section = value('feedback-section');
        const sectionComment = value('feedback-section-comment');
        const overall = panel.querySelector('input[name="feedback-overall"]:checked')?.value || null;
        if (!overall && !value('feedback-comment').trim() && !value('feedback-wanted').trim() && !(section && sectionComment.trim())) {
          status.textContent = 'Choose a rating or write a comment before saving.';
          return;
        }
        pending = {
          schema_version: context.schema_version, feedback_id: crypto.randomUUID(), reviewer_id: context.reviewer_id,
          created_at: new Date().toISOString(), supersedes: latest, target, overall, issue_tags: [],
          comment: value('feedback-comment'), wanted_instead: value('feedback-wanted'),
          sections: section && sectionComment.trim() ? [{section, worth_reading: null, issue_tags: [], comment: sectionComment}] : []
        };
        lock(true);
      }
      const receipt = await call('reviews', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(pending)});
      if (receipt.feedback_id !== pending.feedback_id || !['saved_on_utility', 'imported'].includes(receipt.status)) {
        throw new Error('Unexpected save response. Retry keeps the same review identity.');
      }
      pending = null; lock(false);
      status.textContent = receipt.status === 'imported' ? 'Saved and synced to AI Nexus.' : 'Saved on Utility. Awaiting transfer to AI Nexus.';
      button.textContent = 'Save another revision';
      // A history-read failure must not turn a confirmed save into a retry.
      try { await loadHistory(); } catch (_) { status.textContent += ' History is temporarily unavailable.'; }
    } catch (error) {
      status.textContent = error.message || 'Saving was not confirmed. Your draft stays in this tab.';
      if (error.definite) { pending = null; lock(false); }
      button.textContent = pending ? 'Retry saving this review' : 'Save review';
    } finally { busy = false; button.disabled = false; }
  });
})();
