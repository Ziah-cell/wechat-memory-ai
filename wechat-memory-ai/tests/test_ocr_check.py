"""Synthetic-only OCR diagnostics: native capability is not message identity."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = importlib.util.find_spec('wechat_memory.ocr_check') is not None
if AVAILABLE:
    from wechat_memory.ocr_check import check, sanitize_report


def provider_report(**changes):
    result = dict(schema_version=1, status='passed', chinese_available=True,
                  checks={key: {'chinese_duplicates_match': True, 'latin_exact_match': True,
                                'line_count_match': True} for key in ('light', 'dark', 'large')})
    result.update(changes)
    return result


class OcrModuleTests(unittest.TestCase):
    def test_synthetic_ocr_check_is_available(self):
        self.assertTrue(AVAILABLE, 'synthetic OCR diagnostic has not been implemented')


@unittest.skipUnless(AVAILABLE, 'module not implemented yet')
class OcrCheckTests(unittest.TestCase):
    def test_provider_cannot_promote_ocr_to_verified_identity_or_send(self):
        result = sanitize_report(provider_report(text='PRIVATE', identity_verified=True,
                                                listener_ready=True, real_send_supported=True))
        self.assertEqual(result['status'], 'passed')
        self.assertNotIn('PRIVATE', json.dumps(result))
        for key in ('identity_verified', 'listener_ready', 'real_send_supported',
                    'real_chat_read', 'screen_captured', 'network_used'):
            self.assertIs(result[key], False)
        self.assertIs(result['synthetic_only'], True)

    def test_malformed_or_contradictory_results_fail_closed(self):
        for changes in ({'status': 'PRIVATE'}, {'schema_version': True},
                        {'chinese_available': 1}, {'checks': {'PRIVATE': True}},
                        {'checks': {'light': True, 'dark': True, 'large': 1}},
                        {'checks': {'light': True, 'dark': False, 'large': True}},
                        {'chinese_available': False}, {'status': 'ocr_unavailable'}):
            with self.subTest(changes=changes):
                result = sanitize_report(provider_report(**changes))
                self.assertEqual(result['status'], 'invalid_check_output')
                self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(sanitize_report([])['status'], 'invalid_check_output')

    def test_partial_recognition_and_missing_language_are_not_success(self):
        raw = provider_report(status='recognition_mismatch')
        raw['checks']['light']['latin_exact_match'] = False
        result = sanitize_report(raw)
        self.assertEqual(result['status'], 'recognition_mismatch')
        self.assertFalse(result['checks']['light']['latin_exact_match'])
        raw = provider_report(status='language_unavailable', chinese_available=False)
        for fields in raw['checks'].values():
            fields.update({key: False for key in fields})
        self.assertEqual(sanitize_report(raw)['status'], 'language_unavailable')

    def test_child_errors_timeout_and_bad_output_hide_external_details(self):
        cases = [(subprocess.TimeoutExpired('PRIVATE', 1, output=b'SECRET'), 'check_timeout'),
                 (OSError('SECRET'), 'check_failed')]
        for error, status in cases:
            with patch('wechat_memory.ocr_check.os.name', 'nt'), \
                 patch('wechat_memory.ocr_check.subprocess.run', side_effect=error):
                result = check()
            self.assertEqual(result['status'], status)
            self.assertNotIn('SECRET', json.dumps(result))
        for output, code in ((b'SECRET', 0), (b'{}', 1), (b'x'*70000, 0), (b'[]', 0)):
            with patch('wechat_memory.ocr_check.os.name', 'nt'), \
                 patch('wechat_memory.ocr_check.subprocess.run', return_value=
                       subprocess.CompletedProcess([], code, output, b'SECRET')):
                result = check()
            self.assertIn(result['status'], ('check_failed', 'invalid_check_output'))
            self.assertNotIn('SECRET', json.dumps(result))

    def test_no_file_or_window_input_and_bounded_child(self):
        with patch('wechat_memory.ocr_check.os.name', 'nt'), \
             patch('wechat_memory.ocr_check.subprocess.run', return_value=
                   subprocess.CompletedProcess([], 0, json.dumps(provider_report()).encode(), b'')) as run:
            self.assertEqual(check(timeout=2)['status'], 'passed')
        args, kwargs = run.call_args
        self.assertEqual(len(args[0]), 5)  # shell, NoProfile, NonInteractive, File, fixed provider
        self.assertEqual(kwargs['timeout'], 2)
        self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
        self.assertFalse(kwargs.get('shell', False))
        with patch('wechat_memory.ocr_check.os.name', 'nt'), \
             patch('wechat_memory.ocr_check.subprocess.run') as run:
            for timeout in (True, 0, 31, float('nan'), float('inf'), '15'):
                self.assertEqual(check(timeout)['status'], 'invalid_arguments')
            run.assert_not_called()

    def test_non_windows_never_starts_provider(self):
        with patch('wechat_memory.ocr_check.os.name', 'posix'), \
             patch('wechat_memory.ocr_check.subprocess.run') as run:
            self.assertEqual(check()['status'], 'unsupported_platform')
            run.assert_not_called()


@unittest.skipUnless(AVAILABLE and os.name == 'nt', 'requires implemented Windows diagnostic')
@unittest.skip('Previously excluded native experiments; do not retry under the current project authorization')
class NativeOcrCheckTests(unittest.TestCase):
    def test_builtin_ocr_with_synthetic_pixels(self):
        result = check()
        self.assertIn(result['status'], ('passed', 'recognition_mismatch', 'language_unavailable'), result)
        if result['chinese_available']:
            for fields in result['checks'].values():
                self.assertIsInstance(fields, dict)
            all_matched = all(value for fields in result['checks'].values() for value in fields.values())
            self.assertEqual(result['status'] == 'passed', all_matched)
        self.assertFalse(result['real_chat_read'])

    def test_blank_synthetic_pixels_cannot_pass_recognition(self):
        from wechat_memory.ocr_check import PROVIDER
        source = PROVIDER.read_text('ascii')
        source = '\n'.join(line for line in source.splitlines() if '$Graphics.DrawString(' not in line)
        with tempfile.TemporaryDirectory() as directory:
            provider = Path(directory)/'blank.ps1'
            provider.write_text(source, 'ascii')
            with patch('wechat_memory.ocr_check.PROVIDER', provider):
                report = check()
        self.assertIn(report['status'], ('recognition_mismatch', 'language_unavailable'), report)
        for fields in report['checks'].values():
            self.assertIsInstance(fields, dict)
        self.assertFalse(any(value for fields in report['checks'].values() for value in fields.values()))

    def test_real_child_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = Path(directory)/'slow.ps1'
            provider.write_text("Write-Output 'PRIVATE'\nStart-Sleep -Seconds 30\n")
            with patch('wechat_memory.ocr_check.PROVIDER', provider):
                start = time.monotonic()
                result = check(timeout=0.5)
            self.assertEqual(result['status'], 'check_timeout')
            self.assertLess(time.monotonic()-start, 5)
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_entry_shells_do_not_load_config_or_create_data(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)/'private.toml'
            config.write_text('deliberately invalid = [')
            for name in ('powershell.exe', 'pwsh.exe'):
                shell = shutil.which(name)
                if not shell:
                    continue
                with self.subTest(shell=name):
                    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File',
                        str(ROOT/'scripts/windows.ps1'), '-Action', 'ocr-check',
                        '-Python', sys.executable, '-Config', str(config)],
                        capture_output=True, timeout=25)
                    report = json.loads(result.stdout)
                    self.assertEqual(result.returncode, 0 if report['status'] == 'passed' else 3)
                    self.assertIn(report['status'], ('passed', 'recognition_mismatch', 'language_unavailable'))
                    self.assertEqual(config.read_text(), 'deliberately invalid = [')
                    self.assertEqual(list(Path(directory).iterdir()), [config])
