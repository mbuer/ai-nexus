import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

HOST = Path(__file__).resolve().parents[1] / 'deploy/journal-host'
spec = importlib.util.spec_from_file_location('feedback_checks', HOST / 'feedback_checks.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class ReloadTests(unittest.TestCase):
    def test_old_worker_404_waits_for_expected_login_challenge(self):
        operation = Mock(side_effect=[HTTPError('https://example.test', 404, 'old worker', {}, None), b'challenge'])
        sleep = Mock()
        self.assertEqual(checks.wait_for_login(operation, sleep), b'challenge')
        sleep.assert_called_once_with(0.5)

    def test_persistent_404_is_bounded_and_fails(self):
        operation = Mock(side_effect=HTTPError('https://example.test', 404, 'wrong route', {}, None))
        sleep = Mock()
        with self.assertRaises(HTTPError):
            checks.wait_for_login(operation, sleep)
        self.assertEqual(operation.call_count, 10)
        self.assertEqual(sleep.call_count, 9)

    def test_other_errors_and_anonymous_success_do_not_get_retried(self):
        for failure in (HTTPError('https://example.test', 500, 'failed', {}, None), ValueError('Unexpected verification response')):
            operation, sleep = Mock(side_effect=failure), Mock()
            with self.assertRaises(type(failure)):
                checks.wait_for_login(operation, sleep)
            operation.assert_called_once()
            sleep.assert_not_called()
