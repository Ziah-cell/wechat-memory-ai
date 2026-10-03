"""Continuous read-only observation and generation-bound local controls."""
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from wechat_memory.live_read import ReadError
from wechat_memory.runtime import InstanceLock, atomic_json, send_control

ROOT = Path(__file__).resolve().parents[1]


def row(token, text='FICTIONAL_PRIVATE_TEXT', direction='incoming_candidate'):
    return dict(token=token, text=text, kind='text', direction=direction)


def snapshot(*rows, window=34):
    return dict(status='visual_text_snapshot', process=12, started='123456', window=window,
                root='ChatSingleWindowwxid_fixture', list_token='list', rows=list(rows))


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('wechat_memory.monitor'),
                             'continuous read-only monitor is not implemented')
        self.monitor = importlib.import_module('wechat_memory.monitor')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)/'observer'

    def run_frames(self, frames, *, stop_after=None):
        directory = self.directory
        calls = []
        cleaned = []
        sequence = iter(frames)
        class Reader:
            snapshot_change_retries = 0
            def __init__(self, client_path):
                self.client_path = client_path
            def __enter__(self):
                return self
            def __exit__(self, *args):
                cleaned.append(True)
            def read(self, *, visual_text=False):
                if not visual_text:
                    raise AssertionError('joint text/direction reading required')
                calls.append(True)
                value = next(sequence)
                if stop_after == len(calls):
                    send_control(directory, 'stop')
                if isinstance(value, BaseException):
                    raise value
                return value
        with patch.object(self.monitor, 'NativeReader', Reader), patch.object(self.monitor.time, 'sleep'):
            code = self.monitor.run_monitor('fixture.exe', self.directory)
        status = self.monitor.monitor_status(self.directory)
        serialized = json.dumps(status) + ''.join(path.read_text('utf-8') for path in self.directory.glob('*.json'))
        for private in ('FICTIONAL_PRIVATE_TEXT', 'wxid_fixture', 'list_token'):
            self.assertNotIn(private, serialized)
        self.assertEqual(cleaned, [True])
        self.assertFalse(status['active'])
        return code, status, len(calls)

    def test_baseline_skipped_duplicates_preserved_self_and_unknown_filtered(self):
        a, b = row('a'), row('b')
        own, first, second, unknown = row('s', direction='self_candidate'), row('c'), row('d'), row('u', direction='unknown')
        frames = [snapshot(a,b), snapshot(a,b), snapshot(a,b,own),
                  snapshot(a,b,own,first), snapshot(a,b,own,first,second),
                  snapshot(a,b,own,first,second,unknown), KeyboardInterrupt()]
        code, status, _ = self.run_frames(frames)
        self.assertEqual(code, 0)
        self.assertEqual(status['incoming_candidates'], 2)
        self.assertEqual(status['filtered_self_texts'], 1)
        self.assertEqual(status['filtered_unknown_texts'], 1)
        self.assertEqual(status['snapshots'], 6)
        self.assertEqual(status['stop_reason'], 'interrupted')
        self.assertFalse(status['sender_verified'])
        self.assertFalse(status['history_boundary_verified'])
        self.assertFalse(status['real_send_supported'])
        self.assertFalse(status['model_called'])
        self.assertFalse(status['memory_written'])

    def test_control_stop_during_read_discards_that_uncommitted_batch(self):
        a, b = row('a'), row('b')
        code, status, calls = self.run_frames([snapshot(a,b), snapshot(a,b,row('late'))], stop_after=2)
        self.assertEqual(code, 0)
        self.assertEqual(calls, 2)
        self.assertEqual(status['snapshots'], 1)
        self.assertEqual(status['incoming_candidates'], 0)
        self.assertEqual(status['stop_reason'], 'requested')

    def test_minimize_and_binding_change_stop_without_rebinding(self):
        for failure, reason in ((ReadError('window_minimized'),'window_minimized'),
                                (snapshot(row('a'),row('b'),window=99),'window_or_list_changed')):
            with self.subTest(reason=reason):
                code, status, calls = self.run_frames([snapshot(row('a'),row('b')), failure])
                self.assertEqual(code, 3)
                self.assertEqual(calls, 2)
                self.assertEqual(status['stop_reason'], reason)
                self.assertEqual(status['incoming_candidates'], 0)

    def test_unexpected_external_error_is_redacted_and_releases_lock(self):
        code, status, _ = self.run_frames([snapshot(row('a')), RuntimeError('FICTIONAL_PRIVATE_TEXT')])
        self.assertEqual(code, 3)
        self.assertEqual(status['stop_reason'], 'read_failed')
        with InstanceLock(self.directory, timeout=0):
            pass

    def test_stale_stop_command_cannot_stop_new_generation(self):
        self.directory.mkdir()
        atomic_json(self.directory/'control.json', {'action':'stop','run_id':'old','id':'stale'})
        code, status, calls = self.run_frames([snapshot(row('a')), snapshot(row('a'),row('b')), KeyboardInterrupt()])
        self.assertEqual(code, 0)
        self.assertEqual(calls, 3)
        self.assertEqual(status['incoming_candidates'], 1)

    def test_competing_instance_cannot_overwrite_owner_status_or_read(self):
        self.directory.mkdir()
        owner = {'phase':'observing','run_id':'a'*32,'pid':os.getpid(),'snapshots':9}
        atomic_json(self.directory/'runtime.json', owner)
        with InstanceLock(self.directory, timeout=0), patch.object(self.monitor, 'NativeReader', side_effect=AssertionError('must not read')):
            code = self.monitor.run_monitor('fixture.exe', self.directory)
        self.assertEqual(code, 3)
        self.assertEqual(json.loads((self.directory/'runtime.json').read_text('utf-8')), owner)

    def test_status_whitelists_file_fields_and_detects_dead_worker(self):
        self.directory.mkdir()
        atomic_json(self.directory/'runtime.json', {'phase':'observing','run_id':'b'*32,'pid':os.getpid(),
                    'snapshots':12,'incoming_candidates':2,'text':'FICTIONAL_PRIVATE_TEXT',
                    'stop_reason':'FICTIONAL_PRIVATE_TEXT','model_called':True,'real_send_supported':True})
        status = self.monitor.monitor_status(self.directory)
        self.assertEqual(status['phase'], 'stopped')
        self.assertFalse(status['active'])
        self.assertEqual(status['snapshots'], 12)
        self.assertNotIn('FICTIONAL_PRIVATE_TEXT', json.dumps(status))
        self.assertFalse(status['model_called'])
        self.assertFalse(status['real_send_supported'])

    def test_malformed_status_values_are_sanitized_without_breaking_controls(self):
        self.directory.mkdir()
        atomic_json(self.directory/'runtime.json', {'phase':[], 'stop_reason':{},
                    'snapshots':True, 'incoming_candidates':-1, 'filtered_self_texts':'private'})
        status = self.monitor.monitor_status(self.directory)
        self.assertEqual(status['phase'], 'stopped')
        self.assertIsNone(status['stop_reason'])
        self.assertEqual(status['snapshots'], 0)
        self.assertEqual(status['incoming_candidates'], 0)
        self.assertEqual(status['filtered_self_texts'], 0)

    def test_empty_viewport_does_not_claim_ready_baseline(self):
        code, status, _ = self.run_frames([snapshot(), KeyboardInterrupt()])
        self.assertEqual(code, 0)
        self.assertFalse(status['baseline_ready'])
        code, status, _ = self.run_frames([snapshot(),snapshot(row('a')),KeyboardInterrupt()])
        self.assertTrue(status['baseline_ready'])
        self.assertEqual(status['incoming_candidates'], 0)

    def test_cli_status_and_stop_do_not_load_personal_configuration(self):
        (Path(self.tmp.name)/'.env').write_text('PRIVATE_INVALID_ENV', 'utf-8')
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = self.monitor.main(['--data-dir',str(self.directory),'status'])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(stream.getvalue())['active'])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.monitor.main(['--data-dir',str(self.directory),'stop']), 4)

    def test_background_start_waits_for_readiness_and_stop_uses_real_child(self):
        # Replace only the external desktop reader in an actual child process.
        worker = Path(self.tmp.name)/'fixture worker.py'
        worker.write_text('''import sys
from wechat_memory import monitor
class Reader:
    snapshot_change_retries=0
    def __init__(self,*args,**kwargs): pass
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,**kwargs):
        return dict(status='visual_text_snapshot',process=12,started='123456',window=34,root='ChatSingleWindowwxid_fixture',list_token='list',rows=[dict(token='a',kind='text',text='FICTIONAL_PRIVATE_TEXT',direction='incoming_candidate')])
monitor.NativeReader=Reader
raise SystemExit(monitor.main(sys.argv[1:]))
''', 'utf-8')
        original_popen = subprocess.Popen
        children = []
        def launch(command, **kwargs):
            index = command.index('wechat_memory.monitor')
            process = original_popen([*command[:index-1],str(worker),*command[index+1:]], **kwargs)
            children.append(process)
            return process
        def cleanup():
            for child in children:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=10)
        self.addCleanup(cleanup)
        with patch.object(self.monitor.subprocess, 'Popen', side_effect=launch), redirect_stdout(io.StringIO()):
            code = self.monitor.main(['--data-dir',str(self.directory),'start','--client-path','fixture.exe'])
        self.assertEqual(code, 0)
        ready = self.monitor.monitor_status(self.directory)
        self.assertTrue(ready['active'])
        self.assertEqual(ready['phase'], 'observing')
        self.assertGreaterEqual(ready['snapshots'], 1)
        self.assertEqual(ready['incoming_candidates'], 0)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.monitor.main(['--data-dir',str(self.directory),'stop']), 0)
        self.assertFalse(self.monitor.monitor_status(self.directory)['active'])
        self.assertEqual(children[0].wait(timeout=10), 0)


if __name__ == '__main__':
    unittest.main()
