"""Recovery boundaries: never turn a lost viewport or restart into a reply."""
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory import live_read, monitor
from wechat_memory.preflight import PreflightSession, filter_incoming
from test_background_read import background
from test_monitor import row
from test_reader_timing import native, trace


class BackgroundRecoveryTests(unittest.TestCase):
    def test_torn_read_recovers_only_same_binding_with_old_checkpoint_and_unknown_output(self):
        reader, session = native(), live_read.BackgroundOccurrenceSession()
        a,b,c,d = [row(k,k) for k in 'abcd']
        first, after = background(a,b,c), background(b,c,d)
        failure = dict(status='reader_error',reason='background_snapshot_changed')
        values = [subprocess.CompletedProcess([],0,json.dumps(first).encode(),trace()),
                  subprocess.CompletedProcess([],3,json.dumps(failure).encode(),trace(12)),
                  subprocess.CompletedProcess([],0,json.dumps(after).encode(),trace())]
        with patch.object(live_read.subprocess,'run',side_effect=values) as run, patch.object(live_read.time,'sleep'):
            self.assertEqual(session.accept(reader.read_background_text()),[])
            checkpoint = session.report()
            raw = reader.read_background_text()
            self.assertEqual(session.report(),checkpoint)
            observations=session.accept(raw)
        self.assertEqual([o.direction for o in observations],['unknown'])
        self.assertEqual(filter_incoming(observations),[])
        self.assertEqual(reader.snapshot_change_retries,1)
        self.assertEqual(reader.diagnostics['child_calls'],3)
        self.assertEqual(run.call_args_list[1].kwargs['input'],run.call_args_list[2].kwargs['input'])
        self.assertEqual(session.report()['snapshots'],2)

    def test_lost_viewport_is_terminal_even_if_old_anchor_later_returns(self):
        for changed in (background(row('history1'),row('history2')),
                        background(row('a'),row('b'),minimized=False)|{'list_token':'replacement'}):
            with self.subTest(binding_changed=changed['list_token']!='list'):
                session=live_read.BackgroundOccurrenceSession()
                session.accept(background(row('a'),row('b')))
                before=session.report()
                with self.assertRaises(live_read.ReadError): session.accept(changed)
                stopped=session.report()
                self.assertIn(stopped['stop_reason'],('message_continuity_lost','window_or_list_changed'))
                self.assertEqual(stopped['snapshots'],before['snapshots'])
                self.assertEqual(stopped['candidate_texts'],0)
                with self.assertRaisesRegex(live_read.ReadError,'^session_stopped$'):
                    session.accept(background(row('a'),row('b'),row('late')))
                self.assertEqual(session.report(),stopped)

    def test_explicit_restart_discards_downtime_text_and_never_promotes_self_or_history(self):
        old=live_read.BackgroundOccurrenceSession()
        old.accept(background(row('a'),row('b')))
        old.stop('native_reader_timeout')
        restarted=live_read.BackgroundOccurrenceSession()
        baseline=background(row('a'),row('b'),row('during_downtime','OLD_HISTORY'))
        self.assertEqual(restarted.accept(baseline),[])
        for token,text in (('own','OWN_TEXT'),('sync','SYNCED_HISTORY'),('new','NEW_UNKNOWN')):
            baseline['rows'].append(dict(token=token,text=text,kind='text'))
            observations=restarted.accept(baseline)
            self.assertEqual([o.direction for o in observations],['unknown'])
            self.assertEqual(filter_incoming(observations),[])
        self.assertEqual(restarted.report()['candidate_texts'],3)
        self.assertFalse(restarted.report()['history_boundary_verified'])
        preflight=PreflightSession()
        with self.assertRaises(live_read.ReadError): preflight.accept(baseline)
        self.assertEqual(preflight.report()['preflight_state'],'closed')

    def test_monitor_stops_after_timeout_or_continuity_loss_without_automatic_rebaseline(self):
        failures = [(live_read.ReadError('native_reader_timeout'),'native_reader_timeout'),
                    (background(row('history1'),row('history2')),'message_continuity_lost')]
        for failure,reason in failures:
            values=iter([background(row('a'),row('b')),failure])
            calls=[]
            class Reader:
                snapshot_change_retries=0
                def __init__(self,*args): pass
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def read_background_text(self):
                    calls.append(True)
                    value=next(values)
                    if isinstance(value,Exception): raise value
                    return value
            with tempfile.TemporaryDirectory() as temp:
                with patch.object(monitor,'NativeReader',Reader),patch.object(monitor.time,'sleep'):
                    self.assertEqual(monitor.run_monitor('fixture.exe',temp,reader_mode='background'),3)
                status=monitor.monitor_status(temp)
                self.assertEqual(len(calls),2)
                self.assertEqual(status['snapshots'],1)
                self.assertEqual(status['stop_reason'],reason)
                self.assertEqual(status['incoming_candidates'],0)
                self.assertEqual(status['filtered_unknown_texts'],0)
                self.assertFalse(status['reply_ready'])
                self.assertFalse(status['active'])


if __name__ == '__main__':
    unittest.main()
