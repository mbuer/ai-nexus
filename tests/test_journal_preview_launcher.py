"""Exercise Windows PowerShell transport with a stub SSH; no network/model request."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class LauncherTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows PowerShell transport integration')
    def test_quote_free_transport_and_attempt_guard(self):
        root = Path(__file__).resolve().parents[4]
        launcher = root / 'Run-Journal-Preview-Today.ps1'
        # This integration test belongs to the local reviewed package; the public
        # source checkout can run the remaining tests without the operator wrapper.
        if not launcher.is_file():
            self.skipTest('Local operator launcher not present')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            shutil.copyfile(launcher, folder / launcher.name)
            private = folder / 'outputs/journal-feedback-2026-10-12/private'
            private.mkdir(parents=True)
            code = folder / 'outputs/journal-feedback-2026-10-12/source/clients/windows/journal/manual_preview.py'
            code.parent.mkdir(parents=True)
            content = b'print("synthetic transport test only")\n'
            code.write_bytes(content)
            harness = folder / 'test.ps1'
            harness.write_text('''$ErrorActionPreference='Stop'
function ssh { $global:journalTestSeen=@($args); $global:LASTEXITCODE=0 }
& (Join-Path $PSScriptRoot 'Run-Journal-Preview-Today.ps1') -RunApproved
$global:journalTestSeen | ConvertTo-Json | Set-Content (Join-Path $PSScriptRoot 'captured.json')
''', encoding='utf-8')
            environment = dict(os.environ)
            environment.pop('PSModulePath', None)
            executable = Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
            command = [str(executable), '-NoProfile', '-ExecutionPolicy', 'RemoteSigned', '-File', str(harness)]
            subprocess.run(command, env=environment, capture_output=True, check=True, timeout=30)
            arguments = json.loads((folder / 'captured.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(arguments[:2], ['-t', 'ai-nexus'])
            remote = arguments[2]
            self.assertTrue(remote.startswith('printf %s '))
            self.assertIn(' | base64 --decode | podman exec -i ', remote)
            self.assertFalse(any(character in remote for character in "'\"()"))
            encoded = remote.split()[2]
            self.assertEqual(base64.b64decode(encoded), content)
            repeated = subprocess.run(command, env=environment, capture_output=True, timeout=30)
            self.assertNotEqual(repeated.returncode, 0, 'Ambiguous repeats must stop before SSH')
