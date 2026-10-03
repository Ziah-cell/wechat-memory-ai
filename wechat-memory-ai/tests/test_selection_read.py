"""Multiselect labels are unverified candidates, including while minimized."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory import live_read, monitor
from test_monitor import row, snapshot


def selected(*rows, minimized=True, peer='Fixture Peer'):
    raw = snapshot(*rows)
    raw.update(status='selection_text_snapshot', minimized=minimized, peer_name=peer)
    raw['rows'] = [{k:v for k,v in r.items() if k!='direction'} for r in rows]
    return raw


class SelectionReadTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(live_read, 'validate_selection_snapshot', None)),
                        'selection text reading is not implemented')

    def test_baseline_then_same_text_distinct_rows_without_replay(self):
        session = live_read.SelectionOccurrenceSession()
        a, b = row('a','Fixture Peer old'), row('b','Fixture Peer older')
        self.assertEqual(session.accept(selected(a,b)), [])
        events = session.accept(selected(a,b,row('c','Fixture Peer repeated'),row('d','Fixture Peer repeated')))
        self.assertEqual([e.text for e in events], ['repeated','repeated'])
        self.assertEqual([e.direction for e in events], ['incoming_candidate']*2)
        self.assertNotEqual(events[0].observation_id, events[1].observation_id)
        report = session.report()
        self.assertFalse(report['sender_verified'])
        self.assertFalse(report['history_boundary_verified'])
        self.assertNotIn('Fixture Peer', json.dumps(report))

    def test_nonpeer_names_never_assumed_self_and_nested_prefix_stays_unverified(self):
        _, records = live_read.validate_selection_snapshot(selected(
            row('a','Fixture Self hello'), row('b','unknown'),
            row('c','Fixture Peer Extra ambiguous')))
        self.assertEqual([r[4] for r in records], ['unknown','unknown','incoming_candidate'])
        # Display names can collide or nest: candidate classification cannot authorize sending.
        self.assertFalse(live_read.SelectionOccurrenceSession().report()['sender_verified'])

    def test_minimized_transitions_do_not_rebaseline_but_peer_rename_stops(self):
        session = live_read.SelectionOccurrenceSession()
        a, b = row('a','Fixture Peer first'), row('b','Fixture Peer second')
        session.accept(selected(a,b,minimized=False))
        self.assertEqual(session.accept(selected(a,b,minimized=True)), [])
        with self.assertRaises(live_read.ReadError):
            session.accept(selected(a,b,peer='Renamed Fixture'))
        self.assertEqual(session.report()['stop_reason'], 'window_or_list_changed')

    def test_bad_protocol_and_other_modes_cannot_enter_selection_session(self):
        for changes in ({'minimized':1},{'peer_name':''},{'peer_name':'name\nextra'},
                        {'peer_name':[]},{'extra':'PRIVATE'},{'status':'snapshot'},
                        {'rows':[dict(row('a'),direction='self_candidate')]}):
            raw = selected(row('a','Fixture Peer first'))
            raw.update(changes)
            with self.subTest(fields=list(changes)), self.assertRaises(live_read.ReadError):
                live_read.validate_selection_snapshot(raw)
        with self.assertRaises(live_read.ReadError):
            live_read.VisualOccurrenceSession().accept(selected(row('a')))

    def test_lost_overlap_and_reappearing_occurrences_still_stop(self):
        session = live_read.SelectionOccurrenceSession()
        a,b,c,d = [row(k,'Fixture Peer '+k) for k in 'abcd']
        session.accept(selected(a,b,c))
        session.accept(selected(b,c,d))
        with self.assertRaises(live_read.ReadError):
            session.accept(selected(c,d,a))
        self.assertEqual(session.report()['stop_reason'], 'occurrence_reappeared')
        fresh = live_read.SelectionOccurrenceSession()
        fresh.accept(selected(a,b))
        with self.assertRaises(live_read.ReadError):
            fresh.accept(selected(c,d))
        self.assertEqual(fresh.report()['stop_reason'], 'message_continuity_lost')

    def test_native_mode_stays_separate_and_keeps_binding_private(self):
        raw = selected(row('a','Fixture Peer first'))
        reader = live_read.NativeReader('fixture.exe')
        reader.executable = Path('never-executed.exe')
        result = subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=result) as run:
            self.assertEqual(reader.read_selection_text(), raw)
        self.assertEqual(run.call_args.args[0][-1], '--selection-text')
        self.assertEqual(json.loads(run.call_args.kwargs['input']), None)
        binding = reader.binding
        raw['window'] = 999
        result.stdout = json.dumps(raw).encode()
        with patch.object(live_read.subprocess,'run',return_value=result):
            with self.assertRaisesRegex(live_read.ReadError, '^window_or_list_changed$'):
                reader.read_selection_text()
        self.assertEqual(reader.binding,binding)

    def test_selection_failure_is_fixed_reason_and_is_never_retried(self):
        for reason in ('selection_mode_required','selection_snapshot_changed'):
            reader = live_read.NativeReader('fixture.exe')
            reader.executable = Path('never-executed.exe')
            result = subprocess.CompletedProcess([],3,json.dumps(dict(status='reader_error',reason=reason)).encode(),b'PRIVATE')
            with patch.object(live_read.subprocess,'run',return_value=result) as run:
                with self.assertRaisesRegex(live_read.ReadError, '^'+reason+'$'):
                    reader.read_selection_text()
            self.assertEqual(run.call_count,1)

    def test_monitor_selection_mode_tracks_minimized_without_model_or_persistence(self):
        frames = iter([selected(row('a','Fixture Peer old'),minimized=False),
                       selected(row('a','Fixture Peer old'),row('b','Fixture Peer NEW_PRIVATE_TEXT')),
                       live_read.ReadError('selection_mode_required')])
        class Reader:
            snapshot_change_retries=0
            def __init__(self,*args): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read_selection_text(self):
                value=next(frames)
                if isinstance(value,Exception): raise value
                return value
            def read(self,**kwargs): raise AssertionError('must not capture pixels')
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(monitor,'NativeReader',Reader),patch.object(monitor.time,'sleep'):
                code = monitor.run_monitor('fixture.exe',temp,reader_mode='selection')
            status=monitor.monitor_status(temp)
            self.assertEqual(code,3)
            self.assertEqual(status['reader_mode'],'selection')
            self.assertEqual(status['minimized_snapshots'],1)
            self.assertTrue(status['window_minimized'])
            self.assertEqual(status['incoming_candidates'],1)
            self.assertFalse(status['reply_ready'])
            self.assertFalse(status['model_called'])
            self.assertFalse(status['memory_written'])
            self.assertEqual(status['stop_reason'],'selection_mode_required')
            for path in Path(temp).glob('*.json'):
                self.assertNotIn('PRIVATE_TEXT',path.read_text())
                self.assertNotIn('Fixture Peer',path.read_text())

    def test_bound_selection_transition_resamples_same_target_before_commit(self):
        raw = selected(row('a','Fixture Peer first'))
        binding={k:raw[k] for k in ('process','started','window','root','list_token')}
        reader=live_read.NativeReader('fixture.exe',expected_binding=binding)
        reader.executable=Path('never-executed.exe')
        changed=subprocess.CompletedProcess([],3,b'{"status":"reader_error","reason":"selection_snapshot_changed"}',b'')
        done=subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',side_effect=[changed,done]) as run, patch.object(live_read.time,'sleep'):
            self.assertEqual(reader.read_selection_text(),raw)
        self.assertEqual(reader.snapshot_change_retries,1)
        self.assertEqual([json.loads(c.kwargs['input']) for c in run.call_args_list],[binding,binding])

    def test_bound_selection_retries_are_bounded_and_other_errors_still_stop(self):
        raw=selected(row('a'))
        binding={k:raw[k] for k in ('process','started','window','root','list_token')}
        for reason,calls in (('selection_snapshot_changed',3),('selection_mode_required',1),('window_or_list_changed',1)):
            reader=live_read.NativeReader('fixture.exe',expected_binding=binding)
            reader.executable=Path('never-executed.exe')
            done=subprocess.CompletedProcess([],3,json.dumps(dict(status='reader_error',reason=reason)).encode(),b'')
            with patch.object(live_read.subprocess,'run',return_value=done) as run,patch.object(live_read.time,'sleep'):
                with self.assertRaisesRegex(live_read.ReadError,'^'+reason+'$'):
                    reader.read_selection_text()
            self.assertEqual(run.call_count,calls)

    def test_selection_late_success_is_discarded_at_shared_deadline(self):
        raw=selected(row('a'))
        binding={k:raw[k] for k in ('process','started','window','root','list_token')}
        reader=live_read.NativeReader('fixture.exe',expected_binding=binding)
        reader.executable=Path('never-executed.exe')
        done=subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=done), \
                patch.object(live_read.time,'monotonic',side_effect=[0,0,8.01]):
            with self.assertRaisesRegex(live_read.ReadError,'^native_reader_timeout$'):
                reader.read_selection_text()
