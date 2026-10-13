import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('https_plan', ROOT / 'deploy/journal-host/https_plan.py')
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


class PlanTests(unittest.TestCase):
    def test_scoped_listener_rule_and_separate_site(self):
        template = (ROOT / 'deploy/journal-host/nginx-https.conf.example').read_text()
        packet = planner.plan('192.0.2.10', '192.0.2.0/24', 'test0', template)
        self.assertIn('listen 192.0.2.10:443 ssl;', packet['config_text'])
        self.assertNotIn('listen 443', packet['config_text'])
        self.assertFalse(packet['feedback_writes_enabled'])
        self.assertEqual(packet['firewall_add'][2:], packet['firewall_remove_if_added_by_this_installation'][3:])
        self.assertNotIn('proxy_pass', packet['config_text'])

    def test_public_address_broad_range_and_interface_injection_rejected(self):
        template = (ROOT / 'deploy/journal-host/nginx-https.conf.example').read_text()
        for args in [('8.8.8.8', '8.8.8.0/24', 'test0'), ('192.0.2.10', '192.0.0.0/16', 'test0'),
                     ('192.0.2.10', '192.0.2.0/24', 'test0; restart')]:
            with self.assertRaises(ValueError):
                planner.plan(*args, template)
