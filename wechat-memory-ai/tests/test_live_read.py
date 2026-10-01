"""Real UI snapshots have session identity, not invented server message IDs."""
import json
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from wechat_memory import live_read

ROOT=Path(__file__).resolve().parents[1]


def snapshot(rows=(), **changes):
    value = dict(status='snapshot', process=12, started='123456', window=34,
                 root='ChatSingleWindowwxid_fixture', list_token='1.2.3',
                 rows=[dict(token=token, text=text, kind='text') for token, text in rows])
    value.update(changes)
    return value


class LiveReadTests(unittest.TestCase):
    def test_capability_report_exposes_counts_without_promoting_identity(self):
        raw=snapshot()
        raw.update(status='capability_snapshot',scroll_pattern=True,
                   vertical_scrollable=True,vertical_scroll_percent=100.0,distinct_automation_ids=1)
        raw['rows']=[dict(token='1',kind='text',automation_id=True,help_text=False,
                         item_status=False,item_type=False,labeled_by=False,text_pattern=True),
                     dict(token='2',kind='text',automation_id=False,help_text=False,
                         item_status=False,item_type=False,labeled_by=False,text_pattern=False)]
        report=live_read.capability_report(raw)
        self.assertEqual(report['automation_id_rows'],1)
        self.assertEqual(report['distinct_automation_ids'],1)
        self.assertEqual(report['text_pattern_rows'],1)
        self.assertTrue(report['bottom_observed'])
        self.assertFalse(report['sender_verified'])
        self.assertFalse(report['history_boundary_verified'])
        self.assertNotIn('wxid_fixture',json.dumps(report))
        with self.assertRaises(live_read.ReadError):
            live_read.ReadSession().accept(raw)

    def test_capability_report_rejects_malformed_and_unavailable_scroll(self):
        raw=snapshot()
        raw.update(status='capability_snapshot',scroll_pattern=False,
                   vertical_scrollable=None,vertical_scroll_percent=None,distinct_automation_ids=0)
        self.assertIsNone(live_read.capability_report(raw)['bottom_observed'])
        for change in ({'vertical_scroll_percent':100},{'scroll_pattern':1},
                       {'vertical_scrollable':False},{'text':'PRIVATE'},
                       {'distinct_automation_ids':True},{'distinct_automation_ids':1}):
            with self.assertRaises(live_read.ReadError):
                live_read.capability_report(dict(raw,**change))
        raw.update(scroll_pattern=True,vertical_scrollable=True)
        for value in (float('nan'),True,101,10**400):
            with self.assertRaises(live_read.ReadError):
                live_read.capability_report(dict(raw,vertical_scroll_percent=value))
        raw.update(vertical_scroll_percent=100)
        raw['rows']=[dict(token='1',kind='text',automation_id='PRIVATE',help_text=False,
                         item_status=False,item_type=False,labeled_by=False,text_pattern=False)]
        with self.assertRaises(live_read.ReadError):
            live_read.capability_report(raw)

    def test_cli_capability_inspection_preserves_binding_and_ignores_history(self):
        raw=snapshot()
        raw.update(status='capability_snapshot',scroll_pattern=False,
                   vertical_scrollable=None,vertical_scroll_percent=None,distinct_automation_ids=0)
        reader=live_read.NativeReader('D:/Weixin.exe')
        reader.executable=Path('fixture.exe')
        done=subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=done) as run:
            reader.read(capabilities=True)
            reader.read(capabilities=True)
        self.assertEqual(run.call_args.args[0][-1],'--capabilities')
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['window'],34)
        stream=io.StringIO()
        with patch.object(live_read,'NativeReader') as mocked, redirect_stdout(stream):
            mocked.return_value.__enter__.return_value.read.return_value=raw
            code=live_read.main(['--client-path','fixture.exe','--inspect-capabilities'])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(stream.getvalue())['status'],'capabilities_observed')
        mocked.return_value.__enter__.return_value.read.assert_called_once_with(capabilities=True)

    def test_layout_report_counts_geometry_without_promoting_sender(self):
        raw=snapshot()
        raw['status']='layout_snapshot'
        raw['rows']=[
            dict(token='1',kind='text',left_gap=0.0,right_gap=0.0,width_ratio=1.0,has_children=False),
            dict(token='2',kind='text',left_gap=0.5,right_gap=0.0,width_ratio=0.5,has_children=True),
            dict(token='3',kind='other',left_gap=0.0,right_gap=0.0,width_ratio=1.0,has_children=False)]
        report=live_read.layout_report(raw)
        self.assertEqual(report['rows'],3)
        self.assertEqual(report['text_rows'],2)
        self.assertEqual(report['full_width_text_rows'],1)
        self.assertEqual(report['text_rows_with_children'],1)
        self.assertFalse(report['sender_verified'])
        self.assertFalse(report['real_send_supported'])
        self.assertNotIn('wxid_fixture',json.dumps(report))
        self.assertNotIn('token',report)
        with self.assertRaises(live_read.ReadError):
            live_read.ReadSession().accept(raw)

    def test_layout_rejects_unknown_fields_and_nonfinite_geometry(self):
        raw=snapshot()
        raw['status']='layout_snapshot'
        row=dict(token='1',kind='text',left_gap=0.0,right_gap=0.0,width_ratio=1.0,has_children=False)
        for change in ({'left_gap':float('nan')},{'right_gap':True},{'width_ratio':0},{'left_gap':10**400},
                       {'has_children':'PRIVATE'},{'text':'PRIVATE'}):
            raw['rows']=[dict(row,**change)]
            with self.assertRaises(live_read.ReadError) as error:
                live_read.layout_report(raw)
            self.assertNotIn('PRIVATE',str(error.exception))

    def test_native_layout_mode_uses_same_binding_and_no_text_schema(self):
        raw=snapshot()
        raw['status']='layout_snapshot'
        raw['rows']=[dict(token='1',kind='text',left_gap=0.0,right_gap=0.0,width_ratio=1.0,has_children=False)]
        reader=live_read.NativeReader('D:/Weixin.exe')
        reader.executable=Path('fixture.exe')
        done=subprocess.CompletedProcess([],0,json.dumps(raw).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=done) as run:
            result=reader.read(layout=True)
            reader.read(layout=True)
        self.assertEqual(live_read.layout_report(result)['text_rows'],1)
        self.assertEqual(run.call_args.args[0][-1],'--layout')
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['window'],34)

    def test_cli_layout_reports_once_without_observing_history(self):
        raw=snapshot()
        raw['status']='layout_snapshot'
        stream=io.StringIO()
        with patch.object(live_read,'NativeReader') as reader, redirect_stdout(stream):
            reader.return_value.__enter__.return_value.read.return_value=raw
            result=live_read.main(['--client-path','fixture.exe','--inspect-layout'])
        report=json.loads(stream.getvalue())
        self.assertEqual(result,0)
        self.assertEqual(report['status'],'layout_observed')
        self.assertFalse(report['sender_verified'])
        self.assertNotIn('wxid_fixture',stream.getvalue())
        reader.return_value.__enter__.return_value.read.assert_called_once_with(layout=True)

    def test_report_counts_only_accepted_front_evictions(self):
        session = live_read.ReadSession()
        session.accept(snapshot([('1','old'),('2','b'),('3','c')]))
        self.assertEqual(session.report()['front_evictions'],0)
        self.assertIsNone(session.report()['stop_reason'])
        session.accept(snapshot([('2','b'),('3','c'),('4','new')]))
        session.accept(snapshot([('2','b'),('3','c'),('4','new'),('5','next')]))
        self.assertEqual(session.report()['front_evictions'],1)
        self.assertEqual(session.report()['seen_tokens'],5)
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot([('3','c'),('4','new'),('5','next'),('1','PRIVATE')]))
        report = session.report()
        self.assertEqual(report['stop_reason'],'message_token_reused')
        self.assertEqual(report['front_evictions'],1)
        self.assertEqual(report['seen_tokens'],5)
        self.assertEqual(report['observed_new_rows'],2)
        self.assertNotIn('PRIVATE',json.dumps(report))

    def test_continuity_and_binding_stop_reasons_are_distinct_and_terminal(self):
        for raw, reason in [
                (snapshot([('1','changed')]),'message_continuity_lost'),
                (snapshot([('1','old')],window=35),'window_or_list_changed'),
                (snapshot([('1','old'),('1','new')]),'invalid_snapshot')]:
            with self.subTest(reason=reason):
                session = live_read.ReadSession()
                session.accept(snapshot([('1','old')]))
                with self.assertRaises(live_read.ReadError):
                    session.accept(raw)
                self.assertEqual(session.report()['stop_reason'],reason)
                session.stop('interrupted')
                with self.assertRaises(live_read.ReadError):
                    session.accept(snapshot([('1','old')]))
                self.assertEqual(session.report()['stop_reason'],reason)

    def test_unknown_stop_reason_and_external_error_text_are_sanitized(self):
        session = live_read.ReadSession()
        session.stop('PRIVATE')
        self.assertEqual(session.report()['stop_reason'],'read_failed')
        session = live_read.ReadSession()
        with patch.object(live_read,'validate_snapshot',side_effect=live_read.ReadError('PRIVATE')):
            with self.assertRaises(live_read.ReadError) as error:
                session.accept(snapshot())
        self.assertEqual(session.report()['stop_reason'],'read_failed')
        self.assertNotIn('PRIVATE',str(error.exception)+json.dumps(session.report()))

    def test_cli_reports_native_failure_and_interruption_without_details(self):
        for error, reason in [(live_read.ReadError('native_reader_unavailable'),'native_reader_unavailable'),
                              (live_read.ReadError('PRIVATE'),'read_failed'),
                              (KeyboardInterrupt(),'interrupted')]:
            with self.subTest(reason=reason):
                stream = io.StringIO()
                with patch.object(live_read,'NativeReader') as reader, redirect_stdout(stream):
                    reader.return_value.__enter__.return_value.read.side_effect = error
                    result = live_read.main(['--client-path','fixture.exe','--seconds','1'])
                report = json.loads(stream.getvalue())
                self.assertEqual(result,3)
                self.assertEqual(report['stop_reason'],reason)
                self.assertEqual(report['status'],'stopped')
                self.assertNotIn('PRIVATE',stream.getvalue())

    def test_cli_keeps_session_reason_instead_of_generic_exception(self):
        stream = io.StringIO()
        with patch.object(live_read,'NativeReader') as reader, redirect_stdout(stream), \
                patch.object(live_read.time,'sleep'):
            reader.return_value.__enter__.return_value.read.side_effect = [
                snapshot([('1','old')]), snapshot([('1','changed')])]
            result = live_read.main(['--client-path','fixture.exe','--seconds','1'])
        reports = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(result,3)
        self.assertEqual(reports[-1]['stop_reason'],'message_continuity_lost')
        self.assertEqual(reports[-1]['observed_new_rows'],0)

    def test_baseline_ignores_history_and_preserves_identical_new_rows(self):
        session = live_read.ReadSession()
        self.assertEqual(session.accept(snapshot([('1', 'old')])), [])
        result = session.accept(snapshot([('1', 'old'), ('2', 'hello'), ('3', 'hello')]))
        self.assertEqual([row.text for row in result], ['hello', 'hello'])
        self.assertNotEqual(result[0].observation_id, result[1].observation_id)
        self.assertEqual(session.accept(snapshot([('1', 'old'), ('2', 'hello'), ('3', 'hello')])), [])
        self.assertFalse(session.report()['real_send_supported'])
        self.assertNotIn('hello', json.dumps(session.report()))
        self.assertNotIn('wxid_fixture', json.dumps(session.report()))

    def test_restart_baselines_current_rows_without_replaying(self):
        first = live_read.ReadSession()
        first.accept(snapshot([]))
        first.accept(snapshot([('1', 'new')]))
        restarted = live_read.ReadSession()
        self.assertEqual(restarted.accept(snapshot([('1', 'new')])), [])
        self.assertEqual(restarted.report()['observed_new_rows'], 0)

    def test_front_eviction_keeps_two_identical_appended_messages(self):
        session = live_read.ReadSession()
        baseline = [(str(i), 'history '+str(i)) for i in range(8)]
        session.accept(snapshot(baseline))
        raw = snapshot(baseline[2:]+[('8','timestamp'),('9','same'),('10','same')])
        raw['rows'][6]['kind'] = 'other'
        result = session.accept(raw)
        self.assertEqual([row.text for row in result], ['same','same'])
        self.assertNotEqual(result[0].observation_id,result[1].observation_id)
        self.assertEqual(session.accept(raw),[])
        self.assertEqual(session.report()['observed_new_rows'],3)
        self.assertEqual(session.report()['observed_new_texts'],2)
        self.assertFalse(session.report()['history_boundary_verified'])
        self.assertTrue(all(row.direction == 'unverified' for row in result))

    def test_front_eviction_requires_two_unchanged_anchors_and_append(self):
        baseline = [('1','a'),('2','b'),('3','c'),('4','d')]
        invalid = [baseline[2:], [('4','d'),('5','e')], [('5','e'),('6','f')],
                   [('2','b'),('4','d'),('5','e')],
                   [('3','c'),('2','b'),('4','d'),('5','e')],
                   [('3','changed'),('4','d'),('5','e')]]
        for rows in invalid:
            with self.subTest(rows=rows):
                session = live_read.ReadSession()
                session.accept(snapshot(baseline))
                with self.assertRaises(live_read.ReadError):
                    session.accept(snapshot(rows))
                self.assertEqual(session.report()['observed_new_rows'],0)
                self.assertEqual(session.report()['status'],'stopped')

    def test_evicted_tokens_cannot_reappear_even_with_changed_text(self):
        for text in ('a','different'):
            with self.subTest(text=text):
                session = live_read.ReadSession()
                session.accept(snapshot([('1','a'),('2','b'),('3','c')]))
                session.accept(snapshot([('2','b'),('3','c'),('4','d')]))
                with self.assertRaises(live_read.ReadError):
                    session.accept(snapshot([('3','c'),('4','d'),('5','e'),('1',text)]))
                self.assertEqual(session.report()['observed_new_rows'],1)

    def test_plain_append_cannot_replay_evicted_token(self):
        session = live_read.ReadSession()
        session.accept(snapshot([('1','a'),('2','b'),('3','c')]))
        session.accept(snapshot([('2','b'),('3','c'),('4','d')]))
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot([('2','b'),('3','c'),('4','d'),('1','a')]))

    def test_seen_token_limit_stops_before_returning_partial_batch(self):
        session = live_read.ReadSession()
        rows = [(str(i),'text') for i in range(3)]
        session.accept(snapshot(rows))
        for i in range(3,4096):
            rows = rows[1:]+[(str(i),'text')]
            self.assertEqual(len(session.accept(snapshot(rows))),1)
        self.assertEqual(session.accept(snapshot(rows)),[])
        before = session.report()['observed_new_rows']
        with self.assertRaises(live_read.ReadError):
            session.accept(snapshot(rows[1:]+[('4096','text'),('4097','text')]))
        self.assertEqual(session.report()['observed_new_rows'],before)
        self.assertEqual(session.report()['stop_reason'],'session_token_limit')
        self.assertEqual(session.report()['seen_tokens'],4096)

    def test_eviction_then_restart_baselines_without_replay(self):
        rows = [('1','a'),('2','b'),('3','c')]
        first = live_read.ReadSession()
        first.accept(snapshot(rows))
        rows = rows[1:]+[('4','new')]
        self.assertEqual(len(first.accept(snapshot(rows))),1)
        restarted = live_read.ReadSession()
        self.assertEqual(restarted.accept(snapshot(rows)),[])
        self.assertEqual(restarted.report()['observed_new_texts'],0)

    def test_identity_and_list_changes_stop_and_cannot_rearm(self):
        for change in ({'root':'ChatSingleWindowwxid_other'}, {'window':35},
                       {'process':13}, {'started':'other'}, {'list_token':'new'}):
            session = live_read.ReadSession()
            session.accept(snapshot([('1', 'old')]))
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot([('1', 'old'), ('2', 'private')], **change))
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot([('1', 'old')]))

    def test_rebuild_removed_history_or_reused_token_stops(self):
        for rows in ([('2','old')], [], [('1','changed')], [('1','old'),('1','new')],
                     [('2','new'),('1','old')]):
            session = live_read.ReadSession()
            session.accept(snapshot([('1','old')]))
            with self.assertRaises(live_read.ReadError):
                session.accept(snapshot(rows))

    def test_bad_schema_and_non_independent_chats_rejected(self):
        for change in ({'root':'ChatGroupWindowroom'}, {'process':True}, {'rows':'PRIVATE'},
                       {'rows':[dict(token='1', text='x'*10001, kind='text')]},
                       {'rows':[dict(token='1', text='x', kind='guessed')]},
                       {'status':'PRIVATE'}, {'list_token':''}):
            raw = snapshot()
            raw.update(change)
            with self.assertRaises(live_read.ReadError) as error:
                live_read.ReadSession().accept(raw)
            self.assertNotIn('PRIVATE', str(error.exception))

    def test_non_text_rows_never_become_text_observations(self):
        session = live_read.ReadSession()
        session.accept(snapshot([('1','baseline')]))
        raw = snapshot([('1','baseline')])
        raw['rows'].append(dict(token='2', text='private', kind='other'))
        self.assertEqual(session.accept(raw), [])
        self.assertEqual(session.report()['observed_new_rows'], 1)
        self.assertEqual(session.report()['observed_new_texts'], 0)

    def test_initial_empty_list_never_promotes_late_history(self):
        session=live_read.ReadSession()
        self.assertEqual(session.accept(snapshot([])),[])
        self.assertEqual(session.accept(snapshot([('1','late history')])),[])
        self.assertEqual(session.report()['observed_new_texts'],0)
        self.assertFalse(session.report()['history_boundary_verified'])

    def test_reader_transmits_binding_before_subsequent_native_reads(self):
        reader=live_read.NativeReader('D:/Weixin.exe')
        reader.executable=Path('fixture.exe')
        done=subprocess.CompletedProcess([],0,json.dumps(snapshot([('1','private')])).encode(),b'')
        with patch.object(live_read.subprocess,'run',return_value=done) as run:
            reader.read()
            reader.read()
        second=run.call_args_list[1].kwargs
        binding=json.loads(second['input'])
        self.assertEqual(binding['window'],34)
        self.assertEqual(binding['root'],'ChatSingleWindowwxid_fixture')
        self.assertNotIn('private',second['input'].decode())

    @unittest.skipUnless(os.name=='nt','Windows native compiler required')
    def test_temporary_creation_and_cleanup_errors_are_sanitized(self):
        reader=live_read.NativeReader('D:/Weixin.exe')
        with patch.object(Path,'is_file',side_effect=PermissionError('PRIVATE')):
            with self.assertRaises(live_read.ReadError) as result:
                reader.__enter__()
            self.assertNotIn('PRIVATE',str(result.exception))
        with patch.object(live_read.tempfile,'TemporaryDirectory',side_effect=OSError('PRIVATE')):
            with self.assertRaises(live_read.ReadError) as result:
                reader.__enter__()
            self.assertNotIn('PRIVATE',str(result.exception))
        temporary=unittest.mock.Mock()
        temporary.cleanup.side_effect=OSError('PRIVATE')
        reader._temporary=temporary
        with self.assertRaises(live_read.ReadError) as result:
            reader.__exit__(None,None,None)
        self.assertNotIn('PRIVATE',str(result.exception))

    def test_timeout_child_failure_and_private_errors_are_sanitized(self):
        reader = live_read.NativeReader('D:/Weixin.exe')
        reader.executable = Path('fixture.exe')
        for error in (OSError('PRIVATE'), subprocess.TimeoutExpired('SECRET', 5)):
            with patch.object(live_read.subprocess, 'run', side_effect=error):
                with self.assertRaises(live_read.ReadError) as result:
                    reader.read()
                self.assertNotIn('PRIVATE', str(result.exception))
                self.assertNotIn('SECRET', str(result.exception))

    def test_native_failure_code_is_allowlisted_and_requires_error_exit(self):
        reader=live_read.NativeReader('D:/Weixin.exe')
        reader.executable=Path('fixture.exe')
        for raw, code, expected in [
                ({'status':'reader_error','reason':'window_minimized'},3,'window_minimized'),
                ({'status':'reader_error','reason':'window_or_list_changed'},3,'window_or_list_changed'),
                ({'status':'reader_error','reason':'PRIVATE'},3,'native_reader_unavailable'),
                ({'status':'reader_error','reason':'window_minimized','text':'PRIVATE'},3,'native_reader_unavailable'),
                ({'status':'reader_error','reason':'window_minimized'},0,'native_reader_unavailable')]:
            with self.subTest(expected=expected,exit=code):
                done=subprocess.CompletedProcess([],code,json.dumps(raw).encode(),b'PRIVATE')
                with patch.object(live_read.subprocess,'run',return_value=done):
                    with self.assertRaises(live_read.ReadError) as error:
                        reader.read()
                self.assertEqual(str(error.exception),expected)

    def test_native_timeout_has_specific_sanitized_reason(self):
        reader=live_read.NativeReader('D:/Weixin.exe')
        reader.executable=Path('fixture.exe')
        with patch.object(live_read.subprocess,'run',side_effect=subprocess.TimeoutExpired('PRIVATE',8)):
            with self.assertRaises(live_read.ReadError) as error:
                reader.read()
        self.assertEqual(str(error.exception),'native_reader_timeout')

    def test_literal_child_arguments_and_malformed_output(self):
        reader = live_read.NativeReader('D:/spaces & quote/Weixin.exe')
        reader.executable = Path('fixture.exe')
        for output in (b'PRIVATE', b'[]', b'{"status":"PRIVATE"}',b'x'*4_000_001):
            done=subprocess.CompletedProcess([],0,output,b'PRIVATE')
            with patch.object(live_read.subprocess,'run',return_value=done) as run:
                with self.assertRaises(live_read.ReadError):
                    reader.read()
                args,kwargs=run.call_args
                self.assertEqual(args[0],[str(reader.executable),reader.client_path])
                self.assertFalse(kwargs.get('shell',False))
                self.assertEqual(kwargs['timeout'],8)
                self.assertEqual(kwargs['input'],b'null')

    @unittest.skipUnless(os.name=='nt','Windows native compiler required')
    def test_real_native_build_missing_client_and_temporary_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            with live_read.NativeReader(str(Path(directory)/'Weixin.exe')) as reader:
                executable=reader.executable
                self.assertTrue(executable.is_file())
                with self.assertRaises(live_read.ReadError) as error:
                    reader.read()
                self.assertEqual(str(error.exception),'client_unavailable')
                with self.assertRaises(live_read.ReadError) as error:
                    reader.read(layout=True)
                self.assertEqual(str(error.exception),'client_unavailable')
            self.assertFalse(executable.parent.exists())

    @unittest.skipUnless(os.name=='nt','Windows entry points required')
    def test_windows_entry_points_preserve_config_and_propagate_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            config=directory/'private.toml'
            config.write_text('PRIVATE: deliberately invalid personal configuration')
            for shell in filter(None,(shutil.which('powershell.exe'),shutil.which('pwsh.exe'))):
                with self.subTest(shell=shell):
                    done=subprocess.run([shell,'-NoProfile','-NonInteractive','-File',
                        str(ROOT/'scripts/windows.ps1'),'-Action','listen-wechat',
                        '-ClientPath',str(directory/'Weixin.exe'),'-ListenSeconds','1',
                        '-Python',sys.executable,'-Config',str(config)],capture_output=True,timeout=30)
                    self.assertEqual(done.returncode,3)
                    report=json.loads(done.stdout)
                    self.assertEqual(report['status'],'stopped')
                    self.assertFalse(report['real_send_supported'])
                    self.assertNotIn('PRIVATE',done.stdout.decode())
                    self.assertEqual(config.read_text(),'PRIVATE: deliberately invalid personal configuration')
            self.assertEqual(list(directory.iterdir()),[config])


if __name__ == '__main__':
    unittest.main()
