"""Direction hints must have positive visual evidence on both sides of a row."""
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


def visual_snapshot():
    return dict(status='visual_snapshot',process=12,started='123456',window=34,capture_attempts=1,
                root='ChatSingleWindowwxid_fixture',list_token='1.2.3',rows=[
                    dict(token='1',kind='text',direction='incoming_candidate',reason='incoming_evidence'),
                    dict(token='2',kind='text',direction='self_candidate',reason='self_evidence'),
                    dict(token='3',kind='text',direction='unknown',reason='avatar_inconclusive'),
                    dict(token='4',kind='other',direction='unknown',reason='not_text')])


@unittest.skipUnless(os.name=='nt','Windows .NET bitmap fixture required')
class VisualBitmapTests(unittest.TestCase):
    def test_native_capture_reads_only_a_synthetic_window_and_returns_no_pixels(self):
        framework=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319'
        with tempfile.TemporaryDirectory() as directory:
            executable=Path(directory)/'capture.exe'
            command=[str(framework/'csc.exe'),'/nologo','/target:exe','/out:'+str(executable),
                     '/reference:'+str(framework/'System.Drawing.dll'),
                     '/reference:'+str(framework/'System.Windows.Forms.dll'),
                     '/reference:'+str(framework/'System.Web.Extensions.dll'),
                     str(ROOT/'src/wechat_memory/visual_direction.cs'),
                     str(ROOT/'tests/fixtures/visual_capture_fixture.cs')]
            compiled=subprocess.run(command,capture_output=True,timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(compiled.returncode,0,compiled.stdout.decode(errors='replace'))
            done=subprocess.run([str(executable)],capture_output=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(done.returncode,0,done.stderr.decode(errors='replace'))
        self.assertEqual(json.loads(done.stdout),dict(direction='incoming_candidate',width=600,height=72))

    def test_real_native_visual_mode_keeps_client_scope_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            with live_read.NativeReader(str(Path(directory)/'Weixin.exe')) as reader:
                executable=reader.executable
                with self.assertRaises(live_read.ReadError) as error: reader.read(visual=True)
                self.assertEqual(str(error.exception),'client_unavailable')
            self.assertFalse(executable.exists())

    def test_positive_and_ambiguous_synthetic_rows(self):
        framework=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319'
        with tempfile.TemporaryDirectory() as directory:
            executable=Path(directory)/'fixture.exe'
            command=[str(framework/'csc.exe'),'/nologo','/target:exe','/out:'+str(executable),
                     '/reference:'+str(framework/'System.Drawing.dll'),
                     '/reference:'+str(framework/'System.Web.Extensions.dll'),
                     str(ROOT/'src/wechat_memory/visual_direction.cs'),
                     str(ROOT/'tests/fixtures/visual_direction_fixture.cs')]
            compiled=subprocess.run(command,capture_output=True,timeout=25,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(compiled.returncode,0,compiled.stdout.decode(errors='replace'))
            done=subprocess.run([str(executable)],capture_output=True,timeout=8,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(done.returncode,0)
        results=json.loads(done.stdout)
        for name,direction in results.items():
            expected={'incoming':'incoming_candidate','self':'self_candidate',
                      'dark_incoming':'incoming_candidate','dark_self':'self_candidate',
                      'scaled_incoming':'incoming_candidate','scaled_self':'self_candidate'}.get(name,'unknown')
            with self.subTest(case=name): self.assertEqual(direction,expected)
        self.assertEqual(len(results),18)


class VisualProtocolTests(unittest.TestCase):
    def test_visual_hints_are_counted_without_verified_sender_or_identity(self):
        raw=visual_snapshot()
        report=live_read.visual_report(raw)
        self.assertEqual((report['incoming_candidates'],report['self_candidates'],report['unknown_texts']),(1,1,1))
        self.assertEqual(report['text_rows'],3)
        for field in ('sender_verified','history_boundary_verified','real_send_supported','model_called'):
            self.assertFalse(report[field])
        self.assertNotIn('wxid_fixture',json.dumps(report))
        with self.assertRaises(live_read.ReadError): live_read.ReadSession().accept(raw)

    def test_visual_protocol_rejects_extra_data_unknown_direction_and_nontext_promotion(self):
        for change in ({'direction':'PRIVATE'},{'direction':None},{'text':'PRIVATE'},
                       {'kind':'other','direction':'incoming_candidate'}):
            raw=visual_snapshot()
            raw['rows'][0].update(change)
            with self.assertRaises(live_read.ReadError): live_read.visual_report(raw)

    def test_visual_cli_is_one_shot_and_cannot_feed_the_read_session(self):
        stream=io.StringIO()
        with patch.object(live_read,'NativeReader') as reader, redirect_stdout(stream):
            reader.return_value.__enter__.return_value.read.return_value=visual_snapshot()
            result=live_read.main(['--client-path','fixture.exe','--inspect-visual'])
        self.assertEqual(result,0)
        report=json.loads(stream.getvalue())
        self.assertEqual(report['status'],'visual_observed')
        self.assertNotIn('observed_new_rows',report)
        self.assertNotIn('wxid_fixture',stream.getvalue())

    def test_native_visual_mode_preserves_bound_target_and_rejects_plain_snapshot(self):
        reader=live_read.NativeReader('D:/Weixin.exe')
        reader.executable=Path('fixture.exe')
        raw=visual_snapshot()
        done=subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=done) as run:
            reader.read(visual=True)
            reader.read(visual=True)
        self.assertEqual(run.call_args.args[0][-1],'--visual')
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['window'],34)
        raw['status']='snapshot'
        with patch.object(live_read.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')):
            with self.assertRaises(live_read.ReadError): reader.read(visual=True)


if __name__=='__main__': unittest.main()
