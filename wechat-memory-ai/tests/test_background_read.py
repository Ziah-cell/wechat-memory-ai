"""Normal minimized windows produce unverified text, never inferred senders."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from wechat_memory import live_read, monitor
from test_monitor import row, snapshot


def background(*rows, minimized=True):
    raw=snapshot(*rows)
    raw.update(status='background_text_snapshot',minimized=minimized)
    raw['rows']=[{k:v for k,v in r.items() if k!='direction'} for r in rows]
    return raw


class BackgroundReadTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(live_read,'validate_background_snapshot',None)),
                        'normal minimized text reader is not implemented')

    def test_old_viewport_is_skipped_and_two_equal_text_arrivals_remain_distinct(self):
        session=live_read.BackgroundOccurrenceSession()
        a,b=row('a','old'),row('b','older')
        self.assertEqual(session.accept(background(a,b,minimized=False)),[])
        self.assertEqual(session.accept(background(a,b)),[])
        events=session.accept(background(a,b,row('c','same'),row('d','same')))
        self.assertEqual([e.text for e in events],['same','same'])
        self.assertEqual([e.direction for e in events],['unknown','unknown'])
        self.assertNotEqual(events[0].observation_id,events[1].observation_id)
        self.assertFalse(session.report()['sender_verified'])
        self.assertFalse(session.report()['history_boundary_verified'])

    def test_other_protocols_or_extra_sender_fields_cannot_be_promoted(self):
        for changes in ({'minimized':1},{'status':'snapshot'},{'peer_name':'Fixture'},
                        {'rows':[row('a')]},{'rows':'private'}):
            raw=background(row('a'))
            raw.update(changes)
            with self.subTest(fields=list(changes)),self.assertRaises(live_read.ReadError):
                live_read.validate_background_snapshot(raw)
        raw=background(row('a'))
        for session in (live_read.ReadSession(),live_read.VisualOccurrenceSession(),live_read.SelectionOccurrenceSession()):
            with self.assertRaises(live_read.ReadError):session.accept(raw)

    def test_changed_window_and_old_occurrence_reappearance_still_stop(self):
        for changed in ('window','occurrence'):
            session=live_read.BackgroundOccurrenceSession()
            a,b,c,d=[row(k,k) for k in 'abcd']
            session.accept(background(a,b,c))
            session.accept(background(b,c,d))
            raw=background(c,d,a)
            if changed=='window':raw['window']=999
            with self.assertRaises(live_read.ReadError):session.accept(raw)
            self.assertEqual(session.report()['stop_reason'],
                             'window_or_list_changed' if changed=='window' else 'occurrence_reappeared')

    def test_read_uses_separate_native_mode_without_visual_fallback(self):
        raw=background(row('a'))
        reader=live_read.NativeReader('fixture.exe');reader.executable=Path('never-executed.exe')
        result=subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=result) as run:
            self.assertEqual(reader.read_background_text(),raw)
        self.assertEqual(run.call_args.args[0][-1],'--background-text')
        self.assertEqual(reader.binding,{k:raw[k] for k in ('process','started','window','root','list_token')})

    def test_only_bound_torn_reads_retry_with_same_binding(self):
        raw=background(row('a'))
        binding={k:raw[k] for k in ('process','started','window','root','list_token')}
        for bound,reason,calls in ((True,'background_snapshot_changed',3),(False,'background_snapshot_changed',1),
                                   (True,'background_mode_required',1),(True,'window_or_list_changed',1)):
            reader=live_read.NativeReader('fixture.exe',expected_binding=binding if bound else None)
            reader.executable=Path('never-executed.exe')
            failed=subprocess.CompletedProcess([],3,json.dumps(dict(status='reader_error',reason=reason)).encode(),b'')
            with patch.object(live_read.subprocess,'run',return_value=failed) as run,patch.object(live_read.time,'sleep'):
                with self.assertRaisesRegex(live_read.ReadError,'^'+reason+'$'):reader.read_background_text()
            self.assertEqual(run.call_count,calls)
            self.assertTrue(all(json.loads(c.kwargs['input'])==(binding if bound else None) for c in run.call_args_list))

    def test_monitor_counts_new_text_without_claiming_incoming_or_self(self):
        frames=iter([background(row('a','old')),background(row('a','old'),row('b','PRIVATE')),KeyboardInterrupt()])
        class Reader:
            snapshot_change_retries=0
            def __init__(self,*args):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read_background_text(self):
                value=next(frames)
                if isinstance(value,BaseException):raise value
                return value
            def read(self,**kwargs):raise AssertionError('must not capture pixels')
            def read_selection_text(self):raise AssertionError('must not require selection')
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(monitor,'NativeReader',Reader),patch.object(monitor.time,'sleep'):
                self.assertEqual(monitor.run_monitor('fixture.exe',temp,reader_mode='background'),0)
            status=monitor.monitor_status(temp)
            self.assertEqual(status['reader_mode'],'background')
            self.assertEqual(status['minimized_snapshots'],2)
            self.assertEqual(status['filtered_unknown_texts'],1)
            self.assertEqual(status['incoming_candidates'],0)
            self.assertEqual(status['filtered_self_texts'],0)
            self.assertFalse(status['reply_ready'])
            self.assertFalse(status['model_called'])
            self.assertFalse(status['memory_written'])
            self.assertNotIn('PRIVATE',''.join(p.read_text() for p in Path(temp).glob('*.json')))

    def test_background_late_result_is_not_delivered(self):
        raw=background(row('a'))
        binding={k:raw[k] for k in ('process','started','window','root','list_token')}
        reader=live_read.NativeReader('fixture.exe',expected_binding=binding);reader.executable=Path('never-executed.exe')
        result=subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=result),patch.object(live_read.time,'monotonic',side_effect=[0,0,8.1]):
            with self.assertRaisesRegex(live_read.ReadError,'^native_reader_timeout$'):reader.read_background_text()
