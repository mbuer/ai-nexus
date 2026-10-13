"""Validated initial HTTPS installation plan. This module makes no system changes."""
import ipaddress
import re

SITE = '/etc/nginx/sites-available/birdynator-journal-https'
ENABLED = '/etc/nginx/sites-enabled/birdynator-journal-https'
CERTIFICATE = '/etc/nginx/journal-tls/journal-server.crt'
KEY = '/etc/nginx/journal-tls/journal-server.key'


def plan(address, lan, interface, template):
    address = ipaddress.IPv4Address(address)
    network = ipaddress.IPv4Network(lan, strict=True)
    if (not address.is_private or address.is_loopback or address.is_link_local or address.is_multicast
            or address not in network or network.prefixlen < 24):
        raise ValueError('HTTPS requires the reviewed narrow LAN address/range')
    if not isinstance(interface, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}', interface):
        raise ValueError('Invalid host interface')
    substitutions = {'UTILITY_LAN_IP': str(address), 'HOME_LAN_CIDR': str(network),
                     'JOURNAL_SERVER_CERTIFICATE_PATH': CERTIFICATE,
                     'JOURNAL_SERVER_PRIVATE_KEY_PATH': KEY}
    for marker, value in substitutions.items():
        if marker not in template:
            raise ValueError('HTTPS template lacks expected marker')
        template = template.replace(marker, value)
    if f'listen {address}:443 ssl;' not in template or "default-src 'none'" not in template or 'proxy_pass' in template:
        raise ValueError('Initial HTTPS site must remain scoped and read-only')
    rule = ['in', 'on', interface, 'from', str(network), 'to', str(address), 'port', '443', 'proto', 'tcp']
    return {'schema_version': 'journal-https-install-plan-v1', 'origin': f'https://{address}',
            'new_config': SITE, 'new_enabled_link': ENABLED, 'config_text': template,
            'certificate_path': CERTIFICATE, 'key_path': KEY,
            'firewall_add': ['ufw', 'allow', *rule],
            'firewall_remove_if_added_by_this_installation': ['ufw', 'delete', 'allow', *rule],
            'checks_before_install': ['Current journal configuration unchanged', 'No unknown existing HTTPS site/files',
                                      'Reserved address/interface match inspection', 'Port 443 remains unused',
                                      'UFW active with original scoped rules', 'Server signature/address/expiry and key pair verified'],
            'checks_before_reload': ['Private server-key ownership and permissions', 'nginx -t succeeds'],
            'checks_after_reload': ['Verified TLS request to LAN address', 'Original HTTP journal works',
                                    'Stream Deck service remains reachable', 'Listener and firewall remain scoped'],
            'rollback': ['Remove only the new enabled link if it still matches this installation',
                         'Verify nginx syntax and reload original sites',
                         'Remove the exact new firewall rule only if this installation added it',
                         'Retain private certificate material and the installation receipt for inspection'],
            'unchanged': ['Existing HTTP journal config', 'Companion/Stream Deck', 'OPNsense', 'Ubuntu Infra',
                          'Household DNS/DHCP', 'AI Nexus networking', 'Database schema', 'Device trust stores'],
            'feedback_writes_enabled': False}
