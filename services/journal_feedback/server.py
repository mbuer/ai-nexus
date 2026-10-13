"""Bounded HTTP adapter on a private Unix socket behind nginx authentication.

No TCP listener, TLS termination, password handling, AI access or browser import
acknowledgment. Only the restricted nginx socket peer may supply Remote-User.
"""
import argparse
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import socketserver
import shutil

from .api import API
from .contract import MAX_BYTES, canonical
from .outbox import Queue

MAX_QUEUE_BYTES = 256 * 1024 * 1024
MIN_FREE_BYTES = 32 * 1024 * 1024


def storage_available(path):
    path = Path(path)
    try:
        total = sum(item.stat().st_size for item in path.parent.iterdir() if item.is_file())
        return total < MAX_QUEUE_BYTES and shutil.disk_usage(path.parent).free >= MIN_FREE_BYTES
    except OSError:
        return False


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'JournalFeedback'

    def setup(self):
        self.request.settimeout(10)
        super().setup()

    def log_message(self, format, *args):
        # Do not log review text, URLs, credentials or account identifiers.
        pass

    def answer(self, status, document, headers=None):
        payload = canonical(document)
        self.send_response(status)
        for key, value in (headers or {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}).items():
            self.send_header(key, value)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(payload)

    def handle_operation(self):
        headers = list(self.headers.raw_items())
        lowered = {}
        for name, value in headers:
            name = name.lower()
            if name in lowered:
                return self.answer(400, {'error': 'Repeated request header.'})
            lowered[name] = value
        if 'transfer-encoding' in lowered or 'expect' in lowered:
            return self.answer(400, {'error': 'Unsupported request framing.'})
        length = lowered.get('content-length', '0')
        if not length.isascii() or not length.isdigit() or len(length) > 6:
            return self.answer(400, {'error': 'Invalid request length.'})
        length = int(length)
        if length > MAX_BYTES:
            return self.answer(413, {'error': 'Review exceeds the request limit.'})
        if self.command == 'POST' and 'content-length' not in lowered:
            return self.answer(411, {'error': 'Request length is required.'})
        if self.command == 'POST' and not self.server.storage_available():
            return self.answer(507, {'error': 'Review storage needs attention. Nothing confirmed saved.'})
        body = self.rfile.read(length)
        if len(body) != length:
            return self.answer(400, {'error': 'Incomplete request.'})
        # nginx overwrites this header after Basic authentication; socket is private.
        status, response_headers, document = self.server.api.dispatch(
            self.command, self.path, headers, body, lowered.get('remote-user'))
        return self.answer(status, document, response_headers)

    do_GET = handle_operation
    do_POST = handle_operation
    do_DELETE = handle_operation
    do_OPTIONS = handle_operation
    do_PUT = handle_operation
    do_PATCH = handle_operation


class Server(getattr(socketserver, 'UnixStreamServer', socketserver.BaseServer)):
    # Serial handling bounds worker count and SQLite contention. nginx supplies
    # buffering/rate limits; timeouts bound slow clients on the private socket.
    request_queue_size = 16

    def handle_error(self, request, client_address):
        print('Feedback request failed; review save was not confirmed.', flush=True)


def serve(config_path):
    if not hasattr(socketserver, 'UnixStreamServer'):
        raise ValueError('Service requires Linux Unix sockets; no TCP fallback')
    config = json.loads(Path(config_path).read_text())
    if set(config) != {'origin', 'reviewers', 'socket_path', 'queue_path'}:
        raise ValueError('Unexpected service configuration')
    socket_path = Path(config['socket_path'])
    if (socket_path.is_symlink() or socket_path.exists()
            or socket_path.parent.is_symlink() or not socket_path.parent.is_dir()):
        raise ValueError('Socket directory must be provisioned privately and empty')
    if socket_path.parent.stat().st_mode & 0o007:
        raise ValueError('Socket directory is accessible to unrelated users')
    queue_path = Path(config['queue_path'])
    parent = queue_path.parent
    if parent.is_symlink() or not parent.is_dir() or parent.stat().st_uid != os.geteuid() or parent.stat().st_mode & 0o077:
        raise ValueError('Queue directory must belong privately to the service account')
    api = API(Queue(queue_path), config['origin'], config['reviewers'])
    os.umask(0o007)
    with Server(str(socket_path), Handler) as server:
        server.api = api
        server.storage_available = lambda: storage_available(queue_path)
        socket_path.chmod(0o660)
        try:
            print('Private feedback adapter ready.', flush=True)
            server.serve_forever(poll_interval=0.5)
        finally:
            socket_path.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    serve(parser.parse_args().config)
