"""Persistent, locally controlled observation. Candidates never leave this module.

This is not the supervised PreflightSession and cannot authorize a reply. It
counts unverified UI occurrences, including potential history synchronization.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from .live_read import NativeReader, ReadError, VisualOccurrenceSession, SelectionOccurrenceSession, _STOP_REASONS
from .runtime import AlreadyRunning, Controller, InstanceLock, atomic_json, runtime_status, send_control


_COUNTS = ('snapshots', 'incoming_candidates', 'filtered_self_texts',
           'filtered_unknown_texts', 'snapshot_change_retries', 'minimized_snapshots')
_PHASES = frozenset({'starting', 'waiting_baseline', 'observing', 'stopped', 'busy'})
_REASONS = _STOP_REASONS | frozenset({'requested', 'already_running', 'startup_failed',
                                    'startup_timeout', 'stop_pending', 'not_running', 'monitor_failed'})


def _public_status(raw):
    phase, reason = raw.get('phase'), raw.get('stop_reason')
    result = dict(mode='continuous_readonly_observation', active=raw.get('active') is True,
                  phase=phase if isinstance(phase,str) and phase in _PHASES else 'stopped',
                  stop_reason=reason if isinstance(reason,str) and reason in _REASONS else None,
                  baseline_ready=raw.get('baseline_ready') is True,
                  sender_verified=False, history_boundary_verified=False,
                  real_send_supported=False, model_called=False, memory_written=False,
                  minimized_supported=False, reply_ready=False)
    result['reader_mode'] = 'selection' if raw.get('reader_mode') == 'selection' else 'visual'
    result['minimized_observation_enabled'] = result['reader_mode'] == 'selection'
    result['window_minimized'] = raw.get('window_minimized') is True
    for key in _COUNTS:
        value = raw.get(key, 0)
        result[key] = value if type(value) is int and 0 <= value < 2**63 else 0
    return result


def monitor_status(directory):
    return _public_status(runtime_status(directory))


def run_monitor(client_path, directory, *, run_id=None, reader_mode='visual'):
    """Observe one current private window until stop or the first read failure.

    The first accepted snapshot is a baseline, never an arrival. No background
    rebind, history replay, model callback, or send operation is provided.
    """
    directory = Path(directory)
    if reader_mode not in ('visual','selection'):
        return 2
    if run_id is not None and not re.fullmatch(r'[a-f0-9]{32}', run_id):
        return 2
    try:
        with InstanceLock(directory):
            controller = Controller(directory)
            if run_id is not None:
                controller.run_id = run_id
            session = SelectionOccurrenceSession() if reader_mode == 'selection' else VisualOccurrenceSession()
            reader = None
            counts = dict.fromkeys(_COUNTS, 0)
            counts['baseline_ready'] = False
            counts['reader_mode'] = reader_mode
            counts['window_minimized'] = False

            def publish(phase, reason=None):
                atomic_json(directory/'runtime.json', dict(pid=os.getpid(), run_id=controller.run_id,
                            phase=phase, stop_reason=reason, **counts))

            def stopped():
                return controller.poll() == 'stop'

            publish('starting')
            reason, code = 'requested', 0
            try:
                with NativeReader(client_path) as reader:
                    while True:
                        if stopped():
                            break
                        raw = reader.read_selection_text() if reader_mode == 'selection' else reader.read(visual_text=True)
                        if stopped():
                            break
                        observations = session.accept(raw)
                        progress = session.report()
                        counts['snapshots'] = progress['snapshots']
                        counts['baseline_ready'] = progress['status'] == 'reading'
                        counts['window_minimized'] = raw.get('minimized') is True
                        counts['minimized_snapshots'] += int(counts['window_minimized'])
                        counts['incoming_candidates'] += sum(item.direction == 'incoming_candidate' for item in observations)
                        counts['filtered_self_texts'] += sum(item.direction == 'self_candidate' for item in observations)
                        counts['filtered_unknown_texts'] += sum(item.direction == 'unknown' for item in observations)
                        counts['snapshot_change_retries'] = reader.snapshot_change_retries
                        # Only fixed counters survive the iteration or reach disk.
                        del raw, observations
                        publish('observing' if counts['baseline_ready'] else 'waiting_baseline')
                        for _ in range(10):
                            if stopped():
                                publish('stopped', 'requested')
                                return 0
                            time.sleep(.1)
            except KeyboardInterrupt:
                reason = 'interrupted'
            except ReadError as error:
                reason = str(error)
                if reason == 'read_session_stopped':
                    reason = session.report()['stop_reason']
                if reason not in _STOP_REASONS:
                    reason = 'read_failed'
                code = 3
            except Exception:
                reason, code = 'read_failed', 3
            finally:
                if reader is not None:
                    counts['snapshot_change_retries'] = reader.snapshot_change_retries
                publish('stopped', reason)
            return code
    except AlreadyRunning:
        return 3


def _start(client_path, directory, *, reader_mode='visual'):
    directory = Path(directory).resolve()
    if runtime_status(directory)['active']:
        return 3, dict(monitor_status(directory), stop_reason='already_running')
    # A local generation token lets this launcher distinguish its own child
    # from a simultaneous competing launch; it is not an identity credential.
    token = Controller(directory).run_id
    command = [sys.executable, '-X', 'utf8', '-m', 'wechat_memory.monitor',
               '--data-dir', str(directory), 'run', '--client-path', str(Path(client_path).resolve()),
               '--run-id', token, '--reader', reader_mode]
    env = dict(os.environ)
    source_root = str(Path(__file__).resolve().parent.parent)
    env['PYTHONPATH'] = source_root + (os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    options = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    else:
        options['start_new_session'] = True
    try:
        child = subprocess.Popen(command, **options)
    except OSError:
        return 3, dict(monitor_status(directory), stop_reason='startup_failed')
    deadline = time.monotonic()+45
    while time.monotonic() < deadline:
        raw = runtime_status(directory)
        if (raw.get('run_id') == token and raw['active']
                and raw.get('phase') in ('observing','waiting_baseline')):
            return 0, _public_status(raw)
        if child.poll() is not None:
            reason = raw.get('stop_reason') if raw.get('run_id') == token else 'startup_failed'
            return 3, dict(_public_status(raw), stop_reason=reason if reason in _REASONS else 'startup_failed')
        time.sleep(.1)
    # Only the process object just created can be terminated. Never act on a
    # pid from a stale runtime.json or stop a different generation's worker.
    child.terminate()
    child.wait(timeout=10)
    return 3, dict(monitor_status(directory), stop_reason='startup_timeout')


def _stop(directory):
    try:
        send_control(directory, 'stop')
    except ValueError:
        return 4, dict(monitor_status(directory), stop_reason='not_running')
    deadline = time.monotonic()+10
    while time.monotonic() < deadline:
        status = monitor_status(directory)
        if not status['active']:
            return 0, status
        time.sleep(.1)
    return 3, dict(monitor_status(directory), stop_reason='stop_pending')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Continuous read-only WeChat observation; no model, memory or replies.')
    parser.add_argument('--data-dir', default='data/listener', help='Local control/status directory; no chat text is saved.')
    actions = parser.add_subparsers(dest='action', required=True)
    for action in ('start', 'run'):
        item = actions.add_parser(action)
        item.add_argument('--client-path', required=True)
        item.add_argument('--reader', choices=('visual','selection'), default='visual',
                          help='selection reads multiselect labels without pixels, including minimized windows; candidates only.')
        if action == 'run':
            item.add_argument('--run-id', help=argparse.SUPPRESS)
    actions.add_parser('status')
    actions.add_parser('stop')
    args = parser.parse_args(argv)
    try:
        if args.action == 'start':
            code, status = _start(args.client_path, args.data_dir, reader_mode=args.reader)
        elif args.action == 'stop':
            code, status = _stop(args.data_dir)
        elif args.action == 'run':
            code = run_monitor(args.client_path, args.data_dir, run_id=args.run_id, reader_mode=args.reader)
            status = monitor_status(args.data_dir)
        else:
            code, status = 0, monitor_status(args.data_dir)
    except Exception:
        code, status = 3, _public_status(dict(phase='stopped', stop_reason='monitor_failed'))
    print(json.dumps(status, sort_keys=True), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
