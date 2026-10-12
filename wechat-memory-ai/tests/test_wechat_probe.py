"""Read-only probe contract, privacy, failure and real Windows UIA checks."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from wechat_memory.wechat_probe import probe, sanitize_report


ROOT = Path(__file__).resolve().parents[1]
SHELLS = [p for name in ('powershell.exe', 'pwsh.exe') if (p := shutil.which(name))]


def raw_report(**changes):
    data = dict(schema_version=1, status='structure_observed', client_version='4.1.15.13',
                process_count=1, window_count=1, nodes=3, onscreen_nodes=2,
                control_types={'50032': 1, '50000': 2}, limited=False)
    data.update(changes)
    return data


class ProbeTests(unittest.TestCase):
    def test_output_allowlist_never_promotes_structure_to_identity(self):
        raw = raw_report(name='PRIVATE', text='SECRET', runtime_id=[42],
                         identity_verified=True, real_send_supported=True)
        result = sanitize_report(raw)
        self.assertEqual(result['status'], 'structure_observed')
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('runtime_id', result)
        self.assertFalse(result['identity_verified'])
        self.assertFalse(result['real_send_supported'])
        self.assertFalse(result['listener_ready'])
        self.assertEqual(result['login_state'], 'unverified')

    def test_malformed_and_sensitive_provider_fields_fail_closed(self):
        for changes in ({'status': 'PRIVATE'}, {'client_version': 'SECRET'},
                        {'nodes': True}, {'nodes': -1}, {'nodes': 999999},
                        {'onscreen_nodes': 4}, {'control_types': {'PRIVATE': 3}},
                        {'control_types': {'50000': True}}, {'control_types': {'50000': 2}},
                        {'limited': 'false'}, {'schema_version': 2},
                        {'window_count': 2}, {'process_count': 0}):
            with self.subTest(changes=changes):
                result = sanitize_report(raw_report(**changes))
                self.assertEqual(result['status'], 'invalid_probe_output')
                self.assertNotIn('PRIVATE', json.dumps(result))
                self.assertNotIn('SECRET', json.dumps(result))

    def test_timeout_and_provider_errors_discard_external_details(self):
        errors = [subprocess.TimeoutExpired('PRIVATE', 1, output=b'SECRET'),
                  OSError('SECRET')]
        for error in errors:
            with patch('wechat_memory.wechat_probe.os.name', 'nt'), \
                 patch('wechat_memory.wechat_probe.subprocess.run', side_effect=error):
                result = probe('D:/private/Weixin.exe')
                self.assertIn(result['status'], ('probe_timeout', 'probe_failed'))
                self.assertNotIn('SECRET', json.dumps(result))

    def test_child_is_bounded_and_uses_literal_arguments(self):
        completed = subprocess.CompletedProcess([], 0, json.dumps(raw_report()).encode(), b'SECRET')
        with patch('wechat_memory.wechat_probe.os.name', 'nt'), \
             patch('wechat_memory.wechat_probe.subprocess.run', return_value=completed) as run:
            result = probe('D:/space & quote/Weixin.exe', timeout=3)
        self.assertEqual(result['status'], 'structure_observed')
        args, kwargs = run.call_args
        self.assertIn('D:/space & quote/Weixin.exe', args[0])
        self.assertEqual(kwargs['timeout'], 3)
        self.assertFalse(kwargs.get('shell', False))
        self.assertIn('-NonInteractive', args[0])
        self.assertIn('-NoProfile', args[0])
        self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)

    def test_bad_child_exit_json_or_oversize_is_sanitized(self):
        for output, code in ((b'SECRET', 0), (b'{}', 1), (b'x'*70000, 0), (b'[]', 0)):
            completed = subprocess.CompletedProcess([], code, output, b'SECRET')
            with patch('wechat_memory.wechat_probe.os.name', 'nt'), \
                 patch('wechat_memory.wechat_probe.subprocess.run', return_value=completed):
                result = probe('D:/private/Weixin.exe')
            self.assertIn(result['status'], ('probe_failed', 'invalid_probe_output'))
            self.assertNotIn('SECRET', json.dumps(result))

    def test_non_windows_never_starts_provider(self):
        with patch('wechat_memory.wechat_probe.os.name', 'posix'), \
             patch('wechat_memory.wechat_probe.subprocess.run') as run:
            self.assertEqual(probe('Weixin.exe')['status'], 'unsupported_platform')
            run.assert_not_called()


@unittest.skipUnless(os.name == 'nt' and SHELLS, 'requires Windows PowerShell')
@unittest.skip('Previously excluded native experiments; do not retry under the current project authorization')
class NativeProbeTests(unittest.TestCase):
    def test_actual_child_timeout_is_terminated_without_forwarding_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'slow.ps1'
            path.write_text("param([string]$ClientPath)\nWrite-Output 'PRIVATE'\nStart-Sleep -Seconds 30\n")
            with patch('wechat_memory.wechat_probe.PROVIDER', path):
                started = time.monotonic()
                report = probe('Weixin.exe', timeout=0.5)
            self.assertEqual(report['status'], 'probe_timeout')
            self.assertLess(time.monotonic()-started, 5)
            self.assertNotIn('PRIVATE', json.dumps(report))

    def test_provider_process_path_scope_with_synthetic_executable(self):
        # A temporary invisible test app, never the installed WeChat client.
        fixture = r'''
using System;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
[assembly: AssemblyFileVersion("9.9.9.9")]
public static class Fixture {
    [STAThread] public static void Main(string[] args) {
        Form form = new Form();
        form.Text = "PRIVATE-NAME";
        form.Opacity = 0;
        form.ShowInTaskbar = true;
        Button button = new Button();
        button.Text = "SECRET-BODY";
        form.Controls.Add(button);
        form.Shown += delegate { File.WriteAllText(args[0], "ready"); };
        Application.Run(form);
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='uia fixture ') as directory:
            directory = Path(directory)
            exe, source, marker = directory/'Weixin.exe', directory/'fixture.cs', directory/'ready'
            source.write_text(fixture, 'utf-8')
            ps = directory/'compile.ps1'
            ps.write_text("param($Source, $Output)\n$ErrorActionPreference='Stop'\n"
                          "Add-Type -Path $Source -ReferencedAssemblies System.Windows.Forms "
                          "-OutputAssembly $Output -OutputType WindowsApplication\n")
            built = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
                                    '-File', str(ps), str(source), str(exe)],
                                   capture_output=True, timeout=20)
            self.assertEqual(built.returncode, 0, built.stderr.decode('utf-8', 'replace'))
            process = subprocess.Popen([str(exe), str(marker)], stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic()+5
                while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(marker.exists(), 'synthetic window failed to initialize')
                result = probe(str(exe))
                self.assertEqual(result['status'], 'structure_observed', result)
                self.assertEqual(result['client_version'], '9.9.9.9')
                self.assertEqual(result['process_count'], 1)
                self.assertEqual(result['window_count'], 1)
                self.assertGreaterEqual(result['nodes'], 2)
                self.assertFalse(result['listener_ready'])
                self.assertNotIn('PRIVATE-NAME', json.dumps(result))
                self.assertNotIn('SECRET-BODY', json.dumps(result))
                # Same basename in a different path must not match this process.
                other = directory/'other'
                other.mkdir()
                shutil.copy2(exe, other/'Weixin.exe')
                self.assertEqual(probe(str(other/'Weixin.exe'))['status'], 'not_running')
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)

    def test_missing_client_both_entry_shells_no_config_or_data_created(self):
        with tempfile.TemporaryDirectory(prefix='wechat probe ') as directory:
            for shell in SHELLS:
                with self.subTest(shell=shell):
                    result = subprocess.run(
                        [shell, '-NoProfile', '-NonInteractive', '-File',
                         str(ROOT/'scripts/windows.ps1'), '-Action', 'probe-wechat',
                         '-Python', sys.executable, '-ClientPath', str(Path(directory)/'Weixin.exe'),
                         '-Config', str(Path(directory)/'never-create.toml')],
                        capture_output=True, timeout=25)
                    self.assertEqual(result.returncode, 3, result.stderr.decode('utf-8', 'replace'))
                    self.assertEqual(json.loads(result.stdout)['status'], 'client_not_found')
                    self.assertEqual(list(Path(directory).iterdir()), [])

    def test_native_tree_is_read_only_scoped_and_bounded_with_private_fixture(self):
        # UI data below is entirely fabricated; this test never opens WeChat.
        support = str(ROOT/'src/wechat_memory/uia_support.ps1').replace("'", "''")
        fixture = r'''
$ErrorActionPreference = 'Stop'
. '__SUPPORT__'
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = 'PRIVATE-NAME'
$panel = New-Object System.Windows.Forms.Panel
$panel.Dock = 'Fill'
$form.Controls.Add($panel)
$button = New-Object System.Windows.Forms.Button
$button.Text = 'SECRET-BODY'
$script:clicks = 0
$button.Add_Click({ $script:clicks++ })
$panel.Controls.Add($button)
try {
    $handle = $form.Handle
    $snapshot = [WechatReadOnly.TreeProbe]::Read($handle, $PID, 32, 8)
    $limited = [WechatReadOnly.TreeProbe]::Read($handle, $PID, 1, 8)
    $depth = [WechatReadOnly.TreeProbe]::Read($handle, $PID, 32, 0)
    $wrong = [WechatReadOnly.TreeProbe]::Read($handle, ($PID + 1), 32, 8)
    @{snapshot=$snapshot; limited=$limited; depth=$depth; wrong=$wrong; clicks=$script:clicks} | ConvertTo-Json -Depth 8 -Compress
} finally { $form.Dispose() }
'''.replace('__SUPPORT__', support)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fixture.ps1'
            path.write_text(fixture, encoding='utf-8-sig')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
                                     '-File', str(path)], capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        data = json.loads(result.stdout)
        self.assertGreaterEqual(data['snapshot']['Nodes'], 3)
        self.assertFalse(data['snapshot']['ScopeChanged'])
        self.assertEqual(data['limited']['Nodes'], 1)
        self.assertTrue(data['limited']['Limited'])
        self.assertEqual(data['depth']['Nodes'], 1)
        self.assertTrue(data['depth']['Limited'])
        self.assertTrue(data['wrong']['ScopeChanged'])
        self.assertEqual(data['wrong']['Nodes'], 0)
        self.assertEqual(data['clicks'], 0)
        self.assertNotIn(b'PRIVATE-NAME', result.stdout)
        self.assertNotIn(b'SECRET-BODY', result.stdout)
