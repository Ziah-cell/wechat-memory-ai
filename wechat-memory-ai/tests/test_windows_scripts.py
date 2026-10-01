"""Exercise real PowerShell entry points; no installed py launcher is required."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELLS = [p for name in ('powershell.exe', 'pwsh.exe') if (p := shutil.which(name))]


@unittest.skipUnless(os.name == 'nt' and SHELLS, 'requires Windows PowerShell')
class WindowsScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wechat scripts ')
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name)/'existing config.toml'
        self.original = (ROOT/'config.example.toml').read_bytes()
        self.config.write_bytes(self.original)

    def invoke(self, shell, script='windows.ps1', *args, python=None):
        return subprocess.run(
            [shell, '-NoProfile', '-NonInteractive', '-File', str(ROOT/'scripts'/script),
             '-Python', python or sys.executable, '-Config', str(self.config), *args],
            capture_output=True, timeout=20)

    def test_explicit_python_runs_diagnose_and_preserves_existing_config(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.invoke(shell, 'windows.ps1', '-Action', 'diagnose')
                self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
                data = json.loads(result.stdout)
                self.assertEqual(data['adapter'], 'mock')
                self.assertFalse(data['network_enabled'])
                self.assertFalse(data['real_send_supported'])
                self.assertEqual(self.config.read_bytes(), self.original)

    def test_diagnostic_wrapper_propagates_config_error_exit_code(self):
        self.config.write_text('[app]\nreal_send = true\n', 'utf-8')
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.invoke(shell, 'diagnose-windows.ps1')
                self.assertEqual(result.returncode, 2, result.stderr.decode('utf-8', 'replace'))
                self.assertIn(b'config_error', result.stderr)

    def test_invalid_explicit_python_fails_without_fallback_or_config_change(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.invoke(shell, 'windows.ps1', '-Action', 'diagnose',
                                     python=str(Path(self.tmp.name)/'absent python.exe'))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.config.read_bytes(), self.original)

    def test_offline_check_ignores_personal_config_and_keeps_it_unchanged(self):
        self.config.write_text('[app]\nreal_send = true\nPRIVATE-MARKER\n', 'utf-8')
        original = self.config.read_bytes()
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.invoke(shell, 'windows.ps1', '-Action', 'offline-check')
                self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
                report = json.loads(result.stdout)
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(report['source'], 'synthetic_callbacks')
                self.assertFalse(report['network_enabled'])
                self.assertFalse(report['real_wechat_verified'])
                self.assertNotIn(b'PRIVATE-MARKER', result.stdout+result.stderr)
                self.assertEqual(self.config.read_bytes(), original)

    def test_broken_venv_falls_back_to_working_python(self):
        project = Path(self.tmp.name)/'isolated project'
        scripts = project/'scripts'
        scripts.mkdir(parents=True)
        for name in ('windows.ps1', 'run.py'):
            shutil.copy2(ROOT/'scripts'/name, scripts/name)
        environment = project/'.venv'
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(environment)],
                       capture_output=True, check=True, timeout=20)
        metadata = environment/'pyvenv.cfg'
        metadata.write_text('home = '+str(project/'missing runtime')+'\n', 'utf-8')
        env = dict(os.environ, WECHAT_MEMORY_PYTHON='', PYTHONPATH=str(ROOT/'src'))
        env['PATH'] = str(Path(sys.executable).parent)+os.pathsep+env.get('PATH', '')
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = subprocess.run(
                    [shell, '-NoProfile', '-NonInteractive', '-File', str(scripts/'windows.ps1'),
                     '-Config', str(self.config), '-Action', 'diagnose'],
                    env=env, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
                self.assertEqual(json.loads(result.stdout)['adapter'], 'mock')
