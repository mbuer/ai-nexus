"""Render bounded nginx additions; no service or credential side effects."""
import ipaddress
import re
from uuid import UUID


def configuration(current, address):
    address = ipaddress.IPv4Address(address)
    if not address.is_private or address.is_loopback or address.is_link_local or address.is_unspecified:
        raise ValueError('Expected reserved LAN address')
    if (f'listen {address}:443 ssl;' not in current
            or 'root /srv/birdynator-journal/current;' not in current
            or 'journal-feedback' in current or 'proxy_pass' in current):
        raise ValueError('Existing HTTPS configuration needs inspection')
    pattern = r'add_header Content-Security-Policy "([^"]+)" always;'
    policies = list(re.finditer(pattern, current))
    if len(policies) != 1 or "default-src 'none'" not in policies[0][1] or 'script-src' in policies[0][1]:
        raise ValueError('Unexpected HTTPS policy')
    policy = policies[0][1] + "; script-src 'self'; connect-src https://" + str(address)
    current = re.sub(pattern, lambda _: 'add_header Content-Security-Policy "' + policy + '" always;', current)
    additions = '''
    location = /api/journal-feedback/sign-in.html {
        auth_basic "Birdynator Journal reviews";
        auth_basic_user_file /etc/nginx/journal-feedback.htpasswd;
        limit_req zone=journal_review_rate burst=5 nodelay;
        limit_req_status 429;
        alias /opt/birdynator-journal-feedback/journal-review-sign-in.html;
        add_header Cache-Control "no-store" always;
        add_header Content-Security-Policy "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'" always;
    }
    location = /journal-feedback.js {
        alias /opt/birdynator-journal-feedback/journal_feedback/journal-feedback.js;
        default_type application/javascript;
        add_header X-Content-Type-Options nosniff always;
    }
    location ^~ /api/journal-feedback/ {
        auth_basic "Birdynator Journal reviews";
        auth_basic_user_file /etc/nginx/journal-feedback.htpasswd;
        limit_req zone=journal_review_rate burst=5 nodelay;
        limit_req_status 429;
        client_max_body_size 32k;
        client_body_timeout 10s;
        proxy_request_buffering on;
        proxy_connect_timeout 3s;
        proxy_read_timeout 25s;
        proxy_send_timeout 10s;
        proxy_http_version 1.1;
        proxy_set_header Connection close;
        proxy_set_header Remote-User $remote_user;
        proxy_set_header Authorization "";
        proxy_pass http://unix:/run/journal-feedback/feedback.sock;
    }
'''
    if not current.rstrip().endswith('}'):
        raise ValueError('Unexpected nginx structure')
    return current.rstrip()[:-1] + additions + '}\n'


def service_config(address, reviewer):
    if str(UUID(reviewer)) != reviewer:
        raise ValueError('Invalid reviewer identity')
    parsed = ipaddress.IPv4Address(address)
    if not parsed.is_private or parsed.is_loopback or parsed.is_unspecified or parsed.is_multicast or parsed.is_link_local:
        raise ValueError('Expected reserved LAN address')
    return {'origin': 'https://' + str(parsed), 'reviewers': {'personal': reviewer},
            'socket_path': '/run/journal-feedback/feedback.sock',
            'queue_path': '/var/lib/journal-feedback/queue.sqlite'}


def session_configuration(current):
    if ('location ^~ /api/journal-feedback/' not in current
            or 'proxy_set_header Remote-User $remote_user;' not in current
            or 'location = /api/journal-feedback/session' in current):
        raise ValueError('Expected reviewed feedback configuration without session probe')
    additions = '''
    location = /api/journal-feedback/session {
        auth_basic "Birdynator Journal reviews";
        auth_basic_user_file /etc/nginx/journal-feedback.htpasswd;
        limit_req zone=journal_session_rate burst=5 nodelay;
        limit_req_status 429;
        error_page 401 = @journal_signed_out;
        limit_except GET { deny all; }
        proxy_connect_timeout 3s;
        proxy_read_timeout 10s;
        proxy_set_header Remote-User $remote_user;
        proxy_set_header Authorization "";
        proxy_pass http://unix:/run/journal-feedback/feedback.sock:/api/journal-feedback/context;
    }
    location @journal_signed_out {
        internal;
        default_type application/json;
        add_header Cache-Control "no-store" always;
        return 200 '{"signed_in":false}';
    }
'''
    if not current.rstrip().endswith('}'):
        raise ValueError('Unexpected feedback nginx structure')
    return current.rstrip()[:-1] + additions + '}\n'
