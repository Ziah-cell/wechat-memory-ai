"""A single bounded read joins text with unverified visual direction hints."""
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from wechat_memory import live_read

ROOT=Path(__file__).resolve().parents[1]


def row(token, text='fixture', direction='incoming_candidate', kind='text'):
    return dict(token=token,text=text,direction=direction,kind=kind)


def snapshot(*rows):
    return dict(status='visual_text_snapshot',process=12,started='123456',window=34,
                root='ChatSingleWindowwxid_fixture',list_token='list',rows=list(rows))


class VisualOccurrenceTests(unittest.TestCase):
    def session(self):
        cls=getattr(live_read,'VisualOccurrenceSession',None)
        self.assertIsNotNone(cls,'joined visual occurrence session is missing')
        return cls()

    def test_baseline_is_not_replayed_and_same_text_keeps_its_own_direction(self):
        session=self.session()
        a,b=row('a'),row('b')
        self.assertEqual(session.accept(snapshot(a,b)),[])
        result=session.accept(snapshot(a,b,row('c','same'),row('d','same','self_candidate'),
                                       row('e','same','unknown')))
        self.assertEqual([r.text for r in result],['same','same','same'])
        self.assertEqual([r.direction for r in result],['incoming_candidate','self_candidate','unknown'])
        self.assertEqual(len({r.observation_id for r in result}),3)
        report=session.report()
        self.assertEqual(report['mode'],'visual_occurrence_candidates')
        self.assertEqual((report['incoming_candidate_texts'],report['self_candidate_texts'],
                          report['unknown_candidate_texts']),(1,1,1))
        self.assertEqual(session.accept(snapshot(a,b,row('c','same'),row('d','same','self_candidate'),
                                                row('e','same','unknown'))),[])
        for flag in ('sender_verified','history_boundary_verified','server_message_ids_available',
                     'real_send_supported','model_called'):
            self.assertFalse(report[flag])
        self.assertNotIn('wxid_',json.dumps(report))
        self.assertNotIn('same',json.dumps(report))

    def test_anchor_direction_change_stops_without_partial_counts(self):
        session=self.session()
        session.accept(snapshot(row('a'),row('b')))
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(row('a',direction='self_candidate'),row('b'),row('c')))
        self.assertEqual(session.report()['stop_reason'],'message_continuity_lost')
        self.assertEqual(session.report()['incoming_candidate_texts'],0)
        self.assertEqual(session.report()['candidate_rows'],0)

    def test_unknown_visibility_transitions_do_not_destroy_unchanged_content_anchors(self):
        session=self.session()
        session.accept(snapshot(row('a'),row('b',direction='unknown')))
        result=session.accept(snapshot(row('a',direction='unknown'),row('b'),row('c','new')))
        self.assertEqual([r.text for r in result],['new'])
        self.assertEqual(session.report()['incoming_candidate_texts'],1)
        self.assertEqual(session.accept(snapshot(row('a'),row('b'),row('c','new'))),[])
        self.assertEqual(session.report()['candidate_texts'],1)

    def test_unknown_intermediate_does_not_erase_conflicting_positive_direction(self):
        session=self.session()
        session.accept(snapshot(row('a'),row('b')))
        self.assertEqual(session.accept(snapshot(row('a',direction='unknown'),row('b'))),[])
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(row('a',direction='self_candidate'),row('b'),row('c')))
        self.assertEqual(session.report()['stop_reason'],'message_continuity_lost')
        self.assertEqual(session.report()['candidate_texts'],0)
        self.assertEqual(session.report()['snapshots'],2)

    def test_recycled_new_content_can_be_candidate_but_old_pair_with_new_direction_cannot(self):
        session=self.session()
        session.accept(snapshot(row('a','old'),row('b'),row('c')))
        result=session.accept(snapshot(row('b'),row('c'),row('a','new','self_candidate')))
        self.assertEqual(result[0].direction,'self_candidate')
        self.assertEqual(session.report()['reused_token_candidates'],1)
        session.accept(snapshot(row('c'),row('a','new','self_candidate'),row('d')))
        session.accept(snapshot(row('a','new','self_candidate'),row('d'),row('e')))
        before=session.report()
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(row('d'),row('e'),row('a','old','unknown')))
        self.assertEqual(session.report()['stop_reason'],'occurrence_reappeared')
        for key in ('incoming_candidate_texts','self_candidate_texts','unknown_candidate_texts','candidate_rows'):
            self.assertEqual(session.report()[key],before[key])

    def test_plain_visual_and_joined_modes_cannot_be_interchanged(self):
        raw=snapshot(row('a'),row('b'))
        for cls in (live_read.ReadSession,live_read.OccurrenceSession):
            with self.assertRaises(live_read.ReadError): cls().accept(raw)
        for status in ('snapshot','visual_snapshot','capability_snapshot'):
            with self.assertRaises(live_read.ReadError): self.session().accept(dict(raw,status=status))

    def test_bad_protocol_is_sanitized_and_terminal(self):
        for changed in ({'text':'x'*10001},{'direction':'PRIVATE'}, {'private':'PRIVATE'},
                        {'kind':'other','direction':'incoming_candidate'}, {'token':None}):
            session=self.session()
            raw=snapshot(row('a'),row('b'))
            raw['rows'][0].update(changed)
            with self.assertRaises(live_read.ReadError): session.accept(raw)
            self.assertEqual(session.report()['status'],'stopped')
            self.assertNotIn('PRIVATE',json.dumps(session.report()))
            with self.assertRaises(live_read.ReadError): session.accept(snapshot(row('a')))

    def test_unknown_nontext_and_blank_rows_do_not_promote_to_incoming_text(self):
        session=self.session()
        session.accept(snapshot(row('a'),row('b')))
        result=session.accept(snapshot(row('a'),row('b'),row('c','timestamp','unknown','other'),
                                       row('d','  ','unknown'),row('e','uncertain','unknown')))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0].direction,'unknown')
        self.assertEqual(session.report()['incoming_candidate_texts'],0)
        self.assertEqual(session.report()['unknown_candidate_texts'],1)

    def test_cli_outputs_only_counts_and_uses_the_joined_reader(self):
        stream=io.StringIO()
        def read(**kwargs):
            if kwargs != {'visual_text':True}: raise AssertionError('wrong native mode')
            return next(read.outputs)
        read.outputs=iter([snapshot(row('a'),row('b')),
                           snapshot(row('a'),row('b'),row('c','PRIVATE','self_candidate'))])
        with patch.object(live_read,'NativeReader') as reader, redirect_stdout(stream), \
                patch.object(live_read.time,'sleep'),patch.object(live_read.time,'monotonic',side_effect=[0,0,2]):
            reader.return_value.__enter__.return_value.read.side_effect=read
            result=live_read.main(['--client-path','fixture.exe','--observe-visual-occurrences','--seconds','1'])
        self.assertEqual(result,0)
        last=json.loads(stream.getvalue().splitlines()[-1])
        self.assertEqual(last['self_candidate_texts'],1)
        self.assertNotIn('PRIVATE',stream.getvalue())

    def test_native_protocol_retains_target_binding_and_rejects_unjoined_output(self):
        reader=live_read.NativeReader('D:/Weixin.exe')
        reader.executable=Path('fixture.exe')
        raw=snapshot(row('a'),row('b'))
        calls=[]
        def run(command,**kwargs):
            calls.append((command,kwargs))
            return subprocess.CompletedProcess(command,0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',side_effect=run):
            reader.read(visual_text=True)
            reader.read(visual_text=True)
            raw['status']='visual_snapshot'
            with self.assertRaises(live_read.ReadError): reader.read(visual_text=True)
        self.assertEqual(calls[0][0][-1],'--visual-text')
        self.assertEqual(json.loads(calls[1][1]['input'])['window'],34)


@unittest.skipUnless(os.name=='nt','Windows native fixtures required')
class NativeVisualTextTests(unittest.TestCase):
    def test_compiled_guard_rejects_text_changes_with_stable_token_and_geometry(self):
        framework=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319'
        with tempfile.TemporaryDirectory() as directory:
            executable=Path(directory)/'guard.exe'
            command=[str(framework/'csc.exe'),'/nologo','/target:exe','/main:VisualRowFixture',
                     '/out:'+str(executable),'/reference:'+str(framework/'System.Drawing.dll'),
                     '/reference:'+str(framework/'System.Web.Extensions.dll')]
            command+=['/reference:'+str(framework/'WPF'/name) for name in
                      ('UIAutomationClient.dll','UIAutomationTypes.dll','WindowsBase.dll')]
            command += [str(ROOT/'src/wechat_memory'/name) for name in ('live_reader.cs','visual_direction.cs')]
            command.append(str(ROOT/'tests/fixtures/visual_row_fixture.cs'))
            compiled=subprocess.run(command,capture_output=True,timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(compiled.returncode,0,compiled.stdout.decode(errors='replace'))
            done=subprocess.run([str(executable)],capture_output=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(done.returncode,0)
        self.assertEqual(json.loads(done.stdout),{'same':True,'text':False,'token':False,'kind':False,
                                                'bounds':False,'missing':False,'diagnostic':True})

    def test_real_native_joined_mode_rejects_missing_client_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            with live_read.NativeReader(str(Path(directory)/'Weixin.exe')) as reader:
                executable=reader.executable
                with self.assertRaises(live_read.ReadError) as error: reader.read(visual_text=True)
                self.assertEqual(str(error.exception),'client_unavailable')
            self.assertFalse(executable.exists())


if __name__=='__main__': unittest.main()
