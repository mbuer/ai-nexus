import importlib.util
from pathlib import Path
import unittest

HOST = Path(__file__).resolve().parents[1] / 'deploy/journal-host'
spec = importlib.util.spec_from_file_location('feedback_config', HOST / 'feedback_config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class ConfigTests(unittest.TestCase):
    def test_session_probe_changes_no_save_or_history_authentication(self):
        current = config.configuration(self.baseline(), '192.0.2.10')
        updated = config.session_configuration(current)
        self.assertIn(current.rstrip()[:-1], updated)
        self.assertIn('error_page 401 = @journal_signed_out;', updated)
        self.assertIn('return 200 \'{"signed_in":false}\';', updated)
        self.assertIn('limit_except GET { deny all; }', updated)
        self.assertEqual(updated.count('error_page 401'), 1)
        self.assertNotIn('auth_basic off', updated)
        with self.assertRaises(ValueError):
            config.session_configuration(updated)

    def baseline(self):
        return '''server {
listen 192.0.2.10:443 ssl;
root /srv/birdynator-journal/current;
allow 192.0.2.0/24;
deny all;
add_header Content-Security-Policy "default-src 'none'; img-src 'self'" always;
}'''

    def test_routes_keep_lan_restriction_and_authentication_overwrites_identity(self):
        result = config.configuration(self.baseline(), '192.0.2.10')
        self.assertIn('allow 192.0.2.0/24;', result)
        self.assertIn('deny all;', result)
        self.assertEqual(result.count('auth_basic_user_file'), 2)
        self.assertIn('proxy_set_header Remote-User $remote_user;', result)
        self.assertIn('proxy_set_header Authorization "";', result)
        self.assertIn('connect-src https://192.0.2.10', result)
        self.assertNotIn('Access-Control-Allow-Origin', result)
        self.assertNotIn('listen 8080', result)

    def test_already_modified_unknown_policy_and_address_refused(self):
        changed = config.configuration(self.baseline(), '192.0.2.10')
        for text, address in ((changed, '192.0.2.10'), (self.baseline(), '8.8.8.8'),
                              (self.baseline().replace("default-src 'none'", 'default-src *'), '192.0.2.10')):
            with self.assertRaises(ValueError):
                config.configuration(text, address)

    def test_review_mapping_is_immutable_and_private_socket_only(self):
        packet = config.service_config('192.0.2.10', '11111111-1111-4111-8111-111111111111')
        self.assertEqual(packet['reviewers'], {'personal': '11111111-1111-4111-8111-111111111111'})
        self.assertTrue(packet['socket_path'].startswith('/run/'))
        with self.assertRaises(ValueError):
            config.service_config('192.0.2.10', 'invalid')
