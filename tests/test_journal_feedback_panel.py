from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from journal_feedback.panel import render
from test_journal_feedback import source
from journal_feedback.contract import target
from journal_feedback.rendering import decorate


class PanelTests(unittest.TestCase):
    def test_active_panel_requires_separate_external_script_and_login(self):
        page = render(target(source()), ['todays_story'], active=True)
        self.assertIn('href="/api/journal-feedback/sign-in.html"', page)
        self.assertIn('src="/journal-feedback.js?v=3" defer', page)
        self.assertIn('data-feedback-save', page)
        self.assertIn('data-feedback-history-load', page)
        self.assertNotIn('onclick=', page)
        self.assertLess(page.index('Sign in to reviews'), page.index('<details class="feedback"'))
        self.assertIn('data-feedback-session', page)
        self.assertIn('Check sign-in', page)

    def test_decoration_preserves_story_and_rejects_duplicate_or_unknown_policy(self):
        page = '<html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'"><style></style></head><body><main><p>Saved prose.</p></main></body></html>'
        result = decorate(page, source(), ['todays_story'])
        self.assertIn('<p>Saved prose.</p>', result)
        self.assertIn("script-src 'self'; connect-src 'self'", result)
        self.assertIn(target(source())['narrative_digest'], result)
        with self.assertRaises(ValueError):
            decorate(result, source(), ['todays_story'])
        with self.assertRaises(ValueError):
            decorate(page.replace("default-src 'none'", "default-src *"), source(), ['todays_story'])

    def test_metadata_is_escaped_and_saving_disabled(self):
        record = source()
        record['model'] = 'model"><script>unexpected</script>'
        page = render(target(record), ['todays_story', 'watching'])
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('button type="button" disabled', page)
        self.assertNotIn('<form', page)
        self.assertNotIn('fetch(', page)

    def test_section_choices_are_report_specific(self):
        page = render(target(source()), ['todays_story'])
        self.assertIn('value="todays_story"', page)
        self.assertNotIn('value="who_is_changing"', page)
        with self.assertRaises(ValueError):
            render(target(source()), ['unknown'])
