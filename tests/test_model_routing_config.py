"""Guard against deployed model tiers diverging from code/example defaults."""
import ast
from pathlib import Path
import re
import unittest

class ModelRoutingConfigurationTests(unittest.TestCase):
    def test_three_configuration_surfaces_agree(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / 'services/birdynator/birdynator.py').read_text())
        defaults = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Attribute) and call.func.attr == 'getenv' and len(call.args) == 2:
                    key = ast.literal_eval(call.args[0])
                    if key.startswith('BIRDYNATOR_MODEL_'):
                        defaults[key] = ast.literal_eval(call.args[1])
        expected = {'BIRDYNATOR_MODEL_FAST': 'gpt-6-luna',
                    'BIRDYNATOR_MODEL_DEFAULT': 'gpt-6.1-sol',
                    'BIRDYNATOR_MODEL_DEEP': 'gpt-6-astra'}
        self.assertEqual(defaults, expected)
        for name in ('config/runtime.example.env', 'containers/ai-nexus-birdynator.container'):
            values = dict(re.findall(r'(BIRDYNATOR_MODEL_[A-Z]+)="?([^"\s]+)', (root / name).read_text()))
            self.assertEqual(values, expected, name)

if __name__ == '__main__':
    unittest.main()
