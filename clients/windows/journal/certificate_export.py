"""Explicit private-folder certificate exports. No trust, network or deployment actions."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess

import certificates

ACL_CHECK = r'''
$ErrorActionPreference = 'Stop'
$path = $env:JOURNAL_TLS_PRIVATE_DIRECTORY
$item = Get-Item -LiteralPath $path -Force
$cursor = $item
while ($cursor) {
    if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point in certificate path' }
    $cursor = $cursor.Parent
}
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$acl = Get-Acl -LiteralPath $path
$owner = ([Security.Principal.NTAccount]::new($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
$rules = @($acl.Access | ForEach-Object {
    @{sid=$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value;
      type=$_.AccessControlType.ToString(); inherited=$_.IsInherited}
})
@{owner=$owner; user=$sid; protected=$acl.AreAccessRulesProtected; rules=$rules} | ConvertTo-Json -Depth 4 -Compress
'''


def check_private_directory(path):
    path = Path(path)
    if os.name != 'nt':
        raise ValueError('Use the reviewed Windows preparation workflow')
    if not path.is_dir() or path.is_symlink():
        raise ValueError('Certificate output must be a pre-protected directory')
    # PowerShell 7 module paths can prevent Windows PowerShell's built-in ACL
    # module from loading. Let the child use its own default module paths.
    environment = {key: value for key, value in os.environ.items() if key.upper() != 'PSMODULEPATH'}
    environment['JOURNAL_TLS_PRIVATE_DIRECTORY'] = str(path.absolute())
    result = subprocess.run(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', ACL_CHECK],
                            env=environment,
                            check=True, capture_output=True, text=True)
    acl = json.loads(result.stdout)
    if not acl['protected'] or acl['owner'] != acl['user'] or not acl['rules']:
        raise ValueError('Certificate directory ownership or inheritance needs review')
    if any(rule['sid'] != acl['user'] or rule['type'] != 'Allow' or rule['inherited'] for rule in acl['rules']):
        raise ValueError('Only the current Windows user may have explicit directory access')


def write_bundle(path, files, manifest, passphrase, guard=check_private_directory):
    """Never overwrite an export; retain any partial folder for deliberate inspection."""
    path = Path(path)
    guard(path)
    if any(path.iterdir()):
        raise ValueError('Output directory is not empty; preserve the existing material')
    certificates.verify_material(files, manifest, passphrase)
    backup = certificates.authority_backup(files, manifest, passphrase)
    certificates.restore_authority(backup, passphrase, manifest['authority_sha256'])
    packet = dict(manifest, export_status='incomplete')
    marker = path / 'manifest.json'
    def exclusive(destination, data):
        with destination.open('xb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    exclusive(marker, json.dumps(packet, indent=2).encode())
    for name in ('authority', 'utility', 'device-trust'):
        (path / name).mkdir()
    for name in certificates.AUTHORITY_FILES:
        exclusive(path / 'authority' / name, files[name])
    exclusive(path / 'authority' / 'journal-authority-backup.json', backup)
    for name in certificates.SERVER_FILES:
        exclusive(path / 'utility' / name, files[name])
    for name in certificates.AUTHORITY_FILES[1:]:
        exclusive(path / 'device-trust' / name, files[name])
    # Reload and verify exact exported bytes before declaring the export complete.
    reloaded = {name: (path / ('authority' if name in certificates.AUTHORITY_FILES else 'utility') / name).read_bytes() for name in files}
    certificates.verify_material(reloaded, manifest, passphrase)
    if (path / 'authority' / 'journal-authority-backup.json').read_bytes() != backup:
        raise ValueError('Backup export differs')
    packet['export_status'] = 'complete'
    temporary = path / 'manifest.complete.tmp'
    exclusive(temporary, json.dumps(packet, indent=2).encode())
    temporary.replace(marker)
    return packet


def load_bundle(path, passphrase, guard=check_private_directory):
    path = Path(path)
    guard(path)
    packet = json.loads((path / 'manifest.json').read_text())
    if packet.get('export_status') != 'complete':
        raise ValueError('Certificate export is incomplete; inspect before using it')
    files = {}
    for name in certificates.AUTHORITY_FILES + certificates.SERVER_FILES:
        source = path / ('authority' if name in certificates.AUTHORITY_FILES else 'utility') / name
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 20000:
            raise ValueError('Unexpected certificate file')
        files[name] = source.read_bytes()
    certificates.verify_material(files, packet, passphrase)
    return files, packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--new-address', help='reviewed reserved Utility LAN IPv4 address')
    choice.add_argument('--renew-from', type=Path, help='complete prior private export; issuer and address stay fixed')
    args = parser.parse_args()
    check_private_directory(args.output)
    if any(args.output.iterdir()):
        raise ValueError('Output already contains files; nothing overwritten')
    print('Enter the authority passphrase from your password manager. It is not logged or stored.', flush=True)
    password = getpass.getpass('Authority passphrase: ').encode('utf-8')
    if args.new_address:
        confirmation = getpass.getpass('Confirm authority passphrase: ').encode('utf-8')
        if password != confirmation:
            raise ValueError('Passphrases differ; no material exported')
        files, manifest = certificates.material(args.new_address, password)
    else:
        previous, manifest = load_bundle(args.renew_from, password)
        files, manifest = certificates.renew(previous, manifest, password)
    write_bundle(args.output, files, manifest, password)
    print('Private export verified. Authority SHA-256: ' + manifest['authority_sha256'])
    print('Server expires: ' + manifest['server_expires'])
    print('Only utility/ may be uploaded to Utility. Only device-trust/ contains device trust files.')
    print('Back up authority/journal-authority-backup.json separately and retain the fingerprint and password-manager entry.')
    print('No trust installed, files uploaded, firewall changed or service restarted.')


if __name__ == '__main__':
    main()
