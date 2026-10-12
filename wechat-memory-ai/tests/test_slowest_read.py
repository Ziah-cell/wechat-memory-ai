"""Keep the slowest call's phase evidence after later fast calls replace last."""
import json
import subprocess
import unittest
from unittest.mock import patch

from wechat_memory import live_read, monitor
from test_monitor import row, snapshot
from test_reader_timing import native, trace


class SlowestReadTests(unittest.TestCase):
    def setUp(self):
        self.assertIn('slowest_call',native().diagnostics,'slowest native call is not retained')

    def invoke(self,reader,duration,stderr,*,error=None):
        result=subprocess.CompletedProcess([],0,json.dumps(snapshot(row('a'))).encode(),stderr)
        with patch.object(live_read.subprocess,'run',side_effect=error,return_value=result), \
                patch.object(live_read.time,'perf_counter',side_effect=[0,duration]):
            if error:
                with self.assertRaises(live_read.ReadError):reader.read(visual_text=True)
            else:reader.read(visual_text=True)

    def test_fast_followup_does_not_erase_slow_phase_evidence(self):
        reader=native()
        self.invoke(reader,6,trace(9))
        self.invoke(reader,.5,trace())
        report=reader.diagnostics
        self.assertEqual(report['last_native_stage'],'completed')
        self.assertEqual(report['last_call_ms'],500)
        self.assertEqual(report['slowest_call'],dict(child_call=1,call_ms=6000,timed_out=False,
                         native_trace_valid=True,last_native_stage='rows_first',
                         native_checkpoints_ms=reader.diagnostics['slowest_call']['native_checkpoints_ms']))
        self.assertEqual(report['slowest_call']['native_checkpoints_ms']['rows_first'],80)

    def test_larger_call_replaces_record_but_equal_duration_retains_first(self):
        reader=native()
        for duration,stderr in ((.25,trace(5)),(.5,trace(9)),(.5,trace())):
            self.invoke(reader,duration,stderr)
        self.assertEqual(reader.diagnostics['slowest_call']['child_call'],2)
        self.assertEqual(reader.diagnostics['slowest_call']['call_ms'],500)
        self.assertEqual(reader.diagnostics['slowest_call']['last_native_stage'],'rows_first')

    def test_slow_timeout_or_os_failure_replaces_success_without_leaking_error(self):
        for error in (subprocess.TimeoutExpired('PRIVATE',8,output=b'PRIVATE',stderr=trace(5)),OSError('PRIVATE')):
            reader=native()
            self.invoke(reader,.5,trace())
            self.invoke(reader,8,None,error=error)
            slow=reader.diagnostics['slowest_call']
            self.assertEqual(slow['child_call'],2)
            self.assertEqual(slow['call_ms'],8000)
            self.assertEqual(slow['timed_out'],isinstance(error,subprocess.TimeoutExpired))
            self.assertEqual(slow['last_native_stage'],'window_lookup' if slow['timed_out'] else 'not_reported')
            self.assertNotIn('PRIVATE',json.dumps(reader.diagnostics))

    def test_reports_are_independent_and_only_keep_one_bounded_record(self):
        reader=native()
        self.assertIsNone(reader.diagnostics['slowest_call'])
        for i in range(1,21):self.invoke(reader,i/100,trace())
        exposed=reader.diagnostics
        exposed['slowest_call']['native_checkpoints_ms']['completed']=999
        exposed['slowest_call']['text']='PRIVATE'
        self.assertEqual(reader.diagnostics['slowest_call']['child_call'],20)
        self.assertEqual(reader.diagnostics['slowest_call']['native_checkpoints_ms']['completed'],130)
        self.assertNotIn('PRIVATE',json.dumps(reader.diagnostics))
        self.assertLess(len(json.dumps(reader.diagnostics)),2000)

    def test_public_status_sanitizes_record_and_rejects_inconsistent_metadata(self):
        good=dict(child_calls=5,max_call_ms=6000,slowest_call=dict(child_call=3,call_ms=6000,timed_out=False,
                  native_checkpoints_ms={'started':0,'request_read':1},text='PRIVATE',last_native_stage='PRIVATE'))
        report=monitor._public_status({'reader_diagnostics':good})['reader_diagnostics']
        self.assertEqual(report['slowest_call']['last_native_stage'],'request_read')
        self.assertNotIn('PRIVATE',json.dumps(report))
        for change in ({'child_call':True},{'child_call':0},{'child_call':6},{'call_ms':5999},
                       {'call_ms':True},{'timed_out':'PRIVATE'}):
            raw=good|{'slowest_call':good['slowest_call']|change}
            self.assertIsNone(monitor._public_status({'reader_diagnostics':raw})['reader_diagnostics']['slowest_call'])
        for invalid_maximum in (None,False,-1,'PRIVATE',86_400_001):
            raw=good|{'max_call_ms':invalid_maximum,'slowest_call':good['slowest_call']|{'call_ms':0}}
            self.assertIsNone(monitor._public_status({'reader_diagnostics':raw})['reader_diagnostics']['slowest_call'])
        raw=good|{'slowest_call':good['slowest_call']|{'native_checkpoints_ms':{'PRIVATE':1}}}
        slow=monitor._public_status({'reader_diagnostics':raw})['reader_diagnostics']['slowest_call']
        self.assertEqual(slow['native_checkpoints_ms'],{})
        self.assertFalse(slow['native_trace_valid'])
        self.assertNotIn('PRIVATE',json.dumps(slow))

    def test_legacy_monitor_status_does_not_invent_slowest_trace(self):
        old=dict(child_calls=1837,max_call_ms=5980,last_call_ms=3322,native_checkpoints_ms={'started':1})
        report=monitor._public_status({'reader_diagnostics':old})['reader_diagnostics']
        self.assertEqual(report['max_call_ms'],5980)
        self.assertIsNone(report['slowest_call'])


if __name__=='__main__':unittest.main()
