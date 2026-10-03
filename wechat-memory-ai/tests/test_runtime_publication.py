"""A concurrent status reader must not kill the monitor on Windows."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory import runtime, monitor
from test_monitor import row, snapshot


class RuntimePublicationTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows file sharing regression')
    def test_held_status_reader_released_during_retry_allows_atomic_update(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'runtime.json'
            runtime.atomic_json(path,{'snapshots':1})
            held=path.open('rb')
            try:
                with patch.object(runtime.time,'sleep',side_effect=lambda _: held.close()):
                    try:
                        runtime.atomic_json(path,{'snapshots':2})
                    except PermissionError:
                        self.fail('a brief concurrent status read prevented publication')
            finally:
                held.close()
            self.assertEqual(json.loads(path.read_text()),{'snapshots':2})
            self.assertEqual(list(Path(temp).glob('.control-*')),[])

    def test_persistent_permission_failure_is_bounded_and_preserves_last_status(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'runtime.json'
            runtime.atomic_json(path,{'snapshots':1})
            with patch.object(runtime.os,'replace',side_effect=PermissionError('fixture')) as replace, \
                    patch.object(runtime.time,'sleep') as sleep:
                with self.assertRaises(PermissionError):
                    runtime.atomic_json(path,{'snapshots':2})
            self.assertGreater(replace.call_count,1)
            self.assertLessEqual(replace.call_count,32)
            self.assertLessEqual(sum(c.args[0] for c in sleep.call_args_list),.5)
            self.assertEqual(json.loads(path.read_text()),{'snapshots':1})
            self.assertEqual(list(Path(temp).glob('.control-*')),[])

    @unittest.skipUnless(os.name == 'nt', 'Windows monitor publication overlap')
    def test_monitor_survives_status_read_overlap_and_stops_on_requested_interrupt(self):
        held=[]
        with tempfile.TemporaryDirectory() as temp:
            class Reader:
                snapshot_change_retries=0
                def __init__(self,*args): self.calls=0
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def read(self,**kwargs):
                    self.calls+=1
                    if self.calls>1: raise KeyboardInterrupt()
                    held.append((Path(temp)/'runtime.json').open('rb'))
                    return snapshot(row('a'))
            def release(_):
                for handle in held: handle.close()
            try:
                with patch.object(monitor,'NativeReader',Reader),patch.object(runtime.time,'sleep',side_effect=release):
                    code=monitor.run_monitor('fixture.exe',temp)
            finally:
                release(0)
            self.assertEqual(code,0)
            status=monitor.monitor_status(temp)
            self.assertEqual(status['stop_reason'],'interrupted')
            self.assertEqual(status['snapshots'],1)
            self.assertFalse(status['active'])
