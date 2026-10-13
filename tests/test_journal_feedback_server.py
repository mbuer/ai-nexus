from email.message import Message
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from journal_feedback.server import Handler, storage_available
import tempfile
from unittest.mock import patch


class AdapterTests(unittest.TestCase):
    def test_low_disk_space_prevents_further_saving_without_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'queue.sqlite'
            path.write_bytes(b'preserved')
            with patch('journal_feedback.server.shutil.disk_usage', return_value=Mock(free=0)):
                self.assertFalse(storage_available(path))
            self.assertEqual(path.read_bytes(), b'preserved')

    def request(self, headers, body=b'{}', method='POST'):
        handler = object.__new__(Handler)
        handler.headers = Message()
        for name, value in headers:
            handler.headers[name] = value
        handler.rfile = io.BytesIO(body)
        handler.command = method
        handler.path = '/api/journal-feedback/reviews'
        handler.server = Mock()
        handler.server.api.dispatch.return_value = (200, {}, {'status': 'saved_on_utility'})
        handler.answer = Mock()
        handler.handle_operation()
        return handler

    def test_duplicate_length_and_chunked_framing_never_reach_storage(self):
        for headers in ([('Content-Length', '2'), ('content-length', '2')],
                        [('Transfer-Encoding', 'chunked')], [('Expect', '100-continue')],
                        [('Content-Length', '-1')]):
            handler = self.request(headers)
            self.assertEqual(handler.answer.call_args.args[0], 400)
            handler.server.api.dispatch.assert_not_called()

    def test_size_missing_length_and_truncated_body_refused(self):
        for headers, status in ([('Content-Length', '32769')], 413), ([], 411), ([('Content-Length', '3')], 400):
            handler = self.request(headers)
            self.assertEqual(handler.answer.call_args.args[0], status)
            handler.server.api.dispatch.assert_not_called()

    def test_proxy_principal_is_passed_separately_from_json(self):
        handler = self.request([('Content-Length', '2'), ('Remote-User', 'personal')])
        self.assertEqual(handler.server.api.dispatch.call_args.args[-1], 'personal')
        self.assertEqual(handler.server.api.dispatch.call_args.args[-2], b'{}')

    def test_anonymous_request_has_no_implied_personal_identity(self):
        handler = self.request([('Content-Length', '2')])
        self.assertIsNone(handler.server.api.dispatch.call_args.args[-1])

    def test_read_request_has_no_required_body_length(self):
        handler = self.request([('Remote-User', 'personal')], body=b'', method='GET')
        self.assertEqual(handler.server.api.dispatch.call_args.args[-2], b'')
