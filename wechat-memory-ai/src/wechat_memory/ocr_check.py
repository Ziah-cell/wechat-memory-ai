"""Local Windows OCR rehearsal using only built-in, in-memory synthetic images."""
import argparse
import json
import os
from pathlib import Path
import subprocess


PROVIDER = Path(__file__).with_name('ocr_synthetic.ps1')
CHECKS = ('light', 'dark', 'large')
FIELDS = ('chinese_duplicates_match', 'latin_exact_match', 'line_count_match')
STATUSES = frozenset({'passed', 'recognition_mismatch', 'language_unavailable', 'ocr_unavailable'})


def _report(status):
    return dict(schema_version=1, status=status, chinese_available=False,
                checks={key: {field: False for field in FIELDS} for key in CHECKS}, synthetic_only=True,
                screen_captured=False, real_chat_read=False, network_used=False,
                identity_verified=False, listener_ready=False, real_send_supported=False)


def sanitize_report(raw):
    invalid = _report('invalid_check_output')
    if not isinstance(raw, dict):
        return invalid
    if type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        return invalid
    status, available, checks = raw.get('status'), raw.get('chinese_available'), raw.get('checks')
    if not isinstance(status, str) or status not in STATUSES or type(available) is not bool:
        return invalid
    if not isinstance(checks, dict) or set(checks) != set(CHECKS):
        return invalid
    for fields in checks.values():
        if not isinstance(fields, dict) or set(fields) != set(FIELDS):
            return invalid
        if any(type(value) is not bool for value in fields.values()):
            return invalid
    values = [value for fields in checks.values() for value in fields.values()]
    if status in ('passed', 'recognition_mismatch'):
        if not available or (status == 'passed') != all(values):
            return invalid
    elif available or any(values):
        return invalid
    result = _report(status)
    result.update(chinese_available=available, checks={key: dict(fields) for key, fields in checks.items()})
    return result


def check(timeout=15):
    """No file, window, arbitrary text, configuration or credential input."""
    if os.name != 'nt':
        return _report('unsupported_platform')
    if type(timeout) not in (int, float) or not 0.5 <= timeout <= 30:
        return _report('invalid_arguments')
    shell = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                         'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    try:
        result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(PROVIDER)],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            return _report('check_failed')
        if len(result.stdout) > 65536:
            return _report('invalid_check_output')
        return sanitize_report(json.loads(result.stdout.decode('utf-8-sig')))
    except subprocess.TimeoutExpired:
        return _report('check_timeout')
    except (UnicodeError, ValueError, RecursionError):
        return _report('invalid_check_output')
    except OSError:
        return _report('check_failed')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Synthetic local OCR check; no screen or chat access.')
    parser.parse_args(argv)
    report = check()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report['status'] == 'passed' else 3


if __name__ == '__main__':
    raise SystemExit(main())
