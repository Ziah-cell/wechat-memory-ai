"""One-shot structural UIA diagnostic. Never a message/identity/send adapter."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


PROVIDER = Path(__file__).with_name('uia_probe.ps1')
STATUSES = frozenset({
    'client_not_found', 'invalid_client', 'not_running', 'process_unavailable',
    'no_window', 'ambiguous_window', 'structure_observed', 'empty_tree',
    'window_changed', 'uia_unavailable', 'probe_failed',
})


def _report(status):
    return dict(schema_version=1, status=status, client_version='', process_count=0,
                window_count=0, nodes=0, onscreen_nodes=0, control_types={}, limited=False,
                login_state='unverified', identity_verified=False,
                listener_ready=False, real_send_supported=False)


def sanitize_report(raw):
    """Allowlist only structural counts; never forward arbitrary provider strings."""
    invalid = _report('invalid_probe_output')
    if not isinstance(raw, dict):
        return invalid
    if type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        return invalid
    status = raw.get('status')
    if not isinstance(status, str) or status not in STATUSES:
        return invalid
    version = raw.get('client_version')
    if not isinstance(version, str) or not re.fullmatch(r'(?:\d{1,5}\.){3}\d{1,5}|', version):
        return invalid
    for key, bound in (('process_count', 64), ('window_count', 64),
                       ('nodes', 256), ('onscreen_nodes', 256)):
        if type(raw.get(key)) is not int or not 0 <= raw[key] <= bound:
            return invalid
    if raw['window_count'] > raw['process_count'] or raw['onscreen_nodes'] > raw['nodes']:
        return invalid
    if type(raw.get('limited')) is not bool:
        return invalid
    counts = raw.get('control_types')
    if not isinstance(counts, dict) or len(counts) > 41:
        return invalid
    for key, value in counts.items():
        if not isinstance(key, str) or not re.fullmatch(r'500(?:[0-3][0-9]|40)', key):
            return invalid
        if type(value) is not int or not 1 <= value <= 256:
            return invalid
    if sum(counts.values()) != raw['nodes']:
        return invalid
    if status in ('structure_observed', 'empty_tree'):
        if raw['window_count'] != 1 or raw['process_count'] < 1:
            return invalid
        if (status == 'structure_observed') != (raw['nodes'] > 1):
            return invalid
    elif raw['nodes'] or raw['limited']:
        return invalid
    result = _report(status)
    for key in ('client_version', 'process_count', 'window_count', 'nodes',
                'onscreen_nodes', 'control_types', 'limited'):
        result[key] = raw[key]
    return result


def probe(client_path, timeout=15):
    """Kill an unresponsive UIA subprocess; do not expose its stderr/exception."""
    if os.name != 'nt':
        return _report('unsupported_platform')
    if (not isinstance(client_path, str) or not client_path or '\0' in client_path
            or type(timeout) not in (int, float) or not 0.5 <= timeout <= 30):
        return _report('invalid_arguments')
    shell = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                         'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    try:
        result = subprocess.run(
            [shell, '-NoProfile', '-NonInteractive', '-File', str(PROVIDER),
             '-ClientPath', client_path],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            return _report('probe_failed')
        if len(result.stdout) > 65536:
            return _report('invalid_probe_output')
        return sanitize_report(json.loads(result.stdout.decode('utf-8-sig')))
    except subprocess.TimeoutExpired:
        return _report('probe_timeout')
    except (UnicodeError, ValueError, RecursionError):
        return _report('invalid_probe_output')
    except OSError:
        return _report('probe_failed')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only WeChat UIA structure probe; no messages or sends.')
    parser.add_argument('--client-path', required=True)
    args = parser.parse_args(argv)
    report = probe(args.client_path)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    # 0 only means some child controls were observed, never login/identity success.
    return 0 if report['status'] == 'structure_observed' else 3


if __name__ == '__main__':
    raise SystemExit(main())
