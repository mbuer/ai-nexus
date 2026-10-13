// Offline browser-state tests. No socket, real browser, credential or model call.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../services/journal_feedback/journal-feedback.js'), 'utf8');

function setup({protocol='https:', failSave=false, conflict=false, failHistoryAfterSave=false, signedIn=false, failSession=false, legacyHistory=false}={}) {
  const events = {};
  const element = () => ({value:'', disabled:false, textContent:'', style:{},
    addEventListener(name, fn) { this[name]=fn; }, append(){}, replaceChildren(){}});
  const save = element(), load = element(), status = element(), history = element();
  const session = element(), refresh = element();
  const fields = Object.fromEntries(['feedback-comment','feedback-wanted','feedback-section','feedback-section-comment']
    .map(id => [id, element()]));
  fields['feedback-comment'].value = 'Useful species comparison.';
  const target = {analysis_id:1, model:'test', prompt_version:'test-v1',
    source_digest:'a'.repeat(64), narrative_digest:'b'.repeat(64), source_latest_hour:'2026-10-12T12:00:00'};
  const panel = {dataset:{feedbackTarget:JSON.stringify(target)}, querySelectorAll(){ return Object.values(fields); },
    querySelector(selector) {
      return selector === '[data-feedback-save]' ? save : selector === '[data-feedback-history-load]' ? load :
        selector === '[data-feedback-session]' ? session : selector === '[data-feedback-session-refresh]' ? refresh :
        selector === '.status' ? status : selector === '[data-feedback-history]' ? history :
        selector.startsWith('#') ? fields[selector.slice(1)] : null;
    }};
  const posts = [];
  const calls = [];
  let saved = false;
  const context = {document:{querySelector:()=>panel, createElement:element}, location:{protocol},
    window:{addEventListener(name, fn){events[name]=fn;}}, crypto:require('node:crypto').webcrypto,
    AbortController, setTimeout, clearTimeout, Date, JSON, console,
    async fetch(url, options) {
      calls.push(url);
      assert.equal(options.credentials, 'same-origin');
      if (url.endsWith('/session')) {
        if (failSession) throw new Error('Status unavailable');
        return {ok:true,json:async()=>signedIn ? {schema_version:'journal-feedback-v1',reviewer_id:'reader'} : {signed_in:false}};
      }
      if (url.endsWith('/context')) return {ok:true,json:async()=>({schema_version:'journal-feedback-v1',reviewer_id:'reader'})};
      if (url.includes('/history?')) {
        if (saved && failHistoryAfterSave) throw new Error('History disconnected');
        return {ok:true,json:async()=>legacyHistory ? {reviews:[]} : {schema_version:'journal-feedback-v1',reviewer_id:'reader',reviews:[]}};
      }
      posts.push(options.body);
      if (posts.length === 1 && failSave) throw new Error('Connection lost');
      if (posts.length === 1 && conflict) return {ok:false,status:409};
      saved = true;
      return {ok:true,json:async()=>({feedback_id:JSON.parse(options.body).feedback_id,status:'saved_on_utility'})};
    }};
  vm.runInNewContext(script, context);
  return {save,load,status,fields,posts,events,session,refresh,calls};
}

(async () => {
  let optimized = setup();
  await optimized.save.click();
  assert.equal(optimized.calls.filter(url => url.endsWith('/context')).length, 0);
  assert.equal(optimized.posts.length, 1);
  optimized = setup({legacyHistory:true});
  await optimized.save.click();
  assert.equal(optimized.calls.filter(url => url.endsWith('/context')).length, 1, 'Older installed API retains a safe fallback');
  assert.equal(optimized.posts.length, 1);
  let probe = setup();
  await new Promise(setImmediate);
  assert.equal(probe.session.textContent, 'Not signed in to reviews');
  assert.equal(probe.posts.length, 0, 'Passive status probe cannot save or prompt through context');
  probe = setup({signedIn:true});
  await new Promise(setImmediate);
  assert.equal(probe.session.textContent, 'Signed in to reviews');
  probe = setup({failSession:true});
  await new Promise(setImmediate);
  assert.match(probe.session.textContent, /unavailable/);
  let page = setup({failSave:true});
  await page.save.click();
  assert.equal(page.fields['feedback-comment'].disabled, true);
  assert.match(page.save.textContent, /Retry/);
  let warned = false;
  page.events.beforeunload({preventDefault(){warned=true;}});
  assert.equal(warned, true);
  await page.save.click();
  assert.equal(page.posts.length, 2);
  assert.equal(page.posts[0], page.posts[1], 'Ambiguous retry must preserve UUID and exact payload');
  assert.equal(page.fields['feedback-comment'].disabled, false);
  assert.match(page.status.textContent, /Saved on Utility/);

  page = setup({conflict:true});
  await page.save.click();
  assert.equal(page.fields['feedback-comment'].disabled, false);
  assert.equal(page.fields['feedback-comment'].value, 'Useful species comparison.');
  await page.save.click();
  assert.notEqual(JSON.parse(page.posts[0]).feedback_id, JSON.parse(page.posts[1]).feedback_id);

  page = setup({failHistoryAfterSave:true});
  await page.save.click();
  assert.match(page.status.textContent, /Saved on Utility/);
  assert.match(page.status.textContent, /History is temporarily unavailable/);
  assert.equal(page.fields['feedback-comment'].disabled, false);

  page = setup({protocol:'http:'});
  await page.save.click();
  assert.equal(page.posts.length, 0);
  assert.match(page.status.textContent, /HTTPS/);
  console.log('Browser feedback tests passed: stable retries, conflicts, save receipts and HTTPS requirement.');
})().catch(error => { console.error(error); process.exitCode=1; });
