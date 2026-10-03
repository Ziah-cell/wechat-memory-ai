"""Fixed native checkpoints survive failures without publishing pipe contents."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory import live_read, monitor
from test_background_read import background
from test_monitor import row


STAGES = ('started', 'request_read', 'client_lookup', 'process_lookup',
          'window_lookup', 'binding_check', 'tree_lookup', 'list_binding',
          'rows_first', 'binding_middle', 'rows_second', 'rows_compare',
          'binding_final', 'snapshot_ready', 'serializing', 'completed')


def trace(count=len(STAGES)):
    return ''.join('wmrd1:%s:%d\n' % (stage, i*10) for i,stage in enumerate(STAGES[:count])).encode()


def native():
    reader = live_read.NativeReader('fixture.exe')
    reader.executable = Path('never-executed.exe')
    return reader


class ReaderTimingTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(native(), 'diagnostics'), 'reader timing diagnostics are missing')

    def test_success_keeps_stdout_protocol_and_exposes_only_fixed_checkpoints(self):
        reader = native()
        raw = background(row('a', 'PRIVATE_BODY'))
        done = subprocess.CompletedProcess([], 0, json.dumps(raw).encode(), trace())
        with patch.object(live_read.subprocess, 'run', return_value=done), \
                patch.object(live_read.time, 'perf_counter', side_effect=[1, 1.25]):
            self.assertEqual(reader.read_background_text(), raw)
        report = reader.diagnostics
        self.assertEqual(report['child_calls'], 1)
        self.assertEqual(report['child_timeouts'], 0)
        self.assertEqual(report['last_call_ms'], 250)
        self.assertEqual(report['max_call_ms'], 250)
        self.assertEqual(report['last_native_stage'], 'completed')
        self.assertTrue(report['native_trace_valid'])
        self.assertEqual(report['native_checkpoints_ms']['rows_first'], 80)
        self.assertNotIn('PRIVATE_BODY', json.dumps(report))
        report['native_checkpoints_ms']['rows_first'] = 999
        self.assertEqual(reader.diagnostics['native_checkpoints_ms']['rows_first'], 80)

    def test_timeout_keeps_partial_stderr_but_never_partial_stdout_or_exception(self):
        reader = native()
        error = subprocess.TimeoutExpired('PRIVATE_COMMAND', 8, output=b'PRIVATE_BODY', stderr=trace(9))
        with patch.object(live_read.subprocess, 'run', side_effect=error) as run:
            with self.assertRaisesRegex(live_read.ReadError, '^native_reader_timeout$'):
                reader.read_background_text()
        self.assertEqual(run.call_count, 1)
        self.assertIsNone(reader.binding)
        report = reader.diagnostics
        self.assertEqual(report['child_timeouts'], 1)
        self.assertTrue(report['last_call_timed_out'])
        self.assertEqual(report['last_native_stage'], 'rows_first')
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_malformed_unknown_oversized_and_out_of_order_traces_are_discarded(self):
        bad = [b'', None, 'PRIVATE', b'PRIVATE', trace(2)+b'wmrd1:PRIVATE:20\n',
               trace(2)+b'wmrd1:client_lookup:9\n', b'wmrd1:rows_first:0\n',
               trace(2)+b'wmrd1:request_read:20\n', trace(2)+b'wmrd1:client_lookup:999999999999\n',
               trace(1)+b'wmrd1:request_read:-1\n', trace(1)+b'wmrd1:request_read:true\n',
               trace()+b'PRIVATE'*1000, trace(1)[:-1]]
        for stderr in bad:
            with self.subTest(case=bad.index(stderr)):
                reader = native()
                raw = background(row('a'))
                done = subprocess.CompletedProcess([], 0, json.dumps(raw).encode(), stderr)
                with patch.object(live_read.subprocess, 'run', return_value=done):
                    self.assertEqual(reader.read_background_text(), raw)
                self.assertFalse(reader.diagnostics['native_trace_valid'])
                self.assertEqual(reader.diagnostics['last_native_stage'], 'not_reported')
                self.assertEqual(reader.diagnostics['native_checkpoints_ms'], {})
                self.assertNotIn('PRIVATE', json.dumps(reader.diagnostics))

    def test_trace_is_replaced_each_call_and_counters_include_failed_children(self):
        reader = native()
        raw = background(row('a'))
        responses = [subprocess.CompletedProcess([],0,json.dumps(raw).encode(),trace()),
                     subprocess.CompletedProcess([],3,b'{"status":"reader_error","reason":"window_or_list_changed"}',trace(6))]
        with patch.object(live_read.subprocess, 'run', side_effect=responses), \
                patch.object(live_read.time, 'perf_counter', side_effect=[0,.5,1,1.25]):
            reader.read_background_text()
            with self.assertRaisesRegex(live_read.ReadError, '^window_or_list_changed$'):
                reader.read_background_text()
        report = reader.diagnostics
        self.assertEqual(report['child_calls'], 2)
        self.assertEqual(report['max_call_ms'], 500)
        self.assertEqual(report['last_call_ms'], 250)
        self.assertEqual(report['last_native_stage'], 'binding_check')
        self.assertNotIn('completed', report['native_checkpoints_ms'])

    def test_os_error_discards_prior_trace_and_does_not_publish_exception(self):
        reader = native()
        raw = background(row('a'))
        with patch.object(live_read.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([],0,json.dumps(raw).encode(),trace()), OSError('PRIVATE')]):
            reader.read_background_text()
            with self.assertRaisesRegex(live_read.ReadError, '^native_reader_unavailable$'):
                reader.read_background_text()
        self.assertEqual(reader.diagnostics['child_calls'], 2)
        self.assertFalse(reader.diagnostics['native_trace_valid'])

    def test_real_python_child_timeout_preserves_flushed_phase_without_ui(self):
        # A Python pipe/termination check, not a native UI or bitmap fixture.
        reader = native()
        run = subprocess.run
        script = 'import sys,time; sys.stderr.buffer.write(%r); sys.stderr.flush(); time.sleep(30)' % trace(5)
        def child(_command, **kwargs):
            return run([sys.executable,'-X','utf8','-c',script], **kwargs)
        with patch.object(live_read.subprocess, 'run', side_effect=child):
            with self.assertRaisesRegex(live_read.ReadError, '^native_reader_timeout$'):
                reader._read_once(background_text=True, _timeout=1)
        self.assertEqual(reader.diagnostics['last_native_stage'], 'window_lookup')
        self.assertTrue(reader.diagnostics['last_call_timed_out'])

    def test_monitor_publishes_last_failed_call_and_rejects_untrusted_diagnostics(self):
        values = iter([background(row('a')), live_read.ReadError('native_reader_timeout')])
        class Reader:
            snapshot_change_retries=0
            diagnostics = dict(child_calls=2,child_timeouts=1,last_call_ms=8001,max_call_ms=8001,
                               last_call_timed_out=True,native_checkpoints_ms=dict(zip(STAGES[:9],range(9))),
                               text='PRIVATE',last_native_stage='PRIVATE')
            def __init__(self,*args): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read_background_text(self):
                value=next(values)
                if isinstance(value,Exception): raise value
                return value
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(monitor,'NativeReader',Reader), patch.object(monitor.time,'sleep'):
                self.assertEqual(monitor.run_monitor('fixture.exe',temp,reader_mode='background'),3)
            status=monitor.monitor_status(temp)
            report=status['reader_diagnostics']
            self.assertEqual(report['last_native_stage'],'rows_first')
            self.assertEqual(report['child_timeouts'],1)
            self.assertEqual(status['snapshots'],1)
            self.assertFalse(status['reply_ready'])
            self.assertNotIn('PRIVATE',''.join(p.read_text() for p in Path(temp).glob('*.json')))
        for raw in (None, [], {'native_checkpoints_ms':{'PRIVATE':1}},
                    {'child_calls':True,'child_timeouts':-1,'last_call_ms':'PRIVATE'},
                    {'native_checkpoints_ms':{'started':True}}, {'native_checkpoints_ms':{'started':0,'window_lookup':1}}):
            public=monitor._public_status({'reader_diagnostics':raw})['reader_diagnostics']
            self.assertFalse(public['native_trace_valid'])
            self.assertNotIn('PRIVATE',json.dumps(public))


if __name__ == '__main__':
    unittest.main()
